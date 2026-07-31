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


def _dominant_octant(counts: list[int]) -> str | None:
    if not counts or max(counts) <= 0:
        return None
    return perceive.reflex.OCTANT_ORDER[counts.index(max(counts))]


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
        labels_list = json.load(open(labels_path))
        labels = {l["frame"]: l for l in labels_list}
        
        # Labels contain dominant octants while state_summary contains vectors.
        field_matches = {"threat": 0, "gem": 0, "level_up": 0}
        total_checks = 0
        
        for fp in labels:
            if not os.path.exists(fp):
                continue
            frame = perceive.load_image(fp)
            summary = perceive.state_summary(frame)
            gt = labels[fp]
            threat = _dominant_octant(summary["threats_by_octant"])
            gem = _dominant_octant(summary["gems_by_octant"])
            screen = perceive.screen_type(frame, perceive._cfg())
            field_matches["threat"] += threat == gt.get("threat_octant")
            field_matches["gem"] += gem == gt.get("gem_octant")
            field_matches["level_up"] += ((screen == "LEVEL_UP")
                                           == bool(gt.get("is_level_up")))
            total_checks += 1

        field_accuracy = {
            name: round(matches / total_checks, 3) if total_checks else 0.0
            for name, matches in field_matches.items()
        }
        accuracy = round(sum(field_accuracy.values()) / len(field_accuracy), 3)
        print(json.dumps({
            "frames_checked": len(report),
            "eval_total": total_checks,
            "field_accuracy": field_accuracy,
            "accuracy": accuracy,
            "g2_passed": accuracy >= 0.9,
            "report": out
        }))
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
