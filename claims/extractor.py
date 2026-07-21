"""
Claims Extractor
================
Per company x dimension: retrieve evidence chunks (ingest.retrieval.retrieve),
then ask llama-3.1-8b-instant to extract structured, cited claims from ONLY
those chunks. Output is unverified — claims.gate does the deterministic
citation check afterward.

Groq free tier is ~6K TPM: calls are sequential, time.sleep(2) between them;
on 429 the key rotates across GROQ_API_KEYS (separate accounts = separate TPM).

Run:  .venv/bin/python -m claims.extractor MongoDB database
"""

import sys
import os
import re
import json
import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from groq import Groq

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingest.retrieval import retrieve
from verticals import get_dimensions

from config import GROQ_API_KEYS

EXTRACT_MODEL = "llama-3.1-8b-instant"
# Groq free tier: 6K tokens max per request (input + max_tokens). Table-heavy
# markdown tokenizes at ~2.5 chars/token, so 8K chars ≈ 3.2K tokens; with
# instructions + 2048 output that stays under the cap with margin.
EVIDENCE_CHAR_BUDGET = 8_000
MAX_OUTPUT_TOKENS = 2048

_key_idx = 0  # rotates across GROQ_API_KEYS on 429 (separate accounts = separate TPM)

# One natural-language retrieval query template per dimension name, union
# across database/cloud/crm (llm vertical has no dimensions registered yet).
DIMENSION_QUERY = {
    "cost": "{company} pricing plans cost per month free tier",
    "performance": "{company} performance benchmarks latency throughput",
    "scalability": "{company} scalability horizontal scaling sharding clusters at scale",
    "simplicity": "{company} ease of setup developer experience learning curve",
    "lock_in_risk": "{company} vendor lock-in proprietary format data portability migration",
    "vector_capability": "{company} vector search embeddings similarity search AI features",
    "ecosystem": "{company} integrations ecosystem community plugins drivers SDKs",
    "compliance": "{company} compliance certifications SOC2 HIPAA GDPR security audits",
    "global_reach": "{company} regions availability zones global data centers multi-region",
    "support": "{company} customer support SLA response time enterprise support plans",
    "ease_of_use": "{company} ease of use UI usability onboarding for end users",
    "customization": "{company} customization custom fields workflows configurability",
    "integrations": "{company} integrations third party apps marketplace API connectors",
    "reporting": "{company} reporting analytics dashboards insights",
}


class Claim(BaseModel):
    dimension: str
    claim: str
    stance: Literal["strength", "weakness"]
    evidence_ids: list[str] = Field(min_length=1)
    strength: int = Field(ge=1, le=5)


def _call_groq(messages: list) -> str | None:
    """On 429: rotate to the next key (separate account = fresh TPM); once all
    keys are exhausted, wait 20s and go around once more. None on hard error."""
    global _key_idx
    for attempt in range(2 * len(GROQ_API_KEYS)):
        try:
            client = Groq(api_key=GROQ_API_KEYS[_key_idx])
            response = client.chat.completions.create(
                model=EXTRACT_MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=MAX_OUTPUT_TOKENS,
            )
            return response.choices[0].message.content
        except Exception as e:
            if "429" not in str(e):
                print(f"  ⚠️  Groq error: {e}")
                return None
            _key_idx = (_key_idx + 1) % len(GROQ_API_KEYS)
            if _key_idx == 0 and attempt < 2 * len(GROQ_API_KEYS) - 1:
                print("  ⏳ Groq 429 on all keys — waiting 20s")
                time.sleep(20)
            elif len(GROQ_API_KEYS) > 1:
                print(f"  🔑 Groq 429 — rotating to key #{_key_idx + 1}")
    print("  ⚠️  Groq: rate limited on every key, giving up this call")
    return None


def _parse_claims(raw: str, dim: str, id_map: dict[str, str]) -> tuple[list[Claim], int]:
    """Parse + validate a JSON array of claims. Returns (claims, invalid_count).
    The model cites short labels ([E1]...); id_map resolves them to real chunk
    hashes here. Invented labels are stripped; a claim left with none is
    invalid. Raises ValueError if the whole array is malformed (caller
    re-asks once)."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        # output truncated at max_tokens mid-item: salvage the complete items
        cut = text.rfind("},")
        if cut == -1:
            raise
        items = json.loads(text[:cut + 1] + "]")
    if not isinstance(items, list):
        raise ValueError("expected a JSON array")

    claims, invalid = [], 0
    for item in items:
        if isinstance(item, dict):
            item["evidence_ids"] = [id_map[i.strip("[]")]
                                    for i in item.get("evidence_ids") or []
                                    if isinstance(i, str) and i.strip("[]") in id_map]
        try:
            c = Claim(**item)
            c.dimension = dim  # force — model sometimes drifts
            claims.append(c)
        except (ValidationError, TypeError):
            invalid += 1
    return claims, invalid


# zero-width chars, bidi controls, BOM — invisible junk from scraped pages
_INVISIBLE = re.compile("[\\u200b-\\u200f\\u202a-\\u202e\\u2060\\ufeff]")


def _build_prompt(company: str, dim: str, chunks: list[dict]) -> list[dict]:
    # equal share of the char budget per chunk so one long page can't 413 the
    # call; invisible unicode stripped — it sends the 8B into repetition loops
    per_chunk = EVIDENCE_CHAR_BUDGET // max(len(chunks), 1)
    blocks = "\n\n".join(
        f"[E{i + 1}] {_INVISIBLE.sub('', c['text'][:per_chunk])}"
        for i, c in enumerate(chunks))
    system = (
        "You are a competitive-intelligence claim extractor. You extract only "
        "what the evidence explicitly supports — never prior knowledge."
    )
    user = f"""COMPANY: {company}
DIMENSION: {dim}

EVIDENCE BLOCKS:
{blocks}

Extract 1-4 claims about {company} on dimension "{dim}" ONLY from the evidence
blocks above. Nothing from prior knowledge.
- Each claim must cite evidence_ids: the block labels (like "E1", "E3") it came
  from. Only the labels E1-E{len(chunks)} are valid.
- stance: "strength" if it favors {company}, "weakness" if it hurts {company}.
- strength: 1-5, how decisive the claim is in a buying decision.
Return ONLY a JSON array, no markdown fences, no prose:
[{{"dimension": "{dim}", "claim": "...", "stance": "strength", "evidence_ids": ["E1"], "strength": 3}}]"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def extract_claims(company: str, vertical: str, k: int = 6) -> dict:
    dims = get_dimensions(vertical)
    all_claims: list[Claim] = []
    dimensions_empty = 0
    malformed_dimensions = 0
    claims_invalid = 0
    groq_calls = 0
    rows = []
    t0 = time.time()

    for dim in dims:
        query = DIMENSION_QUERY.get(dim, f"{{company}} {dim}").format(company=company)
        chunks = retrieve(query, company, k=k)
        if not chunks:
            dimensions_empty += 1
            rows.append((dim, 0, 0))
            continue

        id_map = {f"E{i + 1}": c["content_hash"] for i, c in enumerate(chunks)}
        messages = _build_prompt(company, dim, chunks)
        dim_claims: list[Claim] = []
        # attempt 1, plus one re-ask if the output is malformed OR every claim
        # was invalid (e.g. all citations invented) — coverage depends on it
        for is_retry in (False, True):
            raw = _call_groq(messages)
            groq_calls += 1
            time.sleep(2)
            try:
                if raw is None:
                    raise ValueError("no response")
                dim_claims, invalid = _parse_claims(raw, dim, id_map)
                claims_invalid += invalid
                # enforce the prompt's own cap — the model sometimes ignores
                # "1-4 claims"; keep the strongest 4 (stable sort keeps the
                # model's ordering among ties)
                dim_claims.sort(key=lambda c: c.strength, reverse=True)
                dim_claims = dim_claims[:4]
            except (json.JSONDecodeError, ValueError):
                dim_claims = []
                if is_retry:
                    malformed_dimensions += 1
            if dim_claims or is_retry:
                break
            messages = messages + [
                {"role": "assistant", "content": raw or ""},
                {"role": "user", "content":
                    "Your previous output was invalid: either not a JSON array for "
                    "the schema, or its claims cited labels that do not appear in "
                    "the evidence blocks. Return only the JSON array, citing only "
                    "the E-labels (E1, E2, ...) shown above."},
            ]

        all_claims.extend(dim_claims)
        rows.append((dim, len(chunks), len(dim_claims)))

    return {
        "company": company,
        "vertical": vertical,
        "claims": [c.model_dump() for c in all_claims],
        "metrics": {
            "dimensions_total": len(dims),
            "dimensions_empty": dimensions_empty,
            "malformed_dimensions": malformed_dimensions,
            "claims_invalid": claims_invalid,
            "claims_extracted": len(all_claims),
            "groq_calls": groq_calls,
            "seconds": round(time.time() - t0, 1),
        },
        "_rows": rows,  # dimension | chunks | claims, for CLI table
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: -m claims.extractor <Company> <vertical>")
        sys.exit(1)

    company, vertical = sys.argv[1], sys.argv[2]
    print(f"🔎 Extracting claims for {company} ({vertical})")
    result = extract_claims(company, vertical)

    print(f"\n{'dimension':<20} {'chunks':>7} {'claims':>7}")
    print("-" * 36)
    for dim, n_chunks, n_claims in result["_rows"]:
        print(f"{dim:<20} {n_chunks:>7} {n_claims:>7}")

    result.pop("_rows")
    print(f"\n📊 {json.dumps(result['metrics'], indent=2)}")
    print(json.dumps(result, indent=2))
