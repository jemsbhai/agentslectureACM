# VLM Benchmark - H100 candidate set (LECT / SageMaker)

Stage 1 of the Jira task: get the candidate weights onto the LECT instance and confirm
every model loads and runs one inference on a single H100 (80GB). Accuracy, throughput,
and cost come in the next stages.

All commands run in the **SageMaker / LECT terminal (Linux / bash)**, not local PowerShell.

## Where this fits in the ticket
- [ ] Candidate models identified and benchmarked on H100 80GB via LECT  <- **these scripts start this**
- [ ] Results cover performance, quality, and cost                        <- next: accuracy harness + throughput/cost
- [ ] Comparison and recommendation documented and shared                 <- final: the recommendation doc

## The 18-model candidate set
All fit a single H100 (80GB) for a short-context smoke test. Ordered small -> large:
`gemma4-e2b, gemma4-e4b, smolvlm2-2.2b, qwen3-vl-4b, gemma3-4b, phi4-multimodal,
qwen2.5-vl-7b, qwen3-vl-8b, internvl3-8b, gemma3-12b, gemma4-12b, internvl3-14b,
gemma4-26b-a4b, gemma3-27b, qwen3-vl-30b-a3b, qwen2.5-vl-32b, qwen3-vl-32b, gemma4-31b`.

Full model list, repo IDs, and per-model notes live in `configs/registry.yaml`.

## Two gotchas
1. **Two Python environments.** Phi-4-multimodal pins `transformers==4.48.2`; Gemma 4 and
   Qwen3-VL need the latest. So: **main env** (latest transformers) for 17 models, **phi4 venv**
   (4.48.2) for Phi-4 only.
2. **Single H100.** On a multi-GPU instance (an 8x H100 ml.p5) set `CUDA_VISIBLE_DEVICES=0`
   so only one card is used - that is the constraint from the ticket.

## Storage
The 18 weight sets total ~577 GB at bf16. Point `MODEL_ROOT` at a volume with **>= 750 GB free**.
`hf_transfer` (in requirements) speeds up the download a lot.

## Fit caveat
The smoke test uses a short prompt, so all 18 load. For full 256K-context production runs the
larger entries may need quantization; gemma4-31b (~62 GB weights) is borderline on 80GB at full
context. See the per-model notes in the registry and the H100 Fits column in the tracking doc.

---

## Setup

### 1) Token + paths
```bash
cp .env.example .env          # edit HF_TOKEN and MODEL_ROOT
set -a; source .env; set +a
```
Accept the Gemma 3 and Gemma 4 licenses once (while logged into HF) on each model page.

### 2) Main environment
```bash
# Don't reinstall torch if this already prints a CUDA-enabled build:
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
pip install -r requirements-main.txt
# If a model later fails with "no class ..." (Gemma 4 too new for PyPI transformers):
# pip install "git+https://github.com/huggingface/transformers.git"
```

### 3) Download weights (+ sample image)
```bash
python scripts/download_models.py
# subset: python scripts/download_models.py --models qwen3-vl-32b,gemma4-31b
```
Writes `<MODEL_ROOT>/manifest.json` with the pinned commit SHA + size per model.

### 4) Smoke test (main-env models)
```bash
python scripts/smoke_test.py
```
Prints PASS/FAIL + tok/s + peak VRAM per model and writes `smoke_results.json`.
The tok/s and peak-VRAM numbers feed the later cost analysis
(cost per 1M tokens ~= instance $/hr / (tok/s * 3.6)).

### 5) Phi-4 in its own venv
```bash
python -m venv ~/venv-phi4
source ~/venv-phi4/bin/activate
pip install -r requirements-phi4.txt
set -a; source .env; set +a
python scripts/smoke_test.py --models phi4-multimodal
deactivate
```

---

## If a model FAILs
Paste the traceback (it's in `smoke_results.json` and the console) and I'll patch that
model's handler. Most likely to need a tweak: the Gemma 4 family (brand new), the MoE
entries (qwen3-vl-30b-a3b, gemma4-26b-a4b), and internvl3-14b (repo-id / loader).
The smoke test already tries the registry class, then falls back to AutoModelForImageTextToText,
so many class-name mismatches self-heal.
