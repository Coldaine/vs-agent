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
3. Doppler `ai-automation` / `dev` has `HUGGINGFACE_TOKEN` (injected by `sam3.ps1`)

## Durable control script

Use [`sam3.ps1`](sam3.ps1) for day-to-day up/down (no secrets printed):

```powershell
cd sideInspiration/sam3_service
.\sam3.ps1 up        # build if needed, start detached (Doppler → HF_TOKEN)
.\sam3.ps1 warmup    # load facebook/sam3 into GPU (first time downloads weights)
.\sam3.ps1 status    # compose ps + /health
.\sam3.ps1 logs      # follow logs
.\sam3.ps1 down      # stop container (keeps HF weight volume)
.\sam3.ps1 restart
.\sam3.ps1 rebuild   # --no-cache image rebuild
```

`run_sam3.ps1` remains as a thin alias for `.\sam3.ps1 up`.

Do not put tokens in committed `.env` files — use Doppler.

Harness config: `configs/sam3_docker.yaml` (`perception.backend: sam3`).

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
