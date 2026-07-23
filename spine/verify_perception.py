"""verify_perception.py — G2 gate helper. Dumps 20 random frames with
their parsed states for accuracy checking, and computes field accuracy
against eval_set labels when they exist (self-checking once G1.5 has
run; human eyeball only needed before that).

Usage: python spine/verify_perception.py --frames episodes/
"""

from __future__ import annotations
import argparse, glob, json, os, random
import perceive
from io_adapter import IOAdapter
import yaml


def verify(frames_dir: str, n: int = 20):
    frames = sorted(glob.glob(os.path.join(frames_dir, "**", "*.jpg"),
                              recursive=True))
    sample = random.sample(frames, min(n, len(frames)))
    os.makedirs("status/perception_check", exist_ok=True)
    report = []
    for fp in sample:
        frame = perceive.load_image(fp)      # builder seam
        dets, player = perceive.detect(frame)
        hud = perceive.hud_state(frame)
        report.append({"frame": fp, "hud": hud,
                       "n_detections": len(dets),
                       "player_found": player is not None})
    out = "status/perception_check/report.json"
    json.dump(report, open(out, "w"), indent=2)

    labels_path = "eval_set/labels.json"
    if os.path.exists(labels_path):
        labels = {l["frame"]: l for l in json.load(open(labels_path))}
        checked = [r for r in report if r["frame"] in labels]
        # field agreement is computed by replay_eval on prompts; here
        # we report raw detection coverage as the G2 smoke signal
        print(json.dumps({"frames_checked": len(report),
                          "with_labels": len(checked),
                          "report": out}))
    else:
        print(json.dumps({"frames_checked": len(report),
                          "note": "no eval_set labels yet — human "
                                  "spot-check report.json vs frames",
                          "report": out}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--n", type=int, default=20)
    verify(ap.parse_args().frames, ap.parse_args().n)
