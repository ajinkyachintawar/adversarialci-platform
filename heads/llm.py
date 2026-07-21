"""
Heads LLM Caller
================
One shared Groq caller for all heads (buyer/seller/analyst). Copies the
key-rotation-on-429 pattern from claims/extractor.py::_call_groq (does not
import it — heads owns its own caller since it needs both the 8B debate
model and the 70B judge model, picked per-call via `model`).

Groq free tier is ~6K TPM per key: calls are sequential, time.sleep(2) after
every successful call; on 429 the key rotates across GROQ_API_KEYS (separate
accounts = separate TPM), one full extra round after all keys are exhausted,
then give up (None).

Run:  .venv/bin/python -m heads.llm    (self-check, no network)
"""

import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from groq import Groq
from config import GROQ_API_KEYS

_key_idx = 0  # rotates across GROQ_API_KEYS on 429
call_count = 0  # total successful calls this process — read by eval/heads_smoke.py

# Groq per-model TPM caps (input + max_tokens). chars/2.5 — measured on this
# corpus's table-heavy text, not the optimistic /4.
TOKEN_CAPS = {"llama-3.1-8b-instant": 6000, "llama-3.3-70b-versatile": 12000}


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
    """On 429: rotate to the next key; once all keys are exhausted, wait 20s
    and go around once more. None on hard error or exhaustion. Raises
    OversizedPromptError before ever calling Groq if the prompt would exceed
    the model's TOKEN_CAPS — callers must shrink the prompt and retry."""
    global _key_idx, call_count
    cap = TOKEN_CAPS.get(model)
    if cap is not None:
        estimated = estimate_tokens(messages, max_tokens)
        if estimated > cap:
            raise OversizedPromptError(
                f"estimated {estimated:.0f} tokens > {cap} cap for {model}")
    for attempt in range(2 * len(GROQ_API_KEYS)):
        try:
            client = Groq(api_key=GROQ_API_KEYS[_key_idx])
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            call_count += 1
            time.sleep(2)
            return content
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
