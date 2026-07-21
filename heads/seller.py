"""
Seller Head
===========
1-round red-team (8B) + 70B synthesis -> SellerVerdict.

Red-team (one 8B call per competitor): the competitor's advocate attacks
my_company, citing its own strength claims plus my_company's weakness claims
(indexes into the enumerated lists shown in the prompt; validated same as
heads/buyer.py).

Counter (one 8B call): my_company's advocate answers every objection raised,
citing only my_company's own claims.

Synthesis (one 70B call): given the challenge, every gated claim, and the
red-team + counter transcript, produce a SellerVerdict. evidence_ids in the
output are trusted only after heads/consistency.py confirms they resolve
against the real claim pool.

Run:  .venv/bin/python -m heads.seller  (requires Atlas + Groq — see eval/heads_smoke.py)
"""

import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heads import llm as llm_mod
from heads.llm import call_llm
from heads.schemas import SellerVerdict, parse_verdict_json
from heads import evidence as evidence_mod
from heads import citations
from heads.buyer import _render_claims  # shared claim-list rendering, not private logic

DEBATE_MODEL = "llama-3.1-8b-instant"
JUDGE_MAX_TOKENS = 3000


def _strip_json(raw: str | None) -> dict:
    if raw is None:
        return {}
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _red_team(competitor: str, competitor_claims: list[dict],
              my_claims: list[dict], my_company: str, challenge: str) -> dict:
    """One 8B call: competitor attacks my_company. Returns validated
    {"objections": [{"claim_idx": i, "source": "own"|"mine"}]}."""
    competitor_claims = list(competitor_claims)
    weakness_claims = [c for c in my_claims if c["stance"] == "weakness"]
    system = (f"You are the sales advocate for {competitor}, attacking a "
              f"rival ({my_company}) in a competitive deal. Argue only from "
              f"the evidence given.")

    def build():
        return [{"role": "system", "content": system}, {"role": "user", "content": f"""DEAL CONTEXT: {challenge}

YOU REPRESENT: {competitor}
YOUR STRENGTH CLAIMS:
{_render_claims(competitor_claims)}

RIVAL ({my_company})'S WEAKNESS CLAIMS:
{_render_claims(weakness_claims)}

Raise up to 3 objections a prospect might have about choosing {my_company}
over {competitor}. Each objection cites ONE claim by index, and says whether
it's your own strength claim ("own") or the rival's weakness claim ("mine").
Return ONLY JSON, no markdown fences:
{{"objections": [{{"claim_idx": 0, "source": "own"}}]}}"""}]

    dropped = 0
    while not llm_mod.fits(build(), DEBATE_MODEL, 2048):
        # rival's weakness claims first (the "attack" material), own last
        if llm_mod.drop_lowest_strength({"weak": weakness_claims}):
            pass
        elif not llm_mod.drop_lowest_strength({"own": competitor_claims}):
            break
        dropped += 1
    if dropped:
        print(f"  ⚠️ budget: dropped {dropped} low-strength claims to fit {DEBATE_MODEL}")

    raw = call_llm(build(), model=DEBATE_MODEL)
    obj = _strip_json(raw)
    objections = []
    for o in obj.get("objections", []):
        if not isinstance(o, dict):
            continue
        idx, source = o.get("claim_idx"), o.get("source")
        if source == "own" and isinstance(idx, int) and 0 <= idx < len(competitor_claims):
            objections.append({"claim": competitor_claims[idx], "from": competitor})
        elif source == "mine" and isinstance(idx, int) and 0 <= idx < len(weakness_claims):
            objections.append({"claim": weakness_claims[idx], "from": competitor})
    return {"objections": objections}


def _counter(my_company: str, my_claims: list[dict],
             all_objections: list[dict], challenge: str) -> dict:
    """One 8B call: answer every objection using only my_company's claims."""
    if not all_objections:
        return {"responses": []}
    my_claims = list(my_claims)
    obj_block = "\n".join(
        f"- ({o['from']}) \"{o['claim']['claim']}\"" for o in all_objections
    )
    system = f"You are the sales advocate for {my_company}, countering objections."

    def build():
        return [{"role": "system", "content": system}, {"role": "user", "content": f"""DEAL CONTEXT: {challenge}

YOU REPRESENT: {my_company}
YOUR CLAIMS:
{_render_claims(my_claims)}

OBJECTIONS RAISED AGAINST YOU:
{obj_block}

For each objection, pick one of your own claims (by index) that best
answers it, and give a one-sentence response.
Return ONLY JSON, no markdown fences:
{{"responses": [{{"objection_idx": 0, "claim_idx": 0, "text": "..."}}]}}"""}]

    dropped = 0
    while not llm_mod.fits(build(), DEBATE_MODEL, 2048):
        if not llm_mod.drop_lowest_strength({"own": my_claims}):
            break
        dropped += 1
    if dropped:
        print(f"  ⚠️ budget: dropped {dropped} low-strength claims to fit {DEBATE_MODEL}")

    raw = call_llm(build(), model=DEBATE_MODEL)
    obj = _strip_json(raw)
    responses = []
    for r in obj.get("responses", []):
        if not isinstance(r, dict):
            continue
        o_idx, c_idx = r.get("objection_idx"), r.get("claim_idx")
        if (isinstance(o_idx, int) and 0 <= o_idx < len(all_objections)
                and isinstance(c_idx, int) and 0 <= c_idx < len(my_claims)):
            responses.append({
                "objection": all_objections[o_idx],
                "response_claim": my_claims[c_idx],
                "text": r.get("text", ""),
            })
    return {"responses": responses}


def _render_transcript(objections: list[dict], responses: list[dict]) -> str:
    # no evidence hashes here either — this transcript feeds straight into
    # the 70B synthesis prompt (see heads/citations.py module docstring)
    lines = [f"OBJECTION ({o['from']}): \"{o['claim']['claim']}\"" for o in objections]
    for r in responses:
        lines.append(f"RESPONSE: {r['text']} (citing: \"{r['response_claim']['claim']}\")")
    return "\n".join(lines) if lines else "(no objections raised)"


def _synthesize(my_company: str, competitors: list[str], claims_by_company: dict,
                 objections: list[dict], responses: list[dict],
                 challenge: str, judge_model: str) -> SellerVerdict:
    transcript = _render_transcript(objections, responses)
    # local, droppable copy — never mutates the caller's claims_by_company
    pool = {my_company: list(claims_by_company[my_company])}

    def build():
        claims_block, label_to_claim = citations.label_and_render(pool)
        system = ("You are an impartial sales-engineering analyst producing "
                  "a battlecard. Base it only on the cited evidence — every "
                  "claim_id you cite must be one of the labels shown.")
        user = f"""DEAL CONTEXT: {challenge}

YOU SELL: {my_company}
COMPETITORS: {', '.join(competitors)}

{my_company}'S CLAIMS:
{claims_block[my_company]}

RED-TEAM TRANSCRIPT:
{transcript}

Return a SellerVerdict JSON. advantages/vulnerabilities/objections/landmines
must each cite claim_ids using only the labels shown above (e.g. ["C3"]) —
never invent one. win_probability (0-100) should reflect claim strengths and
how well objections were answered.
Return ONLY JSON, no markdown fences:
{{"mode": "seller", "my_company": "{my_company}", "win_probability": 50,
  "advantages": [{{"text": "...", "claim_ids": ["C1"]}}],
  "vulnerabilities": [{{"text": "...", "claim_ids": ["C1"]}}],
  "objections": [{{"objection": "...", "response": "...", "claim_ids": ["C1"]}}],
  "landmines": [{{"text": "...", "claim_ids": ["C1"]}}],
  "talk_tracks": ["..."], "do_not_say": ["..."]}}"""
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
            return parse_verdict_json(raw, SellerVerdict, resolve_ids=resolve_ids)
        except Exception as e:
            if is_retry:
                raise ValueError(f"synthesis output invalid after re-ask: {e}")
            echo = (raw or "")[:200]
            messages = messages + [
                {"role": "assistant", "content": echo + ("..." if raw and len(raw) > 200 else "")},
                {"role": "user", "content":
                    f"Your previous output was invalid JSON for the "
                    f"SellerVerdict schema ({e}). Return only the corrected "
                    f"JSON object, citing only real claim_ids shown above."},
            ]
    raise ValueError("unreachable")


def run_seller(state: dict) -> SellerVerdict:
    """Public contract per the brief. heads/runner.py calls
    `_run_with_evidence` directly to avoid a second evidence.gather."""
    verdict, _ = _run_with_evidence(state)
    return verdict


def _run_with_evidence(state: dict) -> tuple[SellerVerdict, dict]:
    from config import LLM_MODEL
    vertical = state["vertical"]
    primary = state["primary"]
    companies = [primary] + state["competitors"]
    my_company = state.get("my_company") or primary
    competitors = [c for c in companies if c != my_company]
    plaintiff = state["plaintiff"]

    from pipeline.court_session import build_challenge
    challenge = build_challenge(plaintiff, vertical)

    print(f"  🎯 Seller head: {my_company} vs {', '.join(competitors)}")
    gathered = evidence_mod.gather(companies, vertical)
    claims_by_company = gathered["claims_by_company"]
    my_claims = claims_by_company[my_company]

    print("  ⚔️  Red-team — competitor objections")
    all_objections = []
    for competitor in competitors:
        result = _red_team(competitor, claims_by_company[competitor],
                            my_claims, my_company, challenge)
        all_objections.extend(result["objections"])

    print("  🛡️  Counter — my_company responses")
    counter = _counter(my_company, my_claims, all_objections, challenge)

    print("  🧑‍⚖️  Synthesis (70B)")
    verdict = _synthesize(my_company, competitors, claims_by_company,
                           all_objections, counter["responses"], challenge, LLM_MODEL)

    return verdict, claims_by_company


if __name__ == "__main__":
    from state import create_initial_state
    state = create_initial_state("database", "seller")
    state.update({
        "primary": "Pinecone",
        "competitors": ["MongoDB", "Weaviate"],
        "my_company": "Pinecone",
        "plaintiff": {
            "mode": "seller",
            "company_name": "TestCorp",
            "team_size": "8 engineers",
            "budget": "$2,000",
            "use_case": "RAG pipeline for customer support",
            "scale": "5M vectors now, 50M in 12mo",
            "cloud": "AWS",
            "priority": "performance",
        },
    })
    verdict, claims = _run_with_evidence(state)
    print(json.dumps(verdict.model_dump(), indent=2))
