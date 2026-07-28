# G0 live-control follow-up

## Status

In progress. Live menu and stage launch are proven; attach/recovery and the
movement verification remain before G0 can pass.

## Verified route (2026-07-28)

1. The initial combined screen is **Character Selection**, not the final
   stage screen. Its right-side checklist is not proof that a stage is
   selected.
2. Keyboard selection is deterministic from the observed Zi'Assunta state:
   `Up, Up, Up, Up, Left, Left` selected Antonio. The detail panel and focus
   brackets read `Antonio Belpaese (Legacy)`.
3. `Confirm` advances to a separate **Stage Selection** screen; it does not
   start gameplay.
4. From the observed Boss Rash selection, nine `Up` inputs selected Mad
   Forest. The Stage 1 card focus brackets are the selection proof.
5. Arcana must be inspected on the Stage Selection modifier row. It was
   initially enabled and was disabled successfully. Hurry and Limit Break
   remained enabled. Therefore the launched run was a **calibration run**,
   not a scoreable fixed-condition evaluation: “default modifiers” must be
   expanded into six explicit boolean states before G1 evaluation begins.
6. The WGC frame is 1.25x the Windows input hit-test surface. A click at
   frame `(950, 1090)` reached Gallo Tower; the corrected input coordinate
   `(1188, 1364)` toggled Arcana. Treat this as fixed-resolution calibration,
   not a portable constant.
7. Focus traversal on Stage Selection is explicit: confirm on the selected
   stage focuses modifiers; right focuses Start; confirm starts. A verified
   gameplay HUD appeared at 00:16.

Evidence frames live in `status/`:

- `keyboard_left_to_antonio.jpg`
- `g0_ready_mad_forest_antonio_arcanas_off.jpg`
- `g0_gameplay_hud.jpg`

## Next implementation slice

1. Add an attach mode to `spine/run.py` (or a narrow runtime helper): detect
   `IN_GAME` / `LEVEL_UP`, neutralize, and skip `launch.to_stage_select()` and
   `launch.start_run()`.
2. Route an attached level-up through the existing planner/option selector,
   then run the controller's reflex-only loop for the G1 movement check.
3. Save before/after evidence for a two-second movement command and append a
   G0 result to `status/gates.md`. Do not mark G0 passed until that check and
   the attach path have passed.
4. Replace hard-coded click use with an explicit capture-to-input transform
   plus a calibration assertion; fail closed when the fixed display contract
   changes.
5. Add an explicit six-modifier eval baseline to `spine/config.yaml`, enforce
   it on Stage Selection, and record it in each episode's metadata.
