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
        labels_list = json.load(open(labels_path))
        labels = {l["frame"]: l for l in labels_list}
        
        # Calculate field accuracy (>90% required for G2)
        agreements = 0
        total_checks = 0
        
        for fp in labels:
            if not os.path.exists(fp): continue
            frame = perceive.load_image(fp)
            # For G2, we check state_summary fields vs ground truth
            # which includes threat_octant, gem_octant, is_level_up
            summary = perceive.state_summary(frame)
            gt = labels[fp]
            
            # Simple field match (case-insensitive for directions)
            threat_match = str(summary.get("threat_octant")).lower() == str(gt.get("threat_octant")).lower()
            gem_match = str(summary.get("gem_octant")).lower() == str(gt.get("gem_octant")).lower()
            lvl_match = summary.get("is_level_up") == gt.get("is_level_up")
            
            if threat_match and gem_match and lvl_match:
                agreements += 1
            total_checks += 1
            
        accuracy = (agreements / total_checks) if total_checks > 0 else 0
        print(json.dumps({
            "frames_checked": len(report),
            "eval_total": total_checks,
            "eval_agreements": agreements,
            "accuracy": round(accuracy, 3),
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
