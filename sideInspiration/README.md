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
| `vs_harness/` | Leader–follower harness (SAM/YOLO perception, movers, bakeoff, traces) |
| `configs/` | Harness YAML |
| `scripts/` | Entry scripts |
| `tests/` | Harness unit/sim tests |
| `docs/README_harness.md` | Full harness README from the cloud workspace |
| `docs/plans/vs_agent_harness_cloud.plan.md` | Cloud agent plan artifact |
| `pyproject.toml` / `requirements-harness.txt` | Optional install surface for this tree only |

Authority for the product remains `HANDOFF.md` / `GOAL.md` / `spine/`.
Do not treat this package as a second spine.
