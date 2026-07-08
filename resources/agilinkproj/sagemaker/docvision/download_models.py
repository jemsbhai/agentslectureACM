#!/usr/bin/env python3
"""
Download VLM weights for the mini-VLM benchmark, plus a sample smoke-test image.

Reads configs/registry.yaml and snapshot_downloads each model into
<MODEL_ROOT>/<name>. Writes manifest.json recording the resolved repo commit SHA
and on-disk size per model, so every benchmarked weight is pinned to an exact
revision (reproducibility).

Run on the SageMaker instance (Linux terminal / notebook), NOT local PowerShell.

Gated models (e.g. Gemma 3) require:
  1) the license accepted on the model's HF page while logged in, and
  2) HF_TOKEN exported in the environment (see .env.example).

Usage:
  python scripts/download_models.py                          # all models in the registry
  python scripts/download_models.py --models qwen3-vl-4b,smolvlm2-2.2b
  python scripts/download_models.py --model-root /data/models
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing pyyaml. Install with: pip install pyyaml")

try:
    from huggingface_hub import HfApi, snapshot_download
    from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError
except ImportError:
    sys.exit("Missing huggingface_hub. Install with: pip install 'huggingface_hub>=0.26'")

# Two cats on a couch — a standard, stable image used across HF VLM examples.
SAMPLE_IMAGE_URL = "http://images.cocodataset.org/val2017/000000039769.jpg"


def dir_size_gb(path: Path) -> float:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total / (1024 ** 3)


def fetch_sample_image(dest: Path) -> None:
    if dest.exists():
        print(f"[sample image] already present: {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[sample image] downloading {SAMPLE_IMAGE_URL}")
    try:
        urllib.request.urlretrieve(SAMPLE_IMAGE_URL, dest)
        print(f"[sample image] saved -> {dest}")
    except Exception as e:  # noqa: BLE001 - we just want a clear message, not a crash
        print(f"[sample image] WARNING: download failed ({e}).")
        print(f"  Drop any .jpg at {dest} before running the smoke test, or pass --image.")


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Download VLM weights for the benchmark.")
    ap.add_argument("--registry", default=str(here.parent / "configs" / "registry.yaml"))
    ap.add_argument(
        "--model-root",
        default=os.environ.get("MODEL_ROOT", str(Path.home() / "vlm-bench" / "models")),
        help="where weights are stored (default: $MODEL_ROOT or ~/vlm-bench/models)",
    )
    ap.add_argument("--models", default="", help="comma-separated subset of model names (default: all)")
    ap.add_argument("--skip-image", action="store_true", help="do not fetch the sample smoke-test image")
    args = ap.parse_args()

    registry = yaml.safe_load(Path(args.registry).read_text())
    models = registry["models"]
    if args.models:
        wanted = {m.strip() for m in args.models.split(",") if m.strip()}
        models = [m for m in models if m["name"] in wanted]
        missing = wanted - {m["name"] for m in models}
        if missing:
            sys.exit(f"Unknown model name(s): {sorted(missing)}")

    model_root = Path(args.model_root).expanduser()
    model_root.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    print(f"Model root: {model_root}")
    print(f"HF token:   {'set' if token else 'NOT set (gated models will be skipped)'}")
    print(f"Models:     {', '.join(m['name'] for m in models)}\n")

    if not args.skip_image:
        # store assets alongside the models dir (e.g. ~/vlm-bench/assets/sample.jpg)
        fetch_sample_image(model_root.parent / "assets" / "sample.jpg")

    api = HfApi()
    manifest = []
    for m in models:
        name, repo = m["name"], m["repo_id"]
        target = model_root / name
        print(f"=== {name}  ({repo}) ===")

        if m.get("gated") and not token:
            print(f"  SKIP: {repo} is gated and HF_TOKEN is not set.")
            print(f"        Accept the license at https://huggingface.co/{repo} then export HF_TOKEN.\n")
            manifest.append({"name": name, "repo_id": repo, "status": "skipped_gated"})
            continue

        t0 = time.time()
        try:
            local_path = snapshot_download(repo_id=repo, local_dir=str(target), token=token)
            try:
                sha = api.repo_info(repo_id=repo, token=token).sha
            except Exception:  # noqa: BLE001
                sha = None
            size = round(dir_size_gb(target), 2)
            dt = round(time.time() - t0, 1)
            print(f"  OK  -> {local_path}")
            print(f"      commit: {sha}   size: {size} GB   time: {dt}s\n")
            manifest.append(
                {"name": name, "repo_id": repo, "status": "ok",
                 "path": str(target), "commit": sha, "size_gb": size}
            )
        except GatedRepoError:
            print(f"  FAIL: {repo} is gated/denied. Accept the license on its HF page and check HF_TOKEN.\n")
            manifest.append({"name": name, "repo_id": repo, "status": "gated_denied"})
        except RepositoryNotFoundError:
            print(f"  FAIL: repo {repo} not found. Verify the repo id in the registry.\n")
            manifest.append({"name": name, "repo_id": repo, "status": "not_found"})
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL: {type(e).__name__}: {e}\n")
            manifest.append({"name": name, "repo_id": repo, "status": "error", "error": str(e)})

    manifest_path = model_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    ok = sum(1 for x in manifest if x["status"] == "ok")
    print(f"Done. {ok}/{len(manifest)} downloaded. Manifest -> {manifest_path}")
    sys.exit(0 if ok == len(manifest) else 1)


if __name__ == "__main__":
    main()
