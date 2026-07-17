"""
Retrieval Eval
==============
Scores ingest.retrieval against the golden set (eval/golden_retrieval.json).
Metrics: hit@1, hit@5, MRR. Run after any retrieval/chunking/embedding
change; JSON results go to eval/results/ so improvements are provable.

Run:  .venv/bin/python eval/retrieval_eval.py [label]
"""

import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingest.retrieval import retrieve

K = 5


def is_match(chunk: dict, entry: dict) -> bool:
    text = chunk.get("text", "").lower()
    url = chunk.get("source_url", "").lower()
    for s in entry.get("expect_any", []):
        if s.lower() in text:
            return True
    eu = entry.get("expect_url")
    return bool(eu and eu.lower() in url)


def run(label: str = "golden") -> dict:
    with open(os.path.join(os.path.dirname(__file__), "golden_retrieval.json")) as f:
        golden = json.load(f)["queries"]

    rows = []
    for entry in golden:
        results = retrieve(entry["query"], entry["company"], k=K)
        rank = next((i + 1 for i, r in enumerate(results) if is_match(r, entry)), None)
        rows.append({
            "query": entry["query"],
            "company": entry["company"],
            "rank": rank,
            "top_score": round(results[0]["score"], 3) if results else None,
        })
        mark = "✅" if rank == 1 else "🟡" if rank else "❌"
        print(f"  {mark} rank={rank or '-'}  [{entry['company']}] {entry['query']}")

    n = len(rows)
    hit1 = sum(1 for r in rows if r["rank"] == 1)
    hit5 = sum(1 for r in rows if r["rank"] is not None)
    mrr = sum(1 / r["rank"] for r in rows if r["rank"]) / n

    summary = {
        "label": label,
        "timestamp": datetime.utcnow().isoformat(),
        "k": K,
        "queries": n,
        "hit_at_1": f"{hit1}/{n} ({round(hit1 / n * 100)}%)",
        "hit_at_5": f"{hit5}/{n} ({round(hit5 / n * 100)}%)",
        "mrr": round(mrr, 3),
    }

    os.makedirs("eval/results", exist_ok=True)
    path = (f"eval/results/retrieval_eval_{label}_"
            f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w") as f:
        json.dump({**summary, "rows": rows}, f, indent=2)

    print(f"\n  hit@1 {summary['hit_at_1']} | hit@5 {summary['hit_at_5']} | "
          f"MRR {summary['mrr']}")
    print(f"  saved -> {path}")
    return summary


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "golden")
