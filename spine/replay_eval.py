"""replay_eval.py — Loop P offline scoring. No game required.

Scores a follower-prompt variant against eval_set/ AND the failure
gallery. Promotion rule (GOAL.md): must beat the champion AND flip its
target gallery frames without regressing >2% of the rest.

Usage: python spine/replay_eval.py --prompt prompts/follower.md
"""

from __future__ import annotations
import argparse, json, os, time
import model_client


def load_eval_set(root: str) -> list[dict]:
    labels = json.load(open(os.path.join(root, "labels.json")))
    gallery_path = os.path.join(root, "gallery", "labels.json")
    gallery = json.load(open(gallery_path)) if os.path.exists(gallery_path) else []
    return [{"split": "base", **x} for x in labels] + \
           [{"split": "gallery", **x} for x in gallery]


def score_prompt(prompt_path: str) -> dict:
    prompt = open(prompt_path).read()
    rows = load_eval_set("eval_set")
    agree, field_ok, lat, per_row = 0, 0, [], []
    for row in rows:
        t0 = time.monotonic()
        out = model_client.call_follower_eval(prompt, row["frame"])
        lat.append((time.monotonic() - t0) * 1000)
        action_ok = out["action"] == row["correct_action"]
        fields_ok = all(out.get(k) == row[k] for k in
                        ("threat_octant", "gem_octant", "is_level_up")
                        if k in row)
        agree += action_ok
        field_ok += fields_ok
        per_row.append({"frame": row["frame"], "split": row["split"],
                        "ok": action_ok})
    n = len(rows)
    lat.sort()
    result = {
        "prompt": prompt_path,
        "direction_agreement": agree / n,
        "field_accuracy": field_ok / n,
        "latency_p50_ms": lat[len(lat) // 2],
        "latency_p95_ms": lat[int(len(lat) * .95)],
        "rows": per_row,
    }
    with open("loop_p_results.jsonl", "a") as f:
        f.write(json.dumps({k: v for k, v in result.items() if k != "rows"}) + "\n")
    return result


def regression_check(champion_rows: list[dict], variant_rows: list[dict]) -> float:
    """Fraction of previously-correct rows the variant breaks."""
    champ_ok = {r["frame"] for r in champion_rows if r["ok"]}
    broken = sum(1 for r in variant_rows
                 if r["frame"] in champ_ok and not r["ok"])
    return broken / max(len(champ_ok), 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--vs-champion", default=None,
                    help="path to champion loop_p result for regression check")
    args = ap.parse_args()
    res = score_prompt(args.prompt)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=2))

