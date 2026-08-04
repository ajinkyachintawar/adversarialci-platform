"""
Heads LLM Caller
================
One shared Groq caller for all heads (buyer/seller/analyst). Copies the
key-rotation-on-429 pattern from claims/extractor.py::_call_groq (does not
import it — heads owns its own caller since it needs both the 8B debate
model and the 70B judge model, picked per-call via `model`).

Groq free tier is ~6K TPM per key: calls are sequential, paced PACE_S apart
on entry (see call_llm); on 429 the key rotates across GROQ_API_KEYS (separate
accounts = separate TPM), one full extra round after all keys are exhausted,
then give up (None).

Run:  .venv/bin/python -m heads.llm    (self-check, no network)
"""

import sys
import os
import time
from functools import lru_cache

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from groq import Groq
from config import GROQ_API_KEYS

_key_idx = 0  # rotates across GROQ_API_KEYS on 429
call_count = 0  # total successful calls this process — read by eval/heads_smoke.py
_last_call_at = 0.0  # for PACE_S; see call_llm

# Minimum gap between two Groq calls. Enforced BEFORE the call, not after it:
# a trailing sleep(2) also delays the caller's return, which the batch loops
# never noticed but earshot.answer pays on every single question a rep asks.
# Pacing on entry is identical for back-to-back loops and free when calls are
# already seconds apart.
PACE_S = 2.0  # floor; the real gap is computed per call, see _pace_for()


def _pace_for(model: str, estimated: float) -> float:
    """Seconds to leave between calls so a batch stays under the model's TPM.

    A FLAT pace cannot be right: the sustainable rate depends on prompt size,
    the model's per-minute cap, and how many keys share the load. At 5.2K tokens
    against the 70B's 12K TPM, three keys sustain one call per ~8.7s — we were
    firing every 1.6s, saturating TPM and then thrashing on 20s retries. That
    cost two contaminated eval runs before the arithmetic got done.

    Costs nothing on the server path: pacing is enforced on entry, and a rep's
    questions arrive far more than 9s apart. This only bites batch loops, which
    is exactly where it should.
    """
    cap = TOKEN_CAPS.get(model)
    if not cap or not estimated:
        return PACE_S
    return max(PACE_S, 60.0 * estimated / (cap * max(len(GROQ_API_KEYS), 1)))

# How many 20s waits to spend once every model and key is 429ing. Groq's TPM
# window is 60s, so one wait (the original behaviour) could not outlast it — a
# pinned-model eval lost its last 6 of 44 queries that way. Note the server path
# is capped by ASK_TIMEOUT_S long before this budget is spent; it exists for the
# batch/eval path, where finishing slowly beats a contaminated result.
TPM_RETRIES = 3

# Groq per-model TPM caps (input + max_tokens). chars/2.5 — measured on this
# corpus's table-heavy text, not the optimistic /4. Values read from Groq's own
# x-ratelimit-limit-tokens header on 2026-08-03, not guessed.
TOKEN_CAPS = {
    "llama-3.1-8b-instant": 6000,
    "llama-3.3-70b-versatile": 12000,
    "openai/gpt-oss-120b": 8000,
    "openai/gpt-oss-20b": 8000,
    "qwen/qwen3.6-27b": 8000,
}

# EVERY MODEL HAS ITS OWN TPM BUCKET — this is the whole point of the chain.
# earshot's prompt is ~5.2K tokens against the 70B's 12K/min, i.e. 2.3 calls per
# minute, which is why a 44-query eval 429-stormed for 18 minutes. Rotating keys
# alone cannot help: both keys hit the same per-model ceiling. Rotating MODELS
# raises the ceiling to roughly 12K+8K+8K+8K per key.
#
# Ordered by preference, not by size. gpt-oss-120b leads as of 2026-08-04, on
# measured attributed framing (92% vs the 70B's 65%; see earshot/answer.py MODEL)
# — NOT on budget, which it loses: 8K TPM against the 70B's 12K. That trade is
# deliberate and it has a cost: the primary now has the SMALLER bucket, so the
# chain 429s onto the 70B sooner than it used to. The 70B is first fallback
# precisely because it is the biggest bucket, so a degraded run degrades into
# more headroom, not less.
# Fallbacks are a degraded mode — the verbatim gate still catches misquotes, so
# the risk is weaker judgement on evidence_answers_question, never fabrication.
# Benchmark with eval/abstention_eval.py before promoting any of these to primary.
# Tested live against earshot's real prompt on 2026-08-03 (the 70B was already
# 429'd, so this chain was exercised for real, not just stubbed):
#   openai/gpt-oss-120b  OK  1.7s  — same citations as the 70B's 5.0s
#   openai/gpt-oss-20b   OK  0.9s  — quoted the raw scrape artifact verbatim
#   qwen/qwen3.6-27b     PARSE FAIL — does not return bare JSON. EXCLUDED.
# Do not add a model here without running it through _parse() on a real prompt;
# a fallback that cannot produce the schema is worse than no fallback, because
# it burns the retry budget and returns None, which now reads as an outage.
MODEL_FALLBACKS = {
    "openai/gpt-oss-120b": ["llama-3.3-70b-versatile", "openai/gpt-oss-20b"],
    # kept so EARSHOT_MODEL=llama-3.3-70b-versatile still has a chain to fall
    # down — the comparison above is re-runnable, not a one-off.
    "llama-3.3-70b-versatile": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"],
}


@lru_cache(maxsize=8)
def _client(api_key: str) -> Groq:
    """One client per key, reused.

    call_llm used to construct a fresh Groq() per call and never close it, so a
    long run accumulated sockets (90 open in one eval). Harmless in a batch
    script that exits; a genuine leak in the long-lived POST /api/ask server.
    """
    return Groq(api_key=api_key)


class OversizedPromptError(Exception):
    """Raised by call_llm when estimate_tokens(messages, max_tokens) exceeds
    TOKEN_CAPS[model] — content decisions (which claims to drop) belong to
    the caller, not this module, so call_llm never silently truncates."""


def estimate_tokens(messages: list, max_tokens: int) -> float:
    return sum(len(m["content"]) for m in messages) / 2.5 + max_tokens


def fits(messages: list, model: str, max_tokens: int) -> bool:
    """True if messages is under model's TOKEN_CAPS (or the model has no
    configured cap). Heads call this in a loop, dropping claims between
    checks, before ever calling call_llm."""
    cap = TOKEN_CAPS.get(model)
    return cap is None or estimate_tokens(messages, max_tokens) <= cap


def drop_lowest_strength(claim_pool: dict) -> bool:
    """Removes the single lowest-strength claim across every list in
    claim_pool (in place, by reference — same dict/lists the caller renders
    from). Returns False once every list is empty, so a caller's budget-fit
    loop knows to stop. Shared by every head's budget-fit loop (judge,
    synthesis, and the 8B debate prompts)."""
    worst = None  # (strength, key, idx)
    for key, claims in claim_pool.items():
        for idx, c in enumerate(claims):
            if worst is None or c["strength"] < worst[0]:
                worst = (c["strength"], key, idx)
    if worst is None:
        return False
    _, key, idx = worst
    claim_pool[key].pop(idx)
    return True


def call_llm(messages: list, model: str, max_tokens: int = 2048,
             temperature: float = 0.2) -> str | None:
    """On 429: rotate keys, then rotate to a fallback MODEL (separate TPM
    bucket), and only then wait. None on hard error or full exhaustion. Raises
    OversizedPromptError before ever calling Groq if the prompt would exceed
    the requested model's TOKEN_CAPS — callers must shrink and retry.

    Model rotation is what actually breaks a 429 storm: both keys share one
    per-model ceiling, so rotating keys alone cannot raise throughput. Fallback
    models with a smaller cap than the prompt are skipped, never truncated.
    """
    global _key_idx, call_count, _last_call_at
    cap = TOKEN_CAPS.get(model)
    estimated = estimate_tokens(messages, max_tokens)
    if cap is not None and estimated > cap:
        raise OversizedPromptError(
            f"estimated {estimated:.0f} tokens > {cap} cap for {model}")

    # requested model first, then any fallback whose cap still fits the prompt.
    # GROQ_NO_FALLBACK pins the run to one model: a fallback firing mid-eval
    # silently produces a MIXED-MODEL result, which cannot answer "is model X
    # better than Y" — the exact question a benchmark run is asked. Production
    # always wants the fallback; a controlled comparison never does.
    chain = [model]
    if not os.environ.get("GROQ_NO_FALLBACK"):
        chain += [m for m in MODEL_FALLBACKS.get(model, [])
                  if TOKEN_CAPS.get(m, 0) >= estimated]

    for m_idx, m in enumerate(chain):
        if m_idx:
            print(f"  🔄 Groq 429 — falling back to {m} (separate quota)")
        for attempt in range(len(GROQ_API_KEYS)):
            try:
                pace = _pace_for(m, estimated)
                gap = time.time() - _last_call_at
                if gap < pace:
                    time.sleep(pace - gap)
                _last_call_at = time.time()
                response = _client(GROQ_API_KEYS[_key_idx]).chat.completions.create(
                    model=m,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content
                call_count += 1
                if m_idx:
                    print(f"  ✅ answered by fallback {m}")
                return content
            except Exception as e:
                if "429" not in str(e):
                    print(f"  ⚠️  Groq error ({m}): {e}")
                    return None
                _key_idx = (_key_idx + 1) % len(GROQ_API_KEYS)
                if len(GROQ_API_KEYS) > 1:
                    print(f"  🔑 429 on {m} — rotating to key #{_key_idx + 1}")

    # Every model on every key is rate limited, so the ceiling is real: wait out
    # the TPM window rather than hammering. Groq's TPM window is 60s, and ONE
    # 20s wait was not enough — a pinned-model eval lost its last 6 of 44
    # queries to exactly this. Three waits covers a full window.
    for wait_n in range(TPM_RETRIES):
        print(f"  ⏳ 429 everywhere — waiting 20s for the TPM window "
              f"({wait_n + 1}/{TPM_RETRIES})")
        time.sleep(20)
        try:
            response = _client(GROQ_API_KEYS[_key_idx]).chat.completions.create(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens)
            call_count += 1
            return response.choices[0].message.content
        except Exception as e:
            if "429" not in str(e):
                print(f"  ⚠️  Groq error: {e}")
                return None
            _key_idx = (_key_idx + 1) % len(GROQ_API_KEYS)
    print("  ⚠️  Groq: rate limited on every model and key, giving up")
    return None


def _self_check():
    # no network — just verifies the module imports and key rotation index
    # wraps correctly with a fake key list
    global _key_idx
    assert callable(call_llm)
    _key_idx = 0
    assert GROQ_API_KEYS, "GROQ_API_KEYS must be configured in .env for heads/"

    # oversized prompt is rejected before any network call — no key/env
    # dependency, so this checks purely the pre-flight math
    huge = [{"role": "user", "content": "x" * 20000}]
    try:
        call_llm(huge, model="llama-3.1-8b-instant")
        assert False, "should have raised OversizedPromptError"
    except OversizedPromptError:
        pass
    # a model with no configured cap is never rejected pre-flight
    assert estimate_tokens(huge, 2048) > TOKEN_CAPS["llama-3.1-8b-instant"]
    assert fits(huge, "some-uncapped-model", 2048)
    assert not fits(huge, "llama-3.1-8b-instant", 2048)

    # Pacing is enforced on ENTRY, so a cold call returns immediately while
    # two back-to-back calls stay PACE_S apart. This is the whole latency win
    # (p50 was 12.8s with the old trailing sleep) — stub Groq and prove both
    # halves, since a trailing sleep would pass a cold-call check alone.
    global _last_call_at, Groq
    real_groq, small = Groq, [{"role": "user", "content": "hi"}]
    Groq = lambda api_key: type("C", (), {"chat": type("X", (), {"completions": type(
        "Y", (), {"create": staticmethod(lambda **kw: type("R", (), {"choices": [
            type("M", (), {"message": type("N", (), {"content": "ok"})()})()]})())})()})()})()
    def _stub(reply="ok", fail_models=()):
        """Groq stub: 429s for models in fail_models, else returns `reply`."""
        def _mk(api_key):
            def create(**kw):
                if kw["model"] in fail_models:
                    raise RuntimeError("Error code: 429 - rate_limit_exceeded")
                return type("R", (), {"choices": [type("M", (), {
                    "message": type("N", (), {"content": f"{reply}:{kw['model']}"})()})()]})()
            return type("C", (), {"chat": type("X", (), {
                "completions": type("Y", (), {"create": staticmethod(create)})()})()})()
        return _mk

    try:
        Groq = _stub()
        _client.cache_clear()
        _last_call_at = 0.0
        t0 = time.time()
        assert call_llm(small, model="llama-3.1-8b-instant").startswith("ok")
        assert time.time() - t0 < 0.5, "cold call must not pay the pacing sleep"
        t0 = time.time()  # second call immediately after — must be paced
        assert call_llm(small, model="llama-3.1-8b-instant").startswith("ok")
        assert time.time() - t0 >= PACE_S - 0.1, "back-to-back calls must stay paced"

        # MODEL FALLBACK: the primary 429s on every key, so the call must land
        # on a fallback model (its own TPM bucket) rather than sleeping or
        # returning None. This is the entire point of MODEL_FALLBACKS.
        # The env var is set explicitly both ways — reading ambient env made
        # this test fail under GROQ_NO_FALLBACK, i.e. it tested the shell, not
        # the code.
        Groq = _stub(fail_models=("llama-3.3-70b-versatile",))
        _client.cache_clear()
        _last_call_at = 0.0
        os.environ.pop("GROQ_NO_FALLBACK", None)
        got = call_llm(small, model="llama-3.3-70b-versatile", max_tokens=100)
        assert got is not None, "must fall back, not give up"
        assert got.endswith(MODEL_FALLBACKS["llama-3.3-70b-versatile"][0]), got

        # ...and GROQ_NO_FALLBACK pins the run to one model, so a benchmark
        # cannot silently become a mixed-model average.
        os.environ["GROQ_NO_FALLBACK"] = "1"
        _last_call_at = 0.0
        assert call_llm(small, model="llama-3.3-70b-versatile", max_tokens=100) is None, \
            "GROQ_NO_FALLBACK must not silently fall back"
        os.environ.pop("GROQ_NO_FALLBACK", None)

        # a fallback whose TOKEN_CAPS cannot fit the prompt is SKIPPED, never
        # truncated — the 70B's 12K prompt must not be sent to an 8K model
        big = [{"role": "user", "content": "x" * 25000}]  # ~10K tokens
        chain = [m for m in MODEL_FALLBACKS["llama-3.3-70b-versatile"]
                 if TOKEN_CAPS.get(m, 0) >= estimate_tokens(big, 1024)]
        assert chain == [], "8K fallbacks must be skipped for a 10K prompt"

        # one client per key, reused — the leak fix
        _client.cache_clear()
        a, b = _client("k1"), _client("k1")
        assert a is b, "clients must be cached per key, not rebuilt per call"
    finally:
        Groq = real_groq
        _client.cache_clear()

    pool = {"A": [{"strength": 3}, {"strength": 1}], "B": [{"strength": 5}]}
    assert drop_lowest_strength(pool)
    assert pool == {"A": [{"strength": 3}], "B": [{"strength": 5}]}
    while drop_lowest_strength(pool):
        pass
    assert pool == {"A": [], "B": []}
    assert not drop_lowest_strength(pool)

    print("✅ heads.llm self-check passed (offline — no Groq call made)")


if __name__ == "__main__":
    _self_check()
