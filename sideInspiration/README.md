# Side inspiration (cloud rescue)

Work rescued from the orphaned Cursor cloud agent
[Vampire survivor AI harness](https://cursor.com/agents/bc-019f8ec1-f963-71e7-88f1-321413d4c567)
(`bc-019f8ec1-f963-71e7-88f1-321413d4c567`).

This folder is **not** part of the live `spine/` gate path. Keep it here as
reference tooling. We will review it and adopt pieces into the main system
where they earn their keep.

`vs_harness` is **simulation-only** in this tree (`loop.mode` must be `sim`).
Live keyboard/window control is intentionally disabled so it cannot bypass
`spine/controller.py` / computer-control-mcp.

| Path | Contents |
|---|---|
| `vs_harness/` | planner–pilot harness (SAM/YOLO perception, movers, bakeoff, traces) |
| `sam3_service/` | **Recommended** GPU Docker sidecar for SAM 3 image PCS (`:8090`) |
| `configs/` | Harness YAML |
| `scripts/` | Entry scripts |
| `tests/` | Harness unit/sim tests |
| `docs/README_harness.md` | Full harness README from the cloud workspace |
| `docs/plans/vs_agent_harness_cloud.plan.md` | Cloud agent plan artifact |
| `pyproject.toml` / `requirements-harness.txt` | Optional install surface for this tree only |

### SAM 3 (Docker)

Don’t install torch/sam3 into the spine venv. From `sam3_service/`:

```bash
# HF access accepted for facebook/sam3; then:
docker compose up --build -d
```

Set `perception.backend: sam3` and `sam3_url: http://127.0.0.1:8090`.
See [`sam3_service/README.md`](sam3_service/README.md). Image PCS, not video multiplex.

Authority for the product remains `HANDOFF.md` / `GOAL.md` / `spine/`.
Do not treat this package as a second spine.

