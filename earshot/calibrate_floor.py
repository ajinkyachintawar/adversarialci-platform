"""
Calibrate SCORE_FLOOR
======================
Sweeps a vector-search score floor and recommends the lowest value with
zero false-abstains on known-positives (eval/golden_retrieval_v2.json,
scored via is_match from eval/retrieval_eval.py -- do not reimplement it).
Negatives are eval/golden_abstain.json (Task 1.1): questions the corpus
genuinely cannot answer. Read-only against retrieve(); writes a JSON
recommendation, never edits a source file. The constant it recommends is
committed by a human into earshot/answer.py.

Run:  .venv/bin/python -m earshot.calibrate_floor [label]
Out:  eval/results/floor_calibration_<label>_<ts>.json
"""

import sys
import os
import json
from datetime import datetime, UTC

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingest.retrieval import retrieve
from eval.retrieval_eval import is_match

FLOORS = [round(0.55 + 0.01 * i, 2) for i in range(41)]  # 0.55 -> 0.95


def _load(name):
    path = os.path.join(os.path.dirname(__file__), "..", "eval", name)
    with open(path) as f:
        return json.load(f)["queries"]


def score_positives(entries):
    """For each golden_retrieval_v2 entry: top score, and score of the first
    matching chunk (None if no retrieved chunk actually matches)."""
    rows = []
    for entry in entries:
        results = retrieve(entry["query"], entry["company"], k=6)
        top = results[0]["score"] if results else None
        match_score = next((r["score"] for r in results if is_match(r, entry)), None)
        rows.append({"query": entry["query"], "company": entry["company"],
                      "top_score": top, "match_score": match_score})
    return rows


def score_negatives(entries):
    rows = []
    for entry in entries:
        results = retrieve(entry["query"], entry["company"], k=6)
        top = results[0]["score"] if results else None
        rows.append({"query": entry["query"], "company": entry["company"], "top_score": top})
    return rows


def sweep(pos_rows, neg_rows):
    table = []
    for floor in FLOORS:
        # False abstain: corpus DOES contain the answer (a matching chunk
        # exists) but the top score falls below the floor and we'd abstain.
        false_abstains = sum(
            1 for r in pos_rows
            if r["match_score"] is not None and (r["top_score"] or 0) < floor
        )
        # False answer: corpus should abstain (negative) but top score clears
        # the floor so we'd answer anyway.
        false_answers = sum(
            1 for r in neg_rows if (r["top_score"] or 0) >= floor
        )
        n_pos = len(pos_rows)
        n_neg = len(neg_rows)
        table.append({
            "floor": floor,
            "false_abstain_rate": round(false_abstains / n_pos, 3),
            "false_abstain_count": f"{false_abstains}/{n_pos}",
            "false_answer_rate": round(false_answers / n_neg, 3),
            "false_answer_count": f"{false_answers}/{n_neg}",
        })
    return table


def choose_floor(table):
    """Lowest floor with false-abstain rate == 0 on positives."""
    for row in table:
        if row["false_abstain_rate"] == 0.0:
            return row
    return None


def run(label: str = "baseline") -> dict:
    positives = _load("golden_retrieval_v2.json")
    negatives = _load("golden_abstain.json")

    print(f"  scoring {len(positives)} positives (golden_retrieval_v2.json)...")
    pos_rows = score_positives(positives)
    print(f"  scoring {len(negatives)} negatives (golden_abstain.json)...")
    neg_rows = score_negatives(negatives)

    table = sweep(pos_rows, neg_rows)
    chosen = choose_floor(table)

    print(f"\n  {'floor':>6} {'false-abstain':>16} {'false-answer':>16}")
    for row in table:
        marker = "  <-- chosen" if chosen and row["floor"] == chosen["floor"] else ""
        print(f"  {row['floor']:>6} {row['false_abstain_count']:>16} "
              f"{row['false_answer_count']:>16}{marker}")

    print()
    if chosen:
        print(f"  RECOMMENDED SCORE_FLOOR = {chosen['floor']} "
              f"(false-abstain 0/{len(pos_rows)}, "
              f"false-answer {chosen['false_answer_count']} = "
              f"{chosen['false_answer_rate']*100:.0f}%)")
        if chosen["false_answer_rate"] > 0.3:
            print("  WARNING: no floor cleanly separates positives from negatives -- "
                  "the false-answer rate at the only zero-false-abstain floor is high. "
                  "Vector scores do not separate 'corpus covers this' from 'corpus "
                  "doesn't cover this' well on this corpus/embedder. This is a real "
                  "architectural finding for abstention design, not a script bug.")
    else:
        print("  RECOMMENDED SCORE_FLOOR = none found -- no floor in [0.55, 0.95] "
              "achieves zero false-abstains on the positives. Report this as a "
              "critical finding: scores do not separate positives from negatives.")

    result = {
        "label": label,
        "timestamp": datetime.now(UTC).isoformat(),
        "n_positives": len(pos_rows),
        "n_negatives": len(neg_rows),
        "sweep": table,
        "recommended_floor": chosen["floor"] if chosen else None,
        "recommended_false_answer_rate": chosen["false_answer_rate"] if chosen else None,
        "positive_rows": pos_rows,
        "negative_rows": neg_rows,
    }

    os.makedirs("eval/results", exist_ok=True)
    path = (f"eval/results/floor_calibration_{label}_"
            f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n  saved -> {path}")
    return result


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "baseline")
