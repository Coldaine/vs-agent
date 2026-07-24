"""perceive.py — perception seam. The builder implements these against
the forked YOLOv8 weights (victorcoelh/vampire-survivors-bot) and the
io adapter's OCR. Contracts are fixed; implementations are the seam.

External assets (provisioning, see status/HUMAN_NEEDED.md):
  - cfg['yolo_weights']: path to the forked detector weights.
  - cfg['yolo_class_map']: {model_class_name: enemy|elite|gem|player}.
  - Tesseract OCR on PATH (pytesseract) for HUD/level-up text.
Domain fact used here: the Vampire Survivors camera is player-locked,
so the player is always at frame centre (game_reference §1).
"""

from __future__ import annotations
import os
import re
import reflex

# Configure Tesseract path if on Windows
import sys
if sys.platform == "win32":
    import pytesseract
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

last_level = 0
last_kills = 0

_CFG = None
_MODEL = None


def _cfg() -> dict:
    global _CFG
    if _CFG is None:
        import yaml
        path = os.path.join(os.path.dirname(__file__), "config.yaml")
        _CFG = yaml.safe_load(open(path))
    return _CFG


def _model():
    global _MODEL
    if _MODEL is None:
        from ultralytics import YOLO
        weights = _cfg().get("yolo_weights")
        if weights and not os.path.isabs(weights):
            weights = os.path.join(os.path.dirname(__file__), "..", weights)
        if not weights or not os.path.exists(weights):
            raise FileNotFoundError(
                f"YOLO weights not found (cfg yolo_weights={weights!r}). "
                "Provision the forked detector — see status/HUMAN_NEEDED.md.")
        _MODEL = YOLO(weights)
    return _MODEL


def _center(frame) -> reflex.Detection:
    return reflex.Detection(frame.width / 2.0, frame.height / 2.0, "player")


def detect(frame) -> tuple[list[reflex.Detection], reflex.Detection]:
    """YOLO pass. Returns (all detections, player detection).
    Enemy/elite/gem/player classes per game_reference §6; elites get
    weight=3.0. Player is frame centre (player-locked camera)."""
    model = _model()
    class_map = {k.lower(): v for k, v in
                 (_cfg().get("yolo_class_map") or {}).items()}
    conf = _cfg().get("yolo_conf", 0.25)
    results = model.predict(frame.image, conf=conf, verbose=False)
    dets: list[reflex.Detection] = []
    names = getattr(model, "names", {})
    for r in results:
        boxes = getattr(r, "boxes", None)
        if boxes is None:
            continue
        for b in boxes:
            cls_id = int(b.cls[0])
            cls_name = str(names.get(cls_id, cls_id)).lower()
            kind = class_map.get(cls_name)
            if kind not in ("enemy", "elite", "gem"):
                continue
            x0, y0, x1, y1 = (float(v) for v in b.xyxy[0])
            cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            dets.append(reflex.Detection(
                cx, cy, kind, weight=3.0 if kind == "elite" else 1.0))
    return dets, _center(frame)


def _ocr(frame, region=None) -> str:
    import pytesseract
    img = frame.image
    if region:
        x0, y0, x1, y1 = region
        img = img[y0:y1, x0:x1]
    return pytesseract.image_to_string(img)


def screen_type(frame, cfg) -> str:
    """PLAY | LEVEL_UP | DEATH | RUN_END. OCR trigger
    (cfg['level_up_ocr_trigger']) or template match."""
    text = _ocr(frame).upper()
    if cfg.get("level_up_ocr_trigger", "LEVEL UP").upper() in text:
        return "LEVEL_UP"
    for token in cfg.get("death_ocr_triggers", ["YOU DIED", "GAME OVER"]):
        if token.upper() in text:
            return "DEATH"
    for token in cfg.get("run_end_ocr_triggers", ["REAPER", "TIME'S UP"]):
        if token.upper() in text:
            return "RUN_END"
    return "PLAY"


def read_options(frame) -> list[str]:
    """OCR the level-up option card names, top to bottom."""
    region = _cfg().get("hud_regions", {}).get("level_up_options")
    text = _ocr(frame, region)
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _read_int(frame, region) -> int | None:
    if not region:
        return None
    digits = re.sub(r"[^0-9]", "", _ocr(frame, region))
    return int(digits) if digits else None


def hud_state(frame) -> dict:
    """{"hp": int, "level": int, "timer": "MM:SS", "inventory": [...]}"""
        regions = _cfg().get("hud_regions", {})
    hp = _read_int(frame, regions.get("hp"))
    level = _read_int(frame, regions.get("level"))
    timer_txt = _ocr(frame, regions.get("timer")) if regions.get("timer") else ""
    m = re.search(r"(\d{1,2}:\d{2})", timer_txt)
    timer = m.group(1) if m else "00:00"
    if level is not None:
        last_level = level
    return {"hp": hp if hp is not None else 0,
            "level": level if level is not None else last_level,
            "timer": timer, "inventory": []}


def state_summary(frame) -> dict:
    """Compact JSON state for the follower prompt's {{STATE_JSON}}."""
    dets, player = detect(frame)
    hud = hud_state(frame)
    return {
        "hp": hud["hp"], "level": hud["level"], "timer": hud["timer"],
        "threats_by_octant": reflex.threats_by_octant(dets, player),
        "gems_by_octant": reflex.gems_by_octant(dets, player),
    }


def to_jpeg(frame) -> bytes:
    import cv2
    ok, buf = cv2.imencode(".jpg", frame.image)
    if not ok:
        raise RuntimeError("cv2 failed to encode frame")
    return buf.tobytes()


def load_image(path: str):
    """Load a saved frame into a Frame (verify_perception.py seam)."""
    import cv2
    from io_adapter import Frame
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"cannot read frame image: {path}")
    h, w = img.shape[:2]
    return Frame(image=img, width=w, height=h, t_capture=0.0)


def log_protocol_violation(raw_output: str):
    import json, time
    with open("protocol_violations.jsonl", "a") as f:
        f.write(json.dumps({"raw": raw_output, "t": time.time()}) + "\n")
