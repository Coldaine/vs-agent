# G0 live-control follow-up

## Status

In progress. Vision-led menu entry is implemented; live proof must wait for an
**unattended fullscreen** session. Interactive desktop use caused capture size
flicker and broke the hit-test contract.

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

1. [x] Attach mode + vision-led entry: `prepare()` launches/focuses only;
   LangGraph leader navigates menus via `menu_action`. OCR is a hint, not
   the navigator. `--entry-only` stops at the in-game HUD.
2. Route an attached level-up through the existing planner/option selector,
   then run the controller's reflex-only loop for the G1 movement check.
3. [x] Two-second movement evidence path in `verify_g0.py` after vision entry.
   Still need a live `status/gates.md` PASS append.
4. [x] `capture_transform.frame_to_hit_test` in `IOAdapter.click_frame`.
5. [x] Six-modifier baseline required by prepare/attach. Live UI proof that
   all six match Stage Selection checkboxes remains open.
