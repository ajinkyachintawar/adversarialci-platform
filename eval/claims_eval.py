"""
Claims Eval
===========
Phase 1 acceptance harness for the claims engine + citation gate: extract ->
gate for each (company, vertical) pair, report survival rate and dimension
coverage per company, aggregate, and PASS/FAIL against the acceptance bars
(survival >= 90%, dimension coverage 100%). JSON results go to eval/results/
(pattern: eval/retrieval_eval.py).

Run:  .venv/bin/python -m eval.claims_eval
      .venv/bin/python -m eval.claims_eval MongoDB database Pinecone database
"""

import sys
import os
import json
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from claims.extractor import extract_claims
from verticals import get_dimensions

DEFAULT_PAIRS = [("MongoDB", "database"), ("Pinecone", "database"), ("Weaviate", "database")]

SURVIVAL_BAR = 0.90
COVERAGE_BAR = 1.0


def _company_report(company: str, vertical: str) -> dict:
    print(f"\n🏢 {company} ({vertical})")
    extracted = extract_claims(company, vertical)
    extracted.pop("_rows", None)

    from claims.gate import gate_claims
    gated = gate_claims(company, extracted["claims"])

    dims_total = get_dimensions(vertical)
    dims_covered = {c["dimension"] for c in gated["claims"]}
    coverage = round(len(dims_covered) / len(dims_total), 3) if dims_total else 0.0
    missing_dims = sorted(set(dims_total) - dims_covered)

    stances = [c["stance"] for c in gated["claims"]]
    strengths = [c["strength"] for c in gated["claims"]]
    stance_split = {
        "strength": stances.count("strength"),
        "weakness": stances.count("weakness"),
    }
    avg_strength = round(sum(strengths) / len(strengths), 2) if strengths else 0.0

    report = {
        "company": company,
        "vertical": vertical,
        "extraction_metrics": extracted["metrics"],
        "gate_metrics": gated["metrics"],
        "dimensions_total": len(dims_total),
        "dimensions_covered": len(dims_covered),
        "dimension_coverage": coverage,
        "missing_dimensions": missing_dims,
        "stance_split": stance_split,
        "avg_strength": avg_strength,
        "claims": gated["claims"],
    }

    survival_pct = round(gated["metrics"]["survival_rate"] * 100, 1)
    coverage_pct = round(coverage * 100, 1)
    print(f"  claims: {extracted['metrics']['claims_extracted']} extracted, "
          f"{len(gated['claims'])} survived ({survival_pct}%)")
    print(f"  dimension coverage: {len(dims_covered)}/{len(dims_total)} ({coverage_pct}%)"
          + (f" — missing: {missing_dims}" if missing_dims else ""))
    return report


def run(pairs: list[tuple]) -> dict:
    t0 = time.time()
    reports = [_company_report(company, vertical) for company, vertical in pairs]

    total_claims = sum(r["gate_metrics"]["claims_total"] for r in reports)
    total_survived = sum(len(r["claims"]) for r in reports)
    overall_survival = round(total_survived / total_claims, 3) if total_claims else 0.0

    total_dims = sum(r["dimensions_total"] for r in reports)
    covered_dims = sum(r["dimensions_covered"] for r in reports)
    overall_coverage = round(covered_dims / total_dims, 3) if total_dims else 0.0

    total_groq_calls = sum(r["extraction_metrics"]["groq_calls"] for r in reports)
    wall_seconds = round(time.time() - t0, 1)

    survival_pass = overall_survival >= SURVIVAL_BAR
    coverage_pass = overall_coverage >= COVERAGE_BAR
    overall_pass = survival_pass and coverage_pass

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "pairs": [f"{c}/{v}" for c, v in pairs],
        "companies": reports,
        "aggregate": {
            "claims_total": total_claims,
            "claims_survived": total_survived,
            "overall_survival_rate": overall_survival,
            "dimensions_total": total_dims,
            "dimensions_covered": covered_dims,
            "overall_dimension_coverage": overall_coverage,
            "total_groq_calls": total_groq_calls,
            "wall_seconds": wall_seconds,
        },
        "acceptance": {
            "survival_bar": SURVIVAL_BAR,
            "coverage_bar": COVERAGE_BAR,
            "survival_pass": survival_pass,
            "coverage_pass": coverage_pass,
            "overall_pass": overall_pass,
        },
    }

    os.makedirs("eval/results", exist_ok=True)
    path = f"eval/results/claims_eval_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 50)
    print(f"  overall survival: {round(overall_survival * 100, 1)}% "
          f"({'✅' if survival_pass else '❌'} bar {SURVIVAL_BAR * 100:.0f}%)")
    print(f"  overall dimension coverage: {round(overall_coverage * 100, 1)}% "
          f"({'✅' if coverage_pass else '❌'} bar {COVERAGE_BAR * 100:.0f}%)")
    print(f"  groq calls: {total_groq_calls} | wall time: {wall_seconds}s")
    print(f"  {'✅ PASS' if overall_pass else '❌ FAIL'}")
    print(f"  saved -> {path}")
    return summary


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        if len(args) % 2 != 0:
            print("Usage: -m eval.claims_eval [Company vertical ...]")
            sys.exit(1)
        pairs = [(args[i], args[i + 1]) for i in range(0, len(args), 2)]
    else:
        pairs = DEFAULT_PAIRS
    run(pairs)
