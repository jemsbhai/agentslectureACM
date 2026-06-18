#!/usr/bin/env python3
"""
Smoke test the mini-VLM benchmark models.

For each model: load it, run ONE image+text inference, and report load time,
inference time, approx tokens/sec, peak VRAM, and an output snippet. This is a
go/no-go check that the model loads and produces sensible text BEFORE the full
accuracy benchmark. It is NOT an accuracy measurement.

Models are loaded sequentially and freed between runs, so a single 40GB A100 is
plenty even though the combined weights are larger.

Two environments are expected (see README), because Phi-4-multimodal pins
transformers==4.48.2 while Qwen3-VL needs >=4.57:
  main env  -> the 5 unified-API models (profile: hf_chat)   ->  python scripts/smoke_test.py
  phi4 venv -> Phi-4-multimodal only (profile: phi4_legacy)  ->  python scripts/smoke_test.py --models phi4-multimodal

Other usage:
  python scripts/smoke_test.py --models qwen3-vl-4b,internvl3-8b --max-new-tokens 48
"""
import argparse
import gc
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path

try:
    import yaml
    import torch
    import transformers
    from transformers import AutoProcessor
    from PIL import Image
except ImportError as e:
    sys.exit(f"Missing dependency: {e}. Install requirements-main.txt (or requirements-phi4.txt) first.")

DEFAULT_PROMPT = "Describe this image in one sentence."


def env_snapshot() -> dict:
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none"
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": gpu,
    }


def load_image(path: str) -> "Image.Image":
    return Image.open(path).convert("RGB")


def _resolve_class(class_name: str):
    if not hasattr(transformers, class_name):
        raise AttributeError(
            f"transformers {transformers.__version__} has no class '{class_name}'. "
            f"Upgrade transformers (e.g. Qwen3-VL needs >= 4.57)."
        )
    return getattr(transformers, class_name)


def run_hf_chat(cfg, model_path, image, prompt, max_new_tokens):
    """Unified path: SmolVLM2, Qwen3-VL, Gemma 3, Qwen2.5-VL, InternVL3-hf."""
    trust = bool(cfg.get("trust_remote_code", False))
    model_class = _resolve_class(cfg["model_class"])
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=trust)
    model = model_class.from_pretrained(
        model_path, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=trust
    ).eval()

    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
    # Primary: render the chat template to text, then bind the image via the processor.
    try:
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[image], return_tensors="pt").to(model.device)
        bind_path = "two_step"
    except Exception:  # noqa: BLE001 - fall back to letting the template tokenize the image directly
        messages2 = [{"role": "user", "content": [
            {"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
        inputs = processor.apply_chat_template(
            messages2, tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt",
        ).to(model.device)
        bind_path = "all_in_one"

    in_len = inputs["input_ids"].shape[1]
    t0 = time.time()
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    infer_s = time.time() - t0

    gen_ids = out[:, in_len:]
    new_tokens = int(gen_ids.shape[1])
    text_out = processor.batch_decode(gen_ids, skip_special_tokens=True)[0].strip()
    del model, processor, inputs, out, gen_ids
    return text_out, infer_s, new_tokens, bind_path


def run_phi4_legacy(cfg, model_path, image, prompt, max_new_tokens):
    """Phi-4-multimodal: custom prompt tags + trust_remote_code (its own venv)."""
    from transformers import AutoModelForCausalLM, GenerationConfig

    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
    # 'eager' avoids a hard flash-attn dependency; set PHI4_ATTN=flash_attention_2 for speed.
    attn = os.environ.get("PHI4_ATTN", "eager")
    model = AutoModelForCausalLM.from_pretrained(
        model_path, device_map="cuda", torch_dtype="auto",
        trust_remote_code=True, _attn_implementation=attn,
    ).eval()
    gen_cfg = GenerationConfig.from_pretrained(model_path)

    prompt_text = f"<|user|><|image_1|>{prompt}<|end|><|assistant|>"
    inputs = processor(text=prompt_text, images=[image], return_tensors="pt").to(model.device)
    in_len = inputs["input_ids"].shape[1]
    t0 = time.time()
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, generation_config=gen_cfg)
    infer_s = time.time() - t0

    gen_ids = out[:, in_len:]
    new_tokens = int(gen_ids.shape[1])
    text_out = processor.batch_decode(gen_ids, skip_special_tokens=True)[0].strip()
    del model, processor, inputs, out, gen_ids
    return text_out, infer_s, new_tokens, "phi4_legacy"


HANDLERS = {"hf_chat": run_hf_chat, "phi4_legacy": run_phi4_legacy}


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Smoke test mini-VLM models (one inference each).")
    ap.add_argument("--registry", default=str(here.parent / "configs" / "registry.yaml"))
    ap.add_argument(
        "--model-root",
        default=os.environ.get("MODEL_ROOT", str(Path.home() / "vlm-bench" / "models")),
    )
    ap.add_argument("--image", default="", help="test image path (default: <model-root>/../assets/sample.jpg)")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--models", default="", help="comma-separated subset (default: registry default_run==true)")
    ap.add_argument("--max-new-tokens", type=int, default=64)
    ap.add_argument("--output", default="smoke_results.json")
    args = ap.parse_args()

    if not torch.cuda.is_available():
        print("WARNING: CUDA not available; this will be very slow and may not fit in RAM.\n")

    registry = yaml.safe_load(Path(args.registry).read_text())
    all_models = registry["models"]
    if args.models:
        wanted = {m.strip() for m in args.models.split(",") if m.strip()}
        models = [m for m in all_models if m["name"] in wanted]
        missing = wanted - {m["name"] for m in models}
        if missing:
            sys.exit(f"Unknown model name(s): {sorted(missing)}")
    else:
        models = [m for m in all_models if m.get("default_run", True)]

    model_root = Path(args.model_root).expanduser()
    image_path = args.image or str(model_root.parent / "assets" / "sample.jpg")
    if not Path(image_path).exists():
        sys.exit(f"Test image not found: {image_path}. Run download_models.py first or pass --image.")
    image = load_image(image_path)

    env = env_snapshot()
    print("Environment:", json.dumps(env), "\n")

    results = []
    for m in models:
        name = m["name"]
        local_path = model_root / name
        path_arg = str(local_path) if local_path.exists() else m["repo_id"]
        if not local_path.exists():
            print(f"[{name}] local weights not found at {local_path}; trying hub id {m['repo_id']}.")

        handler = HANDLERS.get(m["profile"])
        if handler is None:
            results.append({"name": name, "status": "FAIL", "error": f"unknown profile {m['profile']}"})
            continue

        print(f"=== {name}  ({m['profile']}) ===")
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.empty_cache()

        t0 = time.time()
        try:
            text_out, infer_s, new_tokens, bind_path = handler(
                m, path_arg, image, args.prompt, args.max_new_tokens
            )
            total_s = time.time() - t0
            load_s = max(0.0, total_s - infer_s)
            peak_gb = (torch.cuda.max_memory_allocated() / 1024 ** 3) if torch.cuda.is_available() else 0.0
            tok_s = (new_tokens / infer_s) if infer_s > 0 else 0.0
            snippet = (text_out[:120] + "...") if len(text_out) > 120 else text_out
            print(f"  PASS  load {load_s:.1f}s  infer {infer_s:.1f}s  "
                  f"{new_tokens} tok  {tok_s:.1f} tok/s  peak {peak_gb:.1f} GB  [{bind_path}]")
            print(f"  out: {snippet!r}\n")
            results.append({
                "name": name, "status": "PASS", "params": m.get("params"),
                "load_s": round(load_s, 1), "infer_s": round(infer_s, 2),
                "new_tokens": new_tokens, "tok_s": round(tok_s, 1),
                "peak_vram_gb": round(peak_gb, 1), "bind_path": bind_path,
                "output": text_out,
            })
        except Exception as e:  # noqa: BLE001 - report, don't abort the whole run
            tb = traceback.format_exc(limit=4)
            print(f"  FAIL  {type(e).__name__}: {e}\n{tb}")
            results.append({"name": name, "status": "FAIL",
                            "error": f"{type(e).__name__}: {e}", "traceback": tb})
        finally:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    print("==================== SUMMARY ====================")
    for r in results:
        if r["status"] == "PASS":
            print(f"  PASS  {r['name']:<18} {r['tok_s']:>6.1f} tok/s  {r['peak_vram_gb']:>5.1f} GB")
        else:
            print(f"  FAIL  {r['name']:<18} {r.get('error', '')}")

    out = {
        "env": env, "prompt": args.prompt, "image": image_path,
        "max_new_tokens": args.max_new_tokens, "results": results,
    }
    Path(args.output).write_text(json.dumps(out, indent=2))
    print(f"\nWrote {args.output}")
    n_fail = sum(1 for r in results if r["status"] != "PASS")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
