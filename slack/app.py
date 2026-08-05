"""
Slack /vs
=========
Phase 1 (pure core: signature verification, competitor resolution, message
rendering — no route, no DB, no httpx) plus Phase 2 (route, signature gate,
3s ack with a STUB answer). Pure functions take their inputs as arguments and
never touch env/DB/network, which is what keeps _self_check() runnable
offline with no Mongo reachable — see docs/EARSHOT_A2_SLACK.md. The I/O
section below the self_check-adjacent line is Phase 2: `_known_companies()`,
`_TASKS`, `_answer_and_deliver` (a fixed fake result run through the real
render() — it does NOT import earshot.answer, Phase 3 does that), and the
mounted route `POST /slack/vs`. Phases 3-5 (real answer() wiring, workspace
lookup, real Slack registration) are separate work — this file does not stub
them beyond the Phase 2 scope above.

Run:  .venv/bin/python -m slack.app                    (self-check, offline, no network)
      .venv/bin/uvicorn server:app --port 8011          (route, needs SLACK_SIGNING_SECRET)
"""

import hashlib
import hmac
import time
from urllib.parse import urlparse

# The only three companies with measured corpus quality (Phase 0). Expanding
# is a DATA change — add a name here — never a code change to the matcher
# below. See docs/EARSHOT_A2_SLACK.md "Scope decisions".
ANSWERABLE = ["MongoDB", "Pinecone", "Weaviate"]

# Keep tiny. An alias may NEVER resolve to a company absent from `known` —
# resolve_competitor() enforces that at lookup time, not here.
ALIASES = {"mongo": "MongoDB", "mongodb atlas": "MongoDB"}

# Shared across every non-answer outcome (error/timeout/busy/cap) so the one
# claim this product cannot make ("no evidence") never leaks into a message
# that is actually reporting a tool failure.
_NOT_ABSTENTION = "Nothing was checked — this is a tool problem, not an answer about {c}."

# Slack requires the signature check within 5 minutes of the request
# timestamp; replay protection.
_SIGNATURE_MAX_AGE_S = 300

# render(): cap citations/quote length so a Slack message never blows the
# 40k-char response_url payload limit.
_MAX_CITATIONS = 4
_MAX_QUOTE_CHARS = 300


def verify_slack_signature(secret: str, timestamp: str, signature: str, raw_body: bytes) -> bool:
    """Slack v0 signing scheme. Fail closed: missing secret/headers or a
    stale/future timestamp -> False, checked BEFORE the HMAC so a replay
    costs no crypto. raw_body is used as bytes, never decode()d and
    re-encode()d — one non-UTF-8 byte would silently break every signature."""
    if not secret or not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > _SIGNATURE_MAX_AGE_S:
        return False
    base = b"v0:" + timestamp.encode() + b":" + raw_body
    expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    # Compare as bytes: compare_digest raises TypeError on a non-ASCII str,
    # and `signature` is an attacker-controlled header — a raise here would
    # surface as a 500 instead of the fail-closed 401 this function promises.
    return hmac.compare_digest(expected.encode(), signature.encode())


def parse_command(fields: dict) -> dict:
    """Pull the handful of Slack slash-command fields we use out of the
    parsed form body. Dumb on purpose — no validation, that's the caller's
    job (resolve_competitor for `text`, the route for everything else)."""
    return {
        "team_id": fields.get("team_id", ""),
        "user_id": fields.get("user_id", ""),
        "channel_id": fields.get("channel_id", ""),
        "text": fields.get("text", "") or "",
        "response_url": fields.get("response_url", ""),
    }


def norm_company(s: str) -> str:
    """Case/whitespace-insensitive key for comparing company names —
    collapses internal whitespace too, so a scraped-looking "Mongo DB"
    still keys the same as "MongoDB" would if it were ever aliased that way.
    Also strips leading/trailing sentence punctuation per token, so a
    prefix like "weaviate:" or "weaviate," still matches "weaviate" — this
    is the only place prefixes get normalised, and it must NOT touch the
    question remainder (resolve_competitor slices that from the raw text)."""
    return " ".join(t.strip(".,:;!?") for t in s.split()).lower()


def resolve_competitor(text, known):
    """Longest-prefix match (up to 4 tokens) of `text` against the `known`
    list, so multi-word company names resolve correctly as the list grows —
    that growth is a data change, not a code change here.

    Returns (canonical|None, question, reason),
    reason in {"ok", "no_match", "no_question", "help"}.
    """
    text = (text or "").strip()
    # Bare `/vs` is the single most likely first interaction — treat it the
    # same as an explicit "help" rather than a failed match.
    if not text or text.lower() == "help":
        return None, "", "help"

    tokens = text.split()
    known_by_norm = {norm_company(k): k for k in known}

    matched = None
    matched_len = 0
    for length in range(min(4, len(tokens)), 0, -1):
        prefix_norm = norm_company(" ".join(tokens[:length]))
        if prefix_norm in known_by_norm:
            matched = known_by_norm[prefix_norm]
            matched_len = length
            break
        alias_target = ALIASES.get(prefix_norm)
        if alias_target is not None:
            # Alias safety: never resolve to a company the caller didn't
            # pass in `known` — a shrunk `known` list must shrink what
            # aliases can produce too.
            if norm_company(alias_target) in known_by_norm:
                matched = known_by_norm[norm_company(alias_target)]
                matched_len = length
                break
            # alias exists but its target isn't answerable here — keep
            # trying shorter prefixes rather than treating this as a match.

    if matched is None:
        return None, "", "no_match"

    question = " ".join(tokens[matched_len:]).strip()
    if not question:
        return matched, "", "no_question"
    return matched, question, "ok"


def esc(s: str) -> str:
    """Slack mrkdwn escaping — only these three characters are special."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(result: dict, competitor: str) -> str:
    """Render one of the six outcomes as Slack mrkdwn `text`. Plain text, not
    Block Kit — response_url takes {"text": ...} and Blocks would add a
    schema for identical output.

    `result` is the earshot.answer.answer() contract shape, or a bare
    {"confidence": "timeout"|"busy"|"cap"} for the outcomes answer() never
    produces itself.

    Returns plain text only — in_channel vs ephemeral is the caller's call
    (Phase 3 wires that: evidence -> in_channel, everything else -> ephemeral).
    """
    confidence = result.get("confidence")

    if confidence == "evidence":
        citations = result.get("citations") or []
        if not citations:
            # Hazard #2 from the plan: an uncited paragraph is precisely the
            # assert-a-fact failure this product exists to prevent.
            confidence = "none"
        else:
            lines = [esc(result.get("answer", ""))]
            for cite in citations[:_MAX_CITATIONS]:
                quote = esc(cite.get("quote", "")[:_MAX_QUOTE_CHARS])
                raw_url = cite.get("source_url", "")
                parsed = urlparse(raw_url)
                host_path = f"{parsed.netloc}{parsed.path}" or raw_url
                # `|` breaks Slack's <url|label> syntax into extra segments,
                # same class of problem esc() already handles for < and >.
                url = esc(raw_url).replace("|", "%7C")
                host_path = esc(host_path).replace("|", "%7C")
                line = f'> "{quote}"\n<{url}|{host_path}>'
                captured = cite.get("captured_at", "")
                if captured:
                    line += f" · {captured}"
                lines.append(line)
            return "\n".join(lines)

    if confidence == "none":
        return (
            f":mag: No evidence found on {esc(competitor)}'s own pages for that "
            "question. This is a result, not a bug — try rephrasing, or ask "
            "about pricing, features, or security instead."
        )
    if confidence == "error":
        detail = esc(result.get("error", "")) or "unknown error"
        return f":warning: {_NOT_ABSTENTION.format(c=esc(competitor))} ({detail})"
    if confidence == "timeout":
        return f":warning: That took too long and timed out. {_NOT_ABSTENTION.format(c=esc(competitor))}"
    if confidence == "busy":
        return f":warning: Still working on a previous question — try again shortly. {_NOT_ABSTENTION.format(c=esc(competitor))}"
    if confidence == "cap":
        return f":warning: Daily question limit reached. {_NOT_ABSTENTION.format(c=esc(competitor))}"

    # Unreachable with a well-formed result, but never silently say nothing.
    return f":warning: Unexpected outcome. {_NOT_ABSTENTION.format(c=esc(competitor))}"


# ============================================================================
# I/O — everything below reads the environment, the DB, or the network. The
# pure functions above never do; that split is what keeps _self_check()
# runnable offline. Phase 2 only: _answer_and_deliver is a STUB — it does not
# import earshot.answer (Phase 3 wires that in) — but it runs its fixed fake
# result through the real render() so the plumbing (ack, task, delivery) is
# exercised end to end today.
# ============================================================================

import asyncio
import os
import time as _time

_KNOWN_TTL_S = 300  # 5-minute cache — matches the plan's "5-min TTL".
_known_cache = {"at": 0.0, "companies": None}

# 3s Slack budget; ack copy must not overpromise the measured tail (Risk 2 —
# median 13-20s, p95 ~28s. Keep this in sync with the literal string below.
ACK_TEXT = ":mag: Checking their pages — this can take 20-30s..."


def _known_companies() -> list:
    """rag_chunks.distinct("company"), 5-min TTL, intersected with ANSWERABLE
    — the corpus is the source of truth for what's askable, same intent as
    /api/ask's own distinct() call. A DB failure must never raise into the
    request path: degrade to ANSWERABLE so the command still works, just
    without the freshest company list."""
    now = _time.time()
    if _known_cache["companies"] is not None and now - _known_cache["at"] < _KNOWN_TTL_S:
        return _known_cache["companies"]
    companies = list(ANSWERABLE)
    try:
        from db.atlas import get_collection
        corpus = set(get_collection("rag_chunks").distinct("company"))
        intersected = [c for c in ANSWERABLE if c in corpus]
        if not intersected:
            # A DB that answers but shares nothing with ANSWERABLE (wrong DB,
            # empty collection, renamed field) is a tool problem, not "we
            # answer zero companies" — degrade the same as a DB failure
            # rather than let every rep see "(none configured)".
            print(f"⚠️  _known_companies: corpus/ANSWERABLE intersection is empty (corpus={sorted(corpus)!r}), degrading to ANSWERABLE")
        else:
            companies = intersected
    except Exception as e:
        print(f"⚠️  _known_companies: DB unavailable, degrading to ANSWERABLE ({e})")
    _known_cache["at"] = now
    _known_cache["companies"] = companies
    return companies


# Strong references to in-flight fire-and-forget tasks. asyncio.create_task()
# only holds a WEAK reference — without this set, the task can be garbage
# collected mid-flight and the rep gets silence forever. server.py:349 has
# this exact bug today; this is the fixed shape, not the one to copy as-is.
_TASKS: set = set()


async def _answer_and_deliver(competitor: str, question: str, response_url: str):
    """PHASE 2 STUB. Does not call earshot.answer — Phase 3 wires the real
    call, the LLM lock, and the timeout in here. Produces one fixed fake
    result and runs it through the real render(), so the ack -> background
    task -> render -> deliver plumbing is fully exercised before Phase 3
    lands. The whole body is wrapped in try/except: an exception in a
    fire-and-forget task is otherwise a silent void — the rep never learns
    it failed."""
    try:
        result = {
            "answer": f"[Phase 2 stub] This is a placeholder answer about {competitor}.",
            "citations": [],
            "confidence": "none",
            "seconds": 0.0,
        }
        text = render(result, competitor)
    except Exception as e:
        text = f":warning: {_NOT_ABSTENTION.format(c=esc(competitor))} ({esc(str(e))})"
    await _deliver(text, response_url)


async def _deliver(text: str, response_url: str):
    """Post to Slack's response_url, or print when it's absent (curl testing
    with no Slack install needed — pulled forward from Phase 3 for exactly
    that reason)."""
    if not response_url:
        print(f"[slack.app] (no response_url) would deliver:\n{text}")
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(response_url, json={"text": text})
        if resp.status_code // 100 != 2:
            # An expired/used-up response_url 400s/404s silently otherwise —
            # indistinguishable from success, and the rep gets silence
            # forever, the exact failure _TASKS exists to prevent.
            print(f"⚠️  slack.app: response_url delivery got {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"⚠️  slack.app: response_url delivery failed: {e}")


from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, PlainTextResponse
from urllib.parse import parse_qs

router = APIRouter()


@router.post("/slack/vs")
async def slack_vs(request: Request):
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not secret:
        # Loud and distinct: an env typo on Render otherwise presents to a
        # rep as "Slack is broken" with zero signal in the logs.
        print("🔴 SLACK_SIGNING_SECRET is not set — every /slack/vs request will 401")

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    # Read the body EXACTLY ONCE — required for the HMAC (needs raw bytes)
    # and sidesteps FastAPI's Form(), which would consume the stream first.
    raw = await request.body()

    if not verify_slack_signature(secret, timestamp, signature, raw):
        # Distinguish stale-timestamp from bad-HMAC in the log only — the
        # response itself must not, or it becomes a free oracle for an
        # attacker probing which check failed.
        try:
            stale = secret and timestamp and abs(_time.time() - int(timestamp)) > _SIGNATURE_MAX_AGE_S
        except ValueError:
            stale = False
        reason = "stale timestamp" if stale else "bad signature"
        print(f"🔴 /slack/vs: signature check failed ({reason})")
        return PlainTextResponse("invalid request signature", status_code=401)

    parsed_qs = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
    fields = {k: v[0] for k, v in parsed_qs.items()}
    parsed = parse_command(fields)
    text = parsed["text"]
    response_url = parsed["response_url"]

    # get_collection uses sync pymongo (db/atlas.py), not motor — run it off
    # the event loop or a slow/cold Atlas round-trip blocks every concurrent
    # request and eats the 3s Slack budget, defeating the ack architecture.
    known = await asyncio.to_thread(_known_companies)
    competitor, question, reason = resolve_competitor(text, known)

    if reason == "help":
        return JSONResponse({
            "response_type": "ephemeral",
            "text": ("Ask about a competitor, e.g. `/vs weaviate they said "
                      f"they're cheaper`. I can answer about: {', '.join(sorted(known)) or '(none configured)'}."),
        })
    if reason == "no_match":
        return JSONResponse({
            "response_type": "ephemeral",
            "text": (f":mag: I don't recognize that competitor. I can answer "
                      f"about: {', '.join(sorted(known)) or '(none configured)'}."),
        })
    if reason == "no_question":
        return JSONResponse({
            "response_type": "ephemeral",
            "text": f"What do you want to know about {esc(competitor)}? e.g. `/vs {esc(text)} pricing`.",
        })

    # reason == "ok" — fire the (stub, Phase 2) answer in the background and
    # ack within Slack's 3s budget. Hold a strong reference: see _TASKS.
    task = asyncio.create_task(_answer_and_deliver(competitor, question, response_url))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)

    return JSONResponse({"response_type": "ephemeral", "text": ACK_TEXT})


def _self_check():
    # --- signature verification -------------------------------------------------
    secret = "shhh"
    ts = str(int(time.time()))
    body = b"text=weaviate+pricing&team_id=T1"
    base = b"v0:" + ts.encode() + b":" + body
    good_sig = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()

    assert verify_slack_signature(secret, ts, good_sig, body) is True

    tampered = body + b"x"
    assert verify_slack_signature(secret, ts, good_sig, tampered) is False

    assert verify_slack_signature("wrong-secret", ts, good_sig, body) is False

    old_ts = str(int(time.time()) - 301)
    old_base = b"v0:" + old_ts.encode() + b":" + body
    old_sig = "v0=" + hmac.new(secret.encode(), old_base, hashlib.sha256).hexdigest()
    assert verify_slack_signature(secret, old_ts, old_sig, body) is False

    future_ts = str(int(time.time()) + 301)
    future_base = b"v0:" + future_ts.encode() + b":" + body
    future_sig = "v0=" + hmac.new(secret.encode(), future_base, hashlib.sha256).hexdigest()
    assert verify_slack_signature(secret, future_ts, future_sig, body) is False

    assert verify_slack_signature(secret, None, good_sig, body) is False
    assert verify_slack_signature(secret, ts, None, body) is False

    assert verify_slack_signature("", ts, good_sig, body) is False

    # attacker-controlled header with non-ASCII must fail closed, not raise
    assert verify_slack_signature(secret, ts, "v0=café", body) is False

    # --- resolution table --------------------------------------------------------
    table = [
        ("weaviate they said they're cheaper", "Weaviate", "they said they're cheaper", "ok"),
        ("MONGODB pricing?", "MongoDB", "pricing?", "ok"),
        ("mongo how much", "MongoDB", "how much", "ok"),
        ("  weaviate  are they cheaper ", "Weaviate", "are they cheaper", "ok"),
        ("weaviate", "Weaviate", "", "no_question"),
        ("notacompany x", None, "", "no_match"),
        ("help", None, "", "help"),
        ("", None, "", "help"),
        ("   ", None, "", "help"),
        ("weaviate: pricing?", "Weaviate", "pricing?", "ok"),
        ("weaviate, are they cheaper", "Weaviate", "are they cheaper", "ok"),
    ]
    for text, exp_company, exp_question, exp_reason in table:
        company, question, reason = resolve_competitor(text, ANSWERABLE)
        assert company == exp_company, (text, company)
        assert question == exp_question, (text, question)
        assert reason == exp_reason, (text, reason)

    # --- alias safety: an alias can't invent a company outside `known` -----------
    company, question, reason = resolve_competitor("mongo x", ["Weaviate"])
    assert company is None and reason == "no_match", (company, reason)

    # --- product-principle guard: error/timeout/busy/cap never read as
    # abstention, and always carry the "this is not an answer" framing -----------
    for confidence in ("error", "timeout", "busy", "cap"):
        text = render({"confidence": confidence, "error": "boom"}, "Weaviate")
        assert "no evidence" not in text.lower(), (confidence, text)
        assert _NOT_ABSTENTION.format(c="Weaviate") in text, (confidence, text)

    # --- evidence with empty citations renders as the "none" message -------------
    evidence_empty = render({"confidence": "evidence", "answer": "x", "citations": []}, "Weaviate")
    none_render = render({"confidence": "none"}, "Weaviate")
    assert evidence_empty == none_render

    # --- evidence with real citations renders the quote + link -------------------
    evidence = render({
        "confidence": "evidence",
        "answer": "Weaviate's starter tier is $25/month.",
        "citations": [{
            "quote": "$25 per month for the starter tier",
            "source_url": "https://weaviate.io/pricing",
            "captured_at": "18 Jul 2026",
        }],
    }, "Weaviate")
    assert "$25 per month for the starter tier" in evidence
    assert "weaviate.io/pricing" in evidence
    assert "18 Jul 2026" in evidence

    # a `|`/`>` in the URL must not break out of the <url|label> link syntax
    hostile = render({
        "confidence": "evidence",
        "answer": "x",
        "citations": [{
            "quote": "q",
            "source_url": "https://x.io/p|>evil",
            "captured_at": "",
        }],
    }, "Weaviate")
    # exactly one link opener (the quote's own "> " blockquote marker is a
    # separate, expected ">"); the pipe is gone and the raw ">" got escaped
    assert hostile.count("<") == 1, hostile
    assert "x.io/p|" not in hostile, hostile
    assert "&gt;" in hostile, hostile

    # --- esc -----------------------------------------------------------------
    assert esc("A & B <c>") == "A &amp; B &lt;c&gt;"

    # --- _known_companies must degrade to ANSWERABLE, never raise, and
    # never touch the network. Monkeypatch db.atlas.get_collection (importing
    # the module itself opens no socket — db/atlas.py only connects lazily
    # inside get_collection()) so this stays a pure, offline check. ---------
    import db.atlas as _atlas

    class _FakeCol:
        def __init__(self, companies):
            self._companies = companies
        def distinct(self, field):
            return self._companies

    _orig_get_collection = _atlas.get_collection
    try:
        # DB reachable but shares nothing with ANSWERABLE (wrong DB, empty
        # collection, renamed field) -> degrade, don't report zero companies.
        _atlas.get_collection = lambda name: _FakeCol([])
        _known_cache["at"] = 0.0
        _known_cache["companies"] = None
        assert _known_companies() == ANSWERABLE

        # DB unreachable -> degrade, never raise into the request path.
        def _raise(name):
            raise RuntimeError("simulated DB failure")
        _atlas.get_collection = _raise
        _known_cache["at"] = 0.0
        _known_cache["companies"] = None
        assert _known_companies() == ANSWERABLE
    finally:
        _atlas.get_collection = _orig_get_collection
        _known_cache["at"] = 0.0
        _known_cache["companies"] = None

    print("✅ slack.app self-check passed (offline — no network)")


if __name__ == "__main__":
    _self_check()
