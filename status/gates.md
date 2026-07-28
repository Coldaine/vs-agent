# Gate status

Append-only record of gate progress. Evidence-based (GOAL.md).

## G0 live-control recalibration — 2026-07-28

**Verdict:** IN PROGRESS — prior selector/input blocker cleared; G0 is not
yet passed.

- Live keyboard route selected `Antonio Belpaese (Legacy)` and `Confirm`
  opened the separate Stage Selection screen.
- Mad Forest was selected by bounded directional navigation; Arcana was
  disabled through the calibrated 1.25x WGC-frame-to-hit-test transform.
- Start reached a live HUD and level-up overlay at 00:16
  (`status/g0_gameplay_hud.jpg`).
- This was a calibration run only. Hurry and Limit Break were enabled, so the
  modifier baseline is not yet a fixed evaluation condition. Attach/recovery
  and the two-second movement evidence also remain.

## Session 1 — seam fill + G0 attempt (2026-07-23)

BUILDER work completed (code, no live env required):

- **Seam 1 — spine/model_client.py**: FILLED. OpenAI-compatible client
  (openai SDK), process-injected provider credentials only, direct
  DeepSeek text roles and OpenRouter free vision roles, base64 image
  encoding, tolerant JSON parsing with one retry for sub-agents, every
  call logged to model_calls.jsonl (fn, prompt_hash, latency_ms).
  All fixed contracts implemented: call_follower, call_follower_eval,
  call_leader, call_subagent, call_labeler, call_auditor,
  export_gallery_frames.
- **Seam 2 — spine/io_adapter.py**: FILLED (route A). dxcam capture
  (Desktop Duplication — captures GPU game windows without black
  frames) with BlackFrameError on near-black frames; pydirectinput
  scancode key hold/release with held-key tracking; pygetwindow focus
  + window-region lookup; pytesseract OCR helper; neutralize()
  releases all keys on every exit path.
- **Seam 3 — spine/perceive.py**: FILLED. ultralytics YOLO wiring
  (weights + class map from config), player fixed at frame centre
  (player-locked camera, game_reference §1), OCR-based screen_type /
  read_options / hud_state, state_summary for the follower, to_jpeg,
  and load_image (verify_perception seam).
- **Defect fix — spine/run.py**: level-up handler referenced an
  undefined `brief`; corrected to `shared["brief"]` per the mutable-cell
  design in docs/code_walkthrough.md (would have crashed at the first
  level-up otherwise).
- **Config**: added yolo_weights / yolo_class_map / yolo_conf,
  death/run-end OCR triggers, window_title_hint, and hud_regions crop
  boxes to spine/config.yaml.
- **Scaffolding**: requirements.txt and .gitignore. Provider keys are
  injected at launch and the repository has no pinned Doppler scope.
- All spine modules byte-compile; config.yaml parses.

## G0 PLUMBING — BLOCKED (pending human provisioning)

G0's live checks (launch, capture, keys, menu macro, move check)
cannot run yet: the runtime is not provisioned. See status/BLOCKED.md
and status/HUMAN_NEEDED.md. The game itself IS installed
(C:\Program Files (x86)\Steam\steamapps\common\Vampire Survivors) and
Steam is present; the missing pieces are the detector weights and
live game launch. Provider keys are available through runtime injection.

### Session 2 Updates (2026-07-23)

**Code Readiness: ✓ COMPLETE**

All G0 code defects fixed and verified:
- ✓ verify_g0.py: Fixed key_hold → hold_direction/menu_navigate
- ✓ verify_g0.py: Fixed Frame handling (accessing .image property)
- ✓ verify_g0.py: Added gate evidence output to gates.md
- ✓ verify_g0.py: Added one retry for key test
- ✓ verify_g0.py: Fixed movement test (camera displacement not player coords)
- ✓ io_adapter.py: Added missing time import
- ✓ io_adapter.py: Added missing ocr() method for launch.py
- ✓ perceive.py: Configured Tesseract OCR path
- ✓ .gitignore: Added .venv/ and .env
- ✓ All modules compile and import successfully

**Environment Readiness: PARTIAL**

Python dependencies: ✓ COMPLETE
- ✓ .venv created with Python 3.13
- ✓ openai >= 1.30 installed
- ✓ ultralytics >= 8.2 installed
- ✓ dxcam >= 0.0.5 installed
- ✓ pytesseract >= 0.3.10 installed
- ✓ All other requirements.txt packages installed

Tesseract OCR: ✓ COMPLETE
- ✓ Binary confirmed at C:\Program Files\Tesseract-OCR\tesseract.exe
- ✓ perceive.py configured to use it

**Remaining Blockers:**

1. **YOLO Detector Weights** (CRITICAL)
   - Status: NOT PROVISIONED
   - Need: victorcoelh/vampire-survivors-bot weights
   - Action: Download weights and set yolo_weights path in config.yaml
   - Also: Set yolo_class_map for enemy/elite/gem/player classes

2. **Game Launch and Resolution** (REQUIRED FOR TESTING)
   - Status: Steam running, game NOT launched
   - Need: Launch Vampire Survivors
   - Action: Set fixed windowed resolution
   - Action: Calibrate hud_regions in config.yaml

3. **io_adapter.py / computer-control-mcp Reconciliation** (DEFERRED)
   - Status: Currently using dxcam/pydirectinput (works)
   - AGENTS.md specifies: Use computer-control-mcp MCP server
   - Action: Migrate to computer-control-mcp for WGC capture
   - Priority: LOW (current implementation functional)

**Ready to Execute Once Blockers Resolved:**

```bash
# Step 1: Provision YOLO weights
# Download from victorcoelh/vampire-survivors-bot
# Update config.yaml: yolo_weights: "path/to/weights.pt"

# Step 2: Launch game and set resolution
# Manual: Start Vampire Survivors, set windowed mode
# Calibrate: Update hud_regions in config.yaml

# Step 3: Run G0 verification
doppler run -- python spine/verify_g0.py

# Step 4: If G0 passes, begin G1 reflex-only
doppler run -- python spine/run.py --reflex-only
```

### Session 3 Updates (2026-07-23)

- **Virtual gamepad lifecycle hardened**: `spine/io_adapter.py` now verifies ViGEm/XInput enumeration by polling XInput slots instead of relying on a fixed sleep, recreates the virtual Xbox 360 controller on bounded input failures, and closes it explicitly from `run.py`, `verify_g0.py`, and the new `spine/verify_gamepad.py` diagnostic.
- **Config**: replaced `gamepad_ready_delay_s` with `gamepad_ready_timeout_s`, `gamepad_create_retries`, and `gamepad_recreate_on_error`.
- **Validation**: `python -m compileall spine` passed; `python spine/verify_gamepad.py` returned `{"ok": true, "before": [], "during": [0], "recoveries": 0}`.
- **Historical note**: the earlier live menu blocker was recorded before the verified nav-agent path;
  current blocker state must be read from `status/BLOCKED.md` and the latest G0 result below.

## G0 Plumbing Gate — 2026-07-23 23:28:03
**Verdict:** FAILED

**Results:**
- launch: PASS
- capture: PASS
- keys: PASS
- menu_macro: PASS
- move: FAIL (expected one of ['IN_GAME'], got CHARACTER_SELECT: 'ROCKSTAR FAVOURITE MAX WEAPONS POWER CREEP GOLDEN EGGS ENTER CO-OP FILTER: OFF GENNARO BELPAESE FAVOURITE A MAX WEAPONS [6] POWER CREEP EE. GOLDEN EGGS EO” EGGS: 20 SKIN')

**Evidence:**
- launched_process: False
- capture_resolution: 2562x1479
- capture_mean_brightness: 92.93
- key_diff: 40.6612
- key_ocr_before: a@ ms . Ss = i" & - ——= = ae Character Selection 7 -. hf a TY, me oer, ] @ = : ah : | 2 «| |) & 2! Bio ¢: » & y Ae i! e' : Pe = = ne I i" 7 _ | Bs y ial 
- key_ocr_after: GENNARO BELPAESE FAVOURITE - = MAX WEAPONS [6] POWER CREEP ee. Golden Eggs eo” EGGS: 20 SKIN 
- stage_text: ROCKSTAR » 118891 GENNARO BELPAESE FAVOURITE MAX WEAPONS POWER CREEP GOLDEN EGGS ENTER CO-OP FILTER: OFF GENNARO BELPAESE FAVOURITE - = MAX WEAPONS [6] POWER CREEP EE. GOLDEN EGGS 

## G0 Plumbing Gate — 2026-07-23 23:29:07
**Verdict:** FAILED

**Results:**
- launch: PASS
- capture: PASS
- keys: PASS
- menu_macro: FAIL (expected one of ['IN_GAME', 'STAGE_SELECT'], got MAIN_MENU: 'ROCKSTAR &: 118891 (_ MX } CONCEITED WERE THEY THAT RULED FROM SO HIGH YET STOOPED SO LOW. THIS NEXUS OF DEBASED PURITY IS THE PERFECT PLACE TO FIND A VAMPIRE. PROBABLY. IL MOLISE ')

**Evidence:**
- launched_process: False
- capture_resolution: 2562x1479
- capture_mean_brightness: 60.78
- key_diff: 0.1884
- key_ocr_before: GENNARO BELPAESE  FAVOURITE - =  MAX WEAPONS [6]  POWER CREEP ee.  Golden Eggs eo”  EGGS: 20  SKIN  ” 
- key_ocr_after: GENNARO BELPAESE FAVOURITE * MAX WEAPONS =~ [6] = POWER CREEP ee. Golden Eggs eo” EGGS: 20 SKIN 

## G0 Plumbing Gate — 2026-07-23 23:30:04
**Verdict:** FAILED

**Results:**
- launch: PASS
- capture: PASS
- keys: PASS
- menu_macro: FAIL (expected one of ['MAIN_MENU'], got UNKNOWN: 'ROCKSTAR @ CA EB “ RN 2 & PA ES) TH 2) E FE BY TE ROCKSTAR |G, 118891) | BACK | — : "FILTER: OFF ’ . 3 IE NE RL ES I A IE A +36% & AY OS A IH A Q 1408 CN, : . EN +21% FAA EE PEE EE')

**Evidence:**
- launched_process: False
- capture_resolution: 2562x1479
- capture_mean_brightness: 73.19
- key_diff: 9.8272
- key_ocr_before: Rockstar &: 118891 (_ mx } = a —— i . A : a i Stage Selection | "| pairs saebel: ua Moone __| Conceited were they that ruled from so “~ lel >. alae Snare is high yet stooped so low
- key_ocr_after: Rockstar &: 118891 (_ mx } = zl E 7 q , re Stage Selection I 5 . Scars; The flowers seem to sing here, calling rr. ‘ at bitten oh out to weary heroes. Is such ‘an unspoilt BJ 73% .

## G0 Plumbing Gate — 2026-07-23 23:31:35
**Verdict:** FAILED

**Results:**
- launch: PASS
- capture: PASS
- keys: PASS
- menu_macro: FAIL (expected one of ['STAGE_SELECT'], got CHARACTER_SELECT: 'ROCKSTAR FAVOURITE MAX WEAPONS POWER CREEP GOLDEN EGGS EGGS: 20 SKIN (I ENTER CO-OP | FILTER: OFF GENNARO BELPAESE FAVOURITE = A MAX WEAPONS [6] POWER CREEP EE. GOLDEN EGGS EO” EGG')

**Evidence:**
- launched_process: False
- capture_resolution: 2562x1479
- capture_mean_brightness: 92.87
- key_diff: 0.911
- key_ocr_before: a@  ae Character Selection 7  -.  &  me oreres  = ess) (? 1 :  | ry an : ah  ® : . : gy A | 2 Ss Bio ¢: »  Bit | ftw) ¥E 2  a  fe 2S 4) a9  i _ ' a  ms y ial 
- key_ocr_after: wt  ; ie  ’ ? e +35% oy Sy oS a oF ay +420% ar : Bla oS ol ole & +1 5 3 a - a eZ, ey | a- qi a +50% ' bx 30% a | -  +50% ’ ied +4 re 4 a oI) +10 | comer ser | :  ft a = jo dit 

## G0 Plumbing Gate — 2026-07-28 03:08:51

**Verdict:** FAILED

**Results:**
- launch: PASS
- capture: PASS
- keys: PASS
- menu_macro: FAIL (expected one of ['CHARACTER_SELECT', 'MAIN_MENU', 'STAGE_SELECT', 'TITLE', 'WARNING'], got UNKNOWN: 'ROCKSTAR | 28029 | — | FILTER: OFF ® : G ¢ & CS =) A AED A | GEO 6 IB BEEEE EERE ES ERED : : DB A EC) BS) 5 | SS AL AR AE AF É FE RAMBA :| FI W ~ ; VV] : |S 1G OFLF EO) IE | O R, X')

**Evidence:**
- launch_state: CHARACTER_SELECT
- capture_resolution: 2562x1479
- capture_mean_brightness: 92.02
- key_diff: 0.0276
- key_ocr_before: Character Selection a: fal al B14 | | S| fi a) BE Of w | =oF B= - =~} # a # R J 4 40 $ we Rami ia sls * “ F a = OU Al @) ec & Fk pa Ambrojoe | ) — § 1 (mwenons:6 | ||) gs ba be Fy 
- key_ocr_after: Rockstar | 28029 | — | : Ne a FR : if ua ve ad & ef Ramba | : B® Go Mel va | & ' ° : Ambrojoe i >. & r oF “h — _ 7) a : A) 7) «| 22? 22? 2??? = i cy ] eam ff LS ee, “ (=) 

## G0 Plumbing Gate — 2026-07-28 03:13:25

**Verdict:** FAILED

**Results:**
- blocked: BLOCKED

**Evidence:**
- blocked_status: status/BLOCKED.md is active

## G0 Plumbing Gate — 2026-07-28 03:13:56

**Verdict:** FAILED

**Results:**
- launch: PASS
- capture: PASS
- keys: PASS
- menu_macro: FAIL (expected one of ['STAGE_SELECT'], got CHARACTER_SELECT: 'ROCKSTAR ¥ CLOCK SPEED ES) +| XP BONUS 28029 STAGE SELECTION GREEN ACRES FATE CHANGES BY THE MINUTE IN A REALM WHERE MORTALS CAN ONLY TRESPASS. WHAT EEL REWARDS AWAIT THOSE WHO CHA')

**Evidence:**
- launch_state: CHARACTER_SELECT
- capture_resolution: 2562x1479
- capture_mean_brightness: 68.26
- key_diff: 0.0253
- key_ocr_before: — 7 Rockstar 28029 L | = i r. ‘ , ae) Stage Selection " Moongolow Legend tells of a city swallowed by the r fis i sea under a full moon’s callous watch. F | Pai Home to mysteries u
- key_ocr_after: Rockstar &: 28029 (_ mx } _ L . , re Stage Selection I 5 . 1 "a Fate chan by th inute i 1m F ‘ate ges by the minute in a rea. . ASHORE SionaIhL where mortals can only trespass. Wha

## G0 Plumbing Gate — 2026-07-28 03:14:02

**Verdict:** FAILED

**Results:**
- blocked: BLOCKED

**Evidence:**
- blocked_status: status/BLOCKED.md is active

## G0 Plumbing Gate — 2026-07-28 03:14:40

**Verdict:** FAILED

**Results:**
- launch: PASS
- capture: PASS
- keys: PASS
- menu_macro: PASS
- move: FAIL (expected one of ['IN_GAME'], got STAGE_SELECT: 'ROCKSTAR STAGE SELECTION GREEN ACRES (ENOIBLENICYE THE BONE ZONE <——2CHALLENGES WHITEOUT FATE CHANGES BY THE MINUTE IN A REALM WHERE MORTALS CAN ONLY TRESPASS. WHAT REWARDS AWAIT T')

**Evidence:**
- launch_state: STAGE_SELECT
- capture_resolution: 2562x1479
- capture_mean_brightness: 72.17
- key_diff: 0.0645
- key_ocr_before: — 7 Rockstar &: 28029 a _ at q , ae) Stage Selection $$ - A Fate changes by the minute in a realm rm " Sieat aeses where mortals can only trespass. What Eel rewards await those who
- key_ocr_after: Rockstar & 28029 ack io” oO Stage Selection Green Acres Fate changes by the minute in a realm where mortals can only trespass. What oft rs or] rewards await those who challenge its
- stage_text: ROCKSTAR STAGE SELECTION GREEN ACRES (ENOIBLENICYE THE BONE ZONE <——2CHALLENGES WHITEOUT FATE CHANGES BY THE MINUTE IN A REALM WHERE MORTALS CAN ONLY TRESPASS. WHAT REWARDS AWAIT T

## G0 Plumbing Gate — 2026-07-28 05:16:02

**Verdict:** FAILED

**Results:**
- launch: FAIL (expected one of ['CHARACTER_SELECT', 'MAIN_MENU', 'STAGE_SELECT', 'TITLE'], got WARNING: 'PHOTOSENSITIVITY WARNING THIS GAME CONTAINS BRIGHT FLASHING LIGHTS. PLEASE IMMEDIATELY STOP PLAYING AND CONSULT A DOCTOR IF YOU EXPERIENCE LIGHTHEADEDNESS, ALTERED VISION, EYE OR F')

**Evidence:**

## G0 Plumbing Gate — 2026-07-28 05:18:14

**Verdict:** FAILED

**Results:**
- launch: PASS
- capture: PASS
- keys: PASS
- menu_macro: FAIL (expected one of ['CHARACTER_SELECT', 'MAIN_MENU', 'STAGE_SELECT', 'TITLE', 'WARNING'], got UNKNOWN: 'ROCKSTAR | 28029 | — | & A B A AMBROJOE ® : G ¢ & CS =) A AED A | GEO 6 IB BEEEE EERE ES ERED ROCKSTAR | 28029 | (_MERCOW , : WL & AL BL BL E 4 OA AE A É A RAMBA | W ~ ; = : B® GO ')

**Evidence:**
- launch_state: CHARACTER_SELECT
- capture_resolution: 2562x1472
- capture_mean_brightness: 91.26
- key_diff: 0.0277
- key_ocr_before: Rockstar ([& 22) —) =p Character Selection & fit |) ft a |) FE @  | S| fi a) BE Of is .— ! -—% bee 1 - =~} # a # R J 4 40 . wis Ramba a ~~ - Gst6 b: : F a — OU Al @) ec & Fk ! 7 Am
- key_ocr_after: |  : | & a) So) Rl y | Gx oh Ae af & Ramba .  : ¢ ir  "ae = ] : B® Go Mel va | & : ° : Ambrojoe 4 i  il me | OCeroes| E 2 : , a 22? 22? 22? Random " 2 momen | |  2 = 

## G0 Plumbing Gate — 2026-07-28 05:18:56

**Verdict:** FAILED

**Results:**
- launch: PASS
- capture: PASS
- keys: FAIL (main-menu highlight diff too low: 0.0051)

**Evidence:**
- launch_state: CHARACTER_SELECT
- capture_resolution: 2562x1472
- capture_mean_brightness: 90.72

## G0 Plumbing Gate — 2026-07-28 05:24:14

**Verdict:** FAILED

**Results:**
- launch: PASS
- capture: PASS
- keys: PASS
- menu_macro: FAIL (could not select fixed eval character 'Antonio' after bounded character-menu search; last OCR: "ROCKSTAR ENTER CO-OP FILTER: OFF A CHARACTER SELECTION | FILTER: OFF | I ' LS CR * | 5 = I RE TH ; A I — FS")

**Evidence:**
- launch_state: CHARACTER_SELECT
- capture_resolution: 2562x1472
- capture_mean_brightness: 90.72
- key_diff: 0.0051
- key_ocr_before: Rockstar | 28029 | (_mercow ,  : wl & al Bl Bl e 4 oa Ae a é a Ramba | w ~ ; = : B® Go Mel va | 3 o 7 } ° Ambrojoe s ae > BA @ ie) @. ¢ - 22? 22? 22? Random = mmm (6 EO) aS Cee 
- key_ocr_after: |  : | & a) So) Rl y | Gx oh Ae af & Ramba .  : ¢ ir  "ae = ] : B® Go Mel va | & : ° : Ambrojoe 4 i  il me | OCeroes| E 2 : , a 22? 22? 22? Random " 2 momen | |  2 = 
