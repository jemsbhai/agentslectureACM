# Mini-VLM Benchmark — SageMaker setup (download + smoke test)

The first stage of the benchmark: get the model weights onto the instance and confirm
every model loads and runs one inference. Accuracy/throughput benchmarking comes after.

All commands below run in the **SageMaker terminal (Linux / bash)**, not local PowerShell.

## Models in this round
| name              | repo                                   | params | env  |
|-------------------|----------------------------------------|--------|------|
| smolvlm2-2.2b     | HuggingFaceTB/SmolVLM2-2.2B-Instruct   | 2.2B   | main |
| qwen3-vl-4b       | Qwen/Qwen3-VL-4B-Instruct              | ~4.8B  | main |
| gemma3-4b         | google/gemma-3-4b-it (gated)           | 4B     | main |
| qwen2.5-vl-7b     | Qwen/Qwen2.5-VL-7B-Instruct            | 7B     | main |
| internvl3-8b      | OpenGVLab/InternVL3-8B-hf              | 8B     | main |
| phi4-multimodal   | microsoft/Phi-4-multimodal-instruct    | 5.6B   | phi4 |

## The one gotcha: two Python environments
Phi-4-multimodal's code is pinned to `transformers==4.48.2`; Qwen3-VL needs `>=4.57`.
They cannot share an env, so:
- **main env**  -> the first 5 models
- **phi4 venv** -> Phi-4-multimodal only

## Storage
The six weight sets total ~60GB. Point `MODEL_ROOT` at a volume with **>=120GB free**
(weights + HF cache + datasets later).

---

## Setup

### 1) Token + paths
```bash
cp .env.example .env          # edit HF_TOKEN and MODEL_ROOT
set -a; source .env; set +a
```
Accept the Gemma 3 license once (while logged into HF): https://huggingface.co/google/gemma-3-4b-it

### 2) Main environment
```bash
# Don't reinstall torch if this already prints a CUDA-enabled build:
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
pip install -r requirements-main.txt
# If transformers 4.57 isn't on PyPI yet:
# pip install "git+https://github.com/huggingface/transformers.git"
```

### 3) Download weights (+ sample image)
```bash
python scripts/download_models.py
# subset: python scripts/download_models.py --models qwen3-vl-4b,smolvlm2-2.2b
```
Writes `<MODEL_ROOT>/manifest.json` with the pinned commit SHA + size per model.

### 4) Smoke test the 5 main-env models
```bash
python scripts/smoke_test.py
```
Prints PASS/FAIL + tok/s + peak VRAM per model and writes `smoke_results.json`.

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
model's handler in `scripts/smoke_test.py`. The newest models (Qwen3-VL, InternVL3-hf)
are the most likely to need a transformers-version or processor tweak.
