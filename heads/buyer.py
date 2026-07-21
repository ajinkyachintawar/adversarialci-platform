"""
Buyer Head
==========
2-round debate (8B) + 70B judge -> BuyerVerdict.

Round 1 (one 8B call per company): advocate picks its 3 strongest claims for
this plaintiff profile, and names the weakness claim it will attack on each
rival (claims referenced by list index into the enumerated claim lists shown
in that prompt — indexes are validated, out-of-range ones are dropped).

Round 2 (one 8B call per company): rebuttal — respond to the attacks made on
you in round 1, using only your own claims (again referenced by index).

Judge (one 70B call): given the challenge, every gated claim (with real
evidence_ids) and both debate rounds rendered back to text, produce a
BuyerVerdict. evidence_ids in the verdict are validated against the pool of
real evidence_ids before being trusted — see heads/consistency.py.

Confidence is NOT trusted from the judge: after validation it is recomputed
deterministically as round(100 * dims_won_by_winner / len(per_dimension)) and
overwritten, so heads/consistency.py can assert the identity holds.

Run:  .venv/bin/python -m heads.buyer   (requires Atlas + Groq — see eval/heads_smoke.py)
"""

import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heads import llm as llm_mod
from heads.llm import call_llm
from heads.schemas import BuyerVerdict, parse_verdict_json, names_match
from heads import evidence as evidence_mod
from heads import citations
from verticals import get_dimensions, get_vertical

DEBATE_MODEL = "llama-3.1-8b-instant"
JUDGE_MAX_TOKENS = 3000


def _render_claims(claims: list[dict]) -> str:
    # NB: no evidence hashes here — Phase 1's E-label lesson applies to the
    # debate rounds too (they use local list indexes, not the judge's global
    # C-labels — see heads/citations.py — but hashes never belong in a prompt)
    return "\n".join(
        f"  [{i}] ({c['dimension']}, {c['stance']}, strength {c['strength']}) {c['claim']}"
        for i, c in enumerate(claims)
    )


def _round1(company: str, own_claims: list[dict], rivals: dict[str, list[dict]],
            plaintiff: dict, challenge: str, vertical: str) -> dict:
    """One 8B call: pick top 3 own claims + one attack index per rival."""
    # budget guard: rival claims are the fat part of this prompt — cap them
    # first, own claims last, dropping lowest-strength until it fits
    rivals = {r: list(claims) for r, claims in rivals.items()}
    own_claims = list(own_claims)
    dropped = 0
    while not llm_mod.fits(_round1_messages(company, own_claims, rivals, challenge, vertical),
                           DEBATE_MODEL, 2048):
        # rivals first (the fat part of this prompt), own claims only if
        # rivals are already fully drained
        if any(rivals.values()):
            llm_mod.drop_lowest_strength(rivals)
        elif not llm_mod.drop_lowest_strength({"own": own_claims}):
            break
        dropped += 1
    if dropped:
        print(f"  ⚠️ budget: dropped {dropped} low-strength claims to fit {DEBATE_MODEL}")

    messages = _round1_messages(company, own_claims, rivals, challenge, vertical)
    raw = call_llm(messages, model=DEBATE_MODEL)
    return _parse_round_json(raw, own_claims, rivals)


def _round1_messages(company: str, own_claims: list[dict], rivals: dict[str, list[dict]],
                      challenge: str, vertical: str) -> list[dict]:
    rival_block = "\n\n".join(
        f"{rival}'s claims:\n{_render_claims(claims)}"
        for rival, claims in rivals.items()
    )
    display_name = get_vertical(vertical)["display_name"]
    system = (f"You are the sales advocate for a {display_name} vendor in a "
              "buyer evaluation. Argue only from the evidence given — never "
              "prior knowledge.")
    user = f"""BUYER PROFILE: {challenge}

YOU REPRESENT: {company}
YOUR CLAIMS:
{_render_claims(own_claims)}

RIVAL CLAIMS:
{rival_block}

Pick your 3 strongest claims (by index) for THIS buyer's profile, and pick
one weakness claim (by index) to attack on each rival.
Return ONLY JSON, no markdown fences:
{{"top_claims": [0, 1, 2], "attacks": {{"RivalName": 0}}}}"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_round_json(raw: str | None, own_claims: list[dict],
                       rivals: dict[str, list[dict]]) -> dict:
    if raw is None:
        return {"top_claims": [], "attacks": {}}
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return {"top_claims": [], "attacks": {}}

    top = [i for i in obj.get("top_claims", [])
           if isinstance(i, int) and 0 <= i < len(own_claims)]
    attacks = {}
    for rival, idx in (obj.get("attacks") or {}).items():
        rival_claims = rivals.get(rival, [])
        if isinstance(idx, int) and 0 <= idx < len(rival_claims):
            attacks[rival] = idx
    return {"top_claims": top, "attacks": attacks}


def _round2(company: str, own_claims: list[dict],
            attacks_on_me: dict[str, dict], challenge: str, vertical: str) -> dict:
    """One 8B call: rebut each attack made on `company` in round 1, using
    only company's own claims (index-validated same as round 1)."""
    if not attacks_on_me:
        return {"rebuttals": {}}
    own_claims = list(own_claims)
    attack_block = "\n".join(
        f"- {attacker} attacks you with: \"{claim['claim']}\" (their {claim['dimension']} claim)"
        for attacker, claim in attacks_on_me.items()
    )
    display_name = get_vertical(vertical)["display_name"]
    system = (f"You are the sales advocate for a {display_name} vendor, now "
              "rebutting attacks using only your own evidence.")

    def build():
        return [{"role": "system", "content": system}, {"role": "user", "content": f"""BUYER PROFILE: {challenge}

YOU REPRESENT: {company}
YOUR CLAIMS:
{_render_claims(own_claims)}

ATTACKS ON YOU:
{attack_block}

For each attacker, pick one of your own claims (by index) that best rebuts
them, and give a one-sentence rebuttal.
Return ONLY JSON, no markdown fences:
{{"rebuttals": {{"AttackerName": {{"claim_idx": 0, "text": "..."}}}}}}"""}]

    dropped = 0
    while not llm_mod.fits(build(), DEBATE_MODEL, 2048):
        if not llm_mod.drop_lowest_strength({"own": own_claims}):
            break
        dropped += 1
    if dropped:
        print(f"  ⚠️ budget: dropped {dropped} low-strength claims to fit {DEBATE_MODEL}")

    raw = call_llm(build(), model=DEBATE_MODEL)
    if raw is None:
        return {"rebuttals": {}}
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return {"rebuttals": {}}
    rebuttals = {}
    for attacker, r in (obj.get("rebuttals") or {}).items():
        if not isinstance(r, dict):
            continue
        idx = r.get("claim_idx")
        if isinstance(idx, int) and 0 <= idx < len(own_claims):
            rebuttals[attacker] = {"claim_idx": idx, "text": r.get("text", "")}
    return {"rebuttals": rebuttals}


def _render_debate(companies: list[str], round1: dict, round2: dict,
                    claims_by_company: dict) -> str:
    lines = []
    for company in companies:
        r1 = round1[company]
        top = [claims_by_company[company][i]["claim"] for i in r1["top_claims"]]
        lines.append(f"{company} round 1 — strongest claims: {top}")
        for rival, idx in r1["attacks"].items():
            atk = claims_by_company[rival][idx]["claim"]
            lines.append(f"{company} attacks {rival}: \"{atk}\"")
    for company in companies:
        r2 = round2[company]
        for attacker, r in r2["rebuttals"].items():
            own = claims_by_company[company][r["claim_idx"]]["claim"]
            lines.append(f"{company} rebuts {attacker}: {r['text']} (citing: \"{own}\")")
    return "\n".join(lines) if lines else "(no debate content — LLM calls failed)"


def _judge(companies: list[str], claims_by_company: dict, challenge: str,
           debate_text: str, vertical: str, judge_model: str) -> BuyerVerdict:
    dims = get_dimensions(vertical)

    # local, droppable copy — never mutates the caller's claims_by_company
    # (consistency.py still checks the verdict against the real, full pool)
    pool = {c: list(claims) for c, claims in claims_by_company.items()}

    def build():
        claims_block, label_to_claim = citations.label_and_render(pool)
        rendered = "\n\n".join(f"{c}:\n{claims_block[c]}" for c in companies)
        system = ("You are an impartial judge for a buyer evaluation. Base "
                  "the verdict only on the cited evidence — every claim_id "
                  "you cite must be one of the labels shown below.")
        user = f"""BUYER PROFILE: {challenge}

CANDIDATES: {', '.join(companies)}
DIMENSIONS TO SCORE: {', '.join(dims)}

ALL GATED CLAIMS:
{rendered}

DEBATE TRANSCRIPT:
{debate_text}

Return a BuyerVerdict JSON for this profile. For EVERY dimension listed
above, pick a winner among {', '.join(companies)}. Cite claim_ids using only
the labels shown above (e.g. ["C7"]) — never invent one. Return ONLY JSON,
no markdown fences:
{{"mode": "buyer", "winner": "...", "confidence": 0,
  "per_dimension": [{{"dimension": "cost", "winner": "...", "reason": "...",
                      "claim_ids": ["C7"]}}],
  "summary": "...", "caveats": ["..."]}}"""
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        return messages, label_to_claim

    dropped = 0
    while True:
        messages, label_to_claim = build()
        if llm_mod.fits(messages, judge_model, JUDGE_MAX_TOKENS):
            break
        if not llm_mod.drop_lowest_strength(pool):
            break
        dropped += 1
    if dropped:
        print(f"  ⚠️ budget: dropped {dropped} low-strength claims to fit {judge_model}")

    resolve_ids = lambda obj: citations.resolve_claim_ids(obj, label_to_claim)

    for is_retry in (False, True):
        try:
            raw = call_llm(messages, model=judge_model, max_tokens=JUDGE_MAX_TOKENS)
            return parse_verdict_json(raw, BuyerVerdict, resolve_ids=resolve_ids)
        except Exception as e:
            if is_retry:
                raise ValueError(f"judge output invalid after re-ask: {e}")
            # Truncate echo — the model regenerating from the same prompt
            # doesn't need its full bad output, and echoing 1000+ tokens
            # blows the re-ask past TOKEN_CAPS on borderline-fit prompts.
            echo = (raw or "")[:200]
            messages = messages + [
                {"role": "assistant", "content": echo + ("..." if raw and len(raw) > 200 else "")},
                {"role": "user", "content":
                    f"Your previous output was invalid JSON for the "
                    f"BuyerVerdict schema ({e}). Return only the corrected "
                    f"JSON object, citing only real claim_ids shown above."},
            ]
    raise ValueError("unreachable")


def recompute_confidence(verdict: BuyerVerdict) -> BuyerVerdict:
    """Same formula as _run_with_evidence — exposed so heads/runner.py can
    reapply it after a consistency re-ask (the judge's raw number is never
    trusted, only this deterministic recompute). Winner names matched
    tolerantly (see heads/schemas.py::names_match) — same computation
    heads/consistency.py::_check_buyer asserts against."""
    if verdict.per_dimension:
        dims_won = sum(1 for d in verdict.per_dimension
                        if names_match(d.winner, verdict.winner))
        verdict.confidence = round(100 * dims_won / len(verdict.per_dimension))
    else:
        verdict.confidence = 0
    return verdict


def run_buyer(state: dict) -> BuyerVerdict:
    """Public contract per the Phase 2 brief. heads/runner.py calls
    `_run_with_evidence` directly instead, so it gets claims_by_company back
    without paying for a second (expensive, Groq-call-heavy) evidence.gather
    — this thin wrapper exists for direct/CLI callers that only want the
    verdict."""
    verdict, _ = _run_with_evidence(state)
    return verdict


def _run_with_evidence(state: dict) -> tuple[BuyerVerdict, dict]:
    from config import LLM_MODEL
    vertical = state["vertical"]
    primary = state["primary"]
    competitors = state["competitors"]
    companies = [primary] + competitors
    plaintiff = state["plaintiff"]

    from pipeline.court_session import build_challenge
    challenge = build_challenge(plaintiff, vertical)

    print(f"  ⚖️  Buyer head: {' vs '.join(companies)}")
    gathered = evidence_mod.gather(companies, vertical)
    claims_by_company = gathered["claims_by_company"]

    print("  🥊 Round 1 — opening claims + attacks")
    round1 = {}
    for company in companies:
        rivals = {c: claims_by_company[c] for c in companies if c != company}
        round1[company] = _round1(company, claims_by_company[company], rivals,
                                   plaintiff, challenge, vertical)

    print("  🛡️  Round 2 — rebuttals")
    round2 = {}
    for company in companies:
        attacks_on_me = {}
        for attacker in companies:
            if attacker == company:
                continue
            idx = round1[attacker]["attacks"].get(company)
            if idx is not None:
                attacks_on_me[attacker] = claims_by_company[company][idx]
        round2[company] = _round2(company, claims_by_company[company],
                                   attacks_on_me, challenge, vertical)

    debate_text = _render_debate(companies, round1, round2, claims_by_company)

    print("  🧑‍⚖️  Judge (70B)")
    verdict = _judge(companies, claims_by_company, challenge, debate_text,
                      vertical, LLM_MODEL)

    verdict = recompute_confidence(verdict)  # never trust the judge's own number

    return verdict, claims_by_company


if __name__ == "__main__":
    from state import create_initial_state
    state = create_initial_state("database", "buyer")
    state.update({
        "primary": "MongoDB",
        "competitors": ["Pinecone", "Weaviate"],
        "plaintiff": {
            "mode": "buyer",
            "company_name": "TestCorp",
            "team_size": "8 engineers",
            "budget": "$2,000",
            "use_case": "RAG pipeline for customer support",
            "scale": "5M vectors now, 50M in 12mo",
            "cloud": "AWS",
            "priority": "cost",
        },
    })
    verdict, claims = _run_with_evidence(state)
    print(json.dumps(verdict.model_dump(), indent=2))
