"""
Head Evidence Gathering
=======================
Single entry point every head calls first: extract -> gate per company.
Claims never bypass claims.gate before reaching a head prompt.

Run:  .venv/bin/python -m heads.evidence MongoDB Pinecone database
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from claims.extractor import extract_claims
from claims.gate import gate_claims


def gather(companies: list[str], vertical: str) -> dict:
    """Returns {"claims_by_company": {company: [gated claims]}, "metrics": {...}}."""
    claims_by_company = {}
    metrics_by_company = {}

    for company in companies:
        extracted = extract_claims(company, vertical)
        extracted.pop("_rows", None)
        gated = gate_claims(company, extracted["claims"])
        claims_by_company[company] = gated["claims"]
        metrics_by_company[company] = {
            "extraction": extracted["metrics"],
            "gate": gated["metrics"],
        }
        print(f"  🏢 {company}: {extracted['metrics']['claims_extracted']} extracted -> "
              f"{len(gated['claims'])} gated "
              f"({round(gated['metrics']['survival_rate'] * 100, 1)}% survival)")

    total_claims = sum(len(c) for c in claims_by_company.values())
    return {
        "claims_by_company": claims_by_company,
        "metrics": {
            "companies": len(companies),
            "total_gated_claims": total_claims,
            "by_company": metrics_by_company,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: -m heads.evidence <Company> [Company2 ...] <vertical>")
        sys.exit(1)
    *companies, vertical = sys.argv[1:]
    result = gather(companies, vertical)
    print(f"\n📊 total gated claims: {result['metrics']['total_gated_claims']}")
