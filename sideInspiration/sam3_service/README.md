# SAM 3 Docker sidecar (image PCS)

GPU microservice for [facebookresearch/sam3](https://github.com/facebookresearch/sam3) (11.1k stars).
Keeps torch / CUDA / gated HF weights out of the harness and spine venvs.

## Why Docker (and not “SAM 3.1 multiplex” in-process)

- Local `pip install sam3` + CUDA 12.8 + HF gated download is brittle on the host.
- Meta’s **SAM 3.1 Object Multiplex** is the **video tracker** API.
- Vampire Survivors threat fields want **per-frame image concept masks** →
  `build_sam3_image_model()` + `Sam3Processor.set_text_prompt` (SAM 3 image PCS).
- This container runs that image path and exposes HTTP.

Context7 checked: `/facebookresearch/sam3` — image PCS example + `build_sam3_image_model` hardcodes `facebook/sam3` checkpoints; 3.1 multiplex is `build_sam3_predictor(version="sam3.1")` (video).

## Prerequisites

1. Docker Desktop with NVIDIA runtime (`docker info` should list `nvidia`).
2. Accept model access: https://huggingface.co/facebook/sam3
3. Export a token: `HF_TOKEN=hf_...`

## Run

```bash
cd sideInspiration/sam3_service
# PowerShell: $env:HF_TOKEN = "hf_..."
docker compose up --build -d
curl http://127.0.0.1:8090/health
curl -X POST http://127.0.0.1:8090/v1/warmup
```

First warmup downloads weights into the `sam3-hf-cache` volume.

## API

- `GET /health` — cuda / token / model_loaded
- `POST /v1/warmup` — force model load
- `POST /v1/segment` — `{ image_b64, prompts[], score_thresh, downsample_max_side }`
  → `{ union_png_b64, per_prompt_png_b64, prompt_counts, inference_ms }`

## Harness

In `configs/default.yaml`:

```yaml
perception:
  backend: sam3
  sam3_url: "http://127.0.0.1:8090"
```

If the sidecar is down, `build_perception` falls back to mock.
