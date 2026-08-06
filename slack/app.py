"""
Slack /vs
=========
Phase 1 (pure core: signature verification, competitor resolution, message
rendering — no route, no DB, no httpx), Phase 2 (route, signature gate, 3s
ack), Phase 3 (real answer() wiring: LLM lock, backstop timeout, daily cap,
response_type), and Phase 4 (per-workspace my_company lookup, ask_log).
Pure functions take their inputs as arguments and never touch env/DB/network,
which is what keeps _self_check() runnable offline with no Mongo/Groq
reachable — see docs/EARSHOT_A2_SLACK.md. The I/O section below the
self_check-adjacent line is where `earshot.answer` gets imported (inside
`_run_answer`, never at module scope) — `_known_companies()`, `_my_company()`,
`_log_ask()`/`_log_ask_safe()`, `_TASKS`, `_run_answer`, `_answer_and_deliver`,
`_deliver`, `router`, `slack_vs`. Phase 5 (real Slack app registration) is
separate work.

Run:  .venv/bin/python -m slack.app                    (self-check, offline, no network)
      .venv/bin/uvicorn server:app --port 8011          (route, needs SLACK_SIGNING_SECRET)
"""

import hashlib
import hmac
import time
from urllib.parse import urlparse

# Companies with measured corpus quality. MongoDB/Pinecone/Weaviate from
# Phase 0; Qdrant added in A3 Phase 1 (re-ingested from vendor seed URLs after
# a purge — its pre-A3 115 chunks were 96% third-party). Expanding is a DATA
# change — add a name here — never a code change to the matcher below.
# See docs/EARSHOT_A2_SLACK.md "Scope decisions".
ANSWERABLE = ["MongoDB", "Pinecone", "Weaviate", "Qdrant"]

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

    Returns (canonical|None, question, reason, resolved_via),
    reason in {"ok", "no_match", "no_question", "help"},
    resolved_via in {"direct", "alias", None} — None when no company was
    matched at all (no_match/help). Phase 4 logs this to ask_log so a run of
    "alias" resolutions against a name nobody added an alias for is the
    signal for which aliases to add next.
    """
    text = (text or "").strip()
    # Bare `/vs` is the single most likely first interaction — treat it the
    # same as an explicit "help" rather than a failed match.
    if not text or text.lower() == "help":
        return None, "", "help", None

    tokens = text.split()
    known_by_norm = {norm_company(k): k for k in known}

    matched = None
    matched_len = 0
    resolved_via = None
    for length in range(min(4, len(tokens)), 0, -1):
        prefix_norm = norm_company(" ".join(tokens[:length]))
        if prefix_norm in known_by_norm:
            matched = known_by_norm[prefix_norm]
            matched_len = length
            resolved_via = "direct"
            break
        alias_target = ALIASES.get(prefix_norm)
        if alias_target is not None:
            # Alias safety: never resolve to a company the caller didn't
            # pass in `known` — a shrunk `known` list must shrink what
            # aliases can produce too.
            if norm_company(alias_target) in known_by_norm:
                matched = known_by_norm[norm_company(alias_target)]
                matched_len = length
                resolved_via = "alias"
                break
            # alias exists but its target isn't answerable here — keep
            # trying shorter prefixes rather than treating this as a match.

    if matched is None:
        return None, "", "no_match", None

    question = " ".join(tokens[matched_len:]).strip()
    if not question:
        return matched, "", "no_question", resolved_via
    return matched, question, "ok", resolved_via


def esc(s: str) -> str:
    """Slack mrkdwn escaping — only these three characters are special."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Phase 4: shown only on the two outcomes that actually ran through answer()
# with no workspace configured (evidence/none) — the rep gets a thinner
# search (no comparison retrieval) and should know that's why, not assume
# it's the product's normal behavior. Never shown on error/timeout/busy/cap:
# those never reached the comparison step regardless of my_company.
# Addressed to a sales rep in Slack, not to whoever deploys this — a repo
# path is not something they can act on.
_NO_MY_COMPANY_FOOTER = (
    "\n\n_This answer covers {c} only — nobody has told me which company we "
    "are, so there's no side-by-side comparison. Ask your admin to set it up._"
)


def render(result: dict, competitor: str, no_my_company: bool = False) -> str:
    """Render one of the six outcomes as Slack mrkdwn `text`. Plain text, not
    Block Kit — response_url takes {"text": ...} and Blocks would add a
    schema for identical output.

    `result` is the earshot.answer.answer() contract shape, or a bare
    {"confidence": "timeout"|"busy"|"cap"} for the outcomes answer() never
    produces itself. `no_my_company` appends `_NO_MY_COMPANY_FOOTER` to the
    evidence/none renders (see that constant) — default False keeps every
    existing caller (incl. _self_check) unchanged.

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
            text = "\n".join(lines)
            if no_my_company:
                text += _NO_MY_COMPANY_FOOTER.format(c=esc(competitor))
            return text

    if confidence == "none":
        text = (
            f":mag: No evidence found on {esc(competitor)}'s own pages for that "
            "question. This is a result, not a bug — try rephrasing, or ask "
            "about pricing, features, or security instead."
        )
        if no_my_company:
            text += _NO_MY_COMPANY_FOOTER.format(c=esc(competitor))
        return text
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
# runnable offline. earshot.answer is imported lazily inside _run_answer, not
# at module scope, so importing this module still needs no DB/Groq reachable.
# ============================================================================

import asyncio
import os
import threading
import time as _time
from datetime import datetime

_KNOWN_TTL_S = 300  # 5-minute cache — matches the plan's "5-min TTL".
_known_cache = {"at": 0.0, "companies": None}

# Phase 4: per-team_id cache, same 5-min TTL as _known_companies. A dict
# (not a single slot) because, unlike ANSWERABLE, "my company" is genuinely
# per-workspace.
_MY_COMPANY_TTL_S = 300
_my_company_cache: dict = {}

# 3s Slack budget; ack copy must not overpromise the measured tail (Risk 2 —
# median 13-20s, p95 ~28s. Keep this in sync with the literal string below.
ACK_TEXT = ":mag: Checking their pages — this can take 20-30s..."

# How long to wait to ACQUIRE the LLM lock before giving up and returning
# "busy". Env-overridable so a test can shrink it to prove the busy path
# without waiting 25s. Default matches the plan.
SLACK_QUEUE_WAIT_S = float(os.environ.get("SLACK_QUEUE_WAIT_S", "25"))

# Backstop for the whole answer() call, once the lock is held. Deliberately
# > ASK_TIMEOUT_S (45, see server.py) — there is no browser here to 504, and
# a Slack message at 70s beats silence forever. wait_for() only cancels the
# awaiting coroutine, not the OS thread running answer() underneath it (see
# _answer_and_deliver) — this is a backstop on how long a REP waits, not a
# guarantee the underlying call actually stops.
SLACK_ANSWER_TIMEOUT_S = float(os.environ.get("SLACK_ANSWER_TIMEOUT_S", "90"))

# Dev guard against burning the day's free-tier Groq budget (~16-40
# LLM-reaching answers/day/model/key), not a product feature — real
# customers bring paid keys. In-process (date, count): dies on redeploy,
# accepted (see docs/EARSHOT_A2_SLACK.md Phase 3).
SLACK_DAILY_ANSWER_CAP = int(os.environ.get("SLACK_DAILY_ANSWER_CAP", "40"))
_daily_cap_state = {"date": None, "count": 0}

# ponytail: one process-wide lock, not per-key. heads/llm.py's _key_idx /
# _last_call_at / call_count / _pace_for() are unsynchronized module globals
# that assume one caller at a time; two concurrent /vs requests would race
# the pacer straight into a 429 storm. Groq's free-tier TPM is the binding
# constraint here, not throughput, so serializing is free — upgrade to a
# per-key lock only if paid keys ever make concurrency worth having.
_LLM_LOCK = threading.Lock()


def _daily_cap_room() -> bool:
    """True if today's count is under the cap. Read-only — the counter is
    committed separately, once the outcome is known. Resets on a UTC date
    rollover. Both run on the event loop only, so no lock is needed."""
    today = _time.strftime("%Y-%m-%d", _time.gmtime())
    if _daily_cap_state["date"] != today:
        _daily_cap_state["date"] = today
        _daily_cap_state["count"] = 0
    return _daily_cap_state["count"] < SLACK_DAILY_ANSWER_CAP


def _daily_cap_commit(confidence: str) -> None:
    """Charge one slot — unless the outcome was "busy", which never reached
    the LLM. The cap exists to count quota spend, so charging a request that
    spent none would let a burst of lock contention eat the whole day's
    budget without a single Groq call. "timeout" IS charged: wait_for stops
    the rep waiting, not the orphaned thread, and that thread keeps burning
    quota (see _answer_and_deliver)."""
    if confidence != "busy":
        _daily_cap_state["count"] += 1


def _run_answer(question: str, competitor: str, my_company: str | None) -> dict:
    """Runs on a worker thread via asyncio.to_thread. Acquires _LLM_LOCK
    INSIDE the thread, not around the caller's await — that is what makes an
    orphaned thread (one whose wait_for() already timed out) still own its
    lock slot until answer() genuinely finishes, instead of a second
    concurrent answer() stacking on top of it and racing heads/llm.py's
    pacer into a 429 storm."""
    from earshot.answer import answer
    if not _LLM_LOCK.acquire(timeout=SLACK_QUEUE_WAIT_S):
        return {"confidence": "busy"}
    try:
        return answer(question, competitor, my_company)
    finally:
        _LLM_LOCK.release()


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


def _my_company(team_id: str) -> str | None:
    """slack_workspaces.find_one({"team_id": ...}) -> DEFAULT_MY_COMPANY env
    -> None, 5-min cache per team_id. A DB failure falls through to the env
    fallback, never raises — same contract as _known_companies. Skipping the
    env on a DB blip would show a workspace that IS configured the "not
    configured" footer, i.e. report a tool problem as a settings statement;
    DEFAULT_MY_COMPANY is a deploy-time constant that needs no DB to read.
    answer() handles
    my_company=None natively (skips the comparison retrieval), so an
    unconfigured workspace degrades rather than fails; render() adds a
    footer for it (see _NO_MY_COMPANY_FOOTER)."""
    now = _time.time()
    cached = _my_company_cache.get(team_id)
    if cached is not None and now - cached[1] < _MY_COMPANY_TTL_S:
        return cached[0]
    try:
        from db.atlas import get_collection
        doc = get_collection("slack_workspaces").find_one({"team_id": team_id})
        value = (doc or {}).get("my_company") or os.environ.get("DEFAULT_MY_COMPANY") or None
    except Exception as e:
        print(f"⚠️  _my_company: DB unavailable, falling back to DEFAULT_MY_COMPANY ({e})")
        value = os.environ.get("DEFAULT_MY_COMPANY") or None
    _my_company_cache[team_id] = (value, now)
    return value


def _log_ask(**fields) -> None:
    """Sync insert into the shared ask_log collection (see server.py's
    /api/ask for the "source": "api" counterpart this mirrors). Runs on a
    worker thread — sync pymongo, same reason _known_companies/_my_company
    do."""
    from db.atlas import get_collection
    get_collection("ask_log").insert_one({"created_at": datetime.utcnow(), **fields})


async def _log_ask_safe(**fields) -> None:
    """The rep's answer is the product, the log is for A4 — a logging
    failure must never surface to the rep. Mirrors /api/ask's ask_log
    try/except."""
    try:
        await asyncio.to_thread(_log_ask, **fields)
    except Exception as e:
        print(f"⚠️  ask_log write failed (continuing): {e}")


# Strong references to in-flight fire-and-forget tasks. asyncio.create_task()
# only holds a WEAK reference — without this set, the task can be garbage
# collected mid-flight and the rep gets silence forever. server.py:349 has
# this exact bug today; this is the fixed shape, not the one to copy as-is.
_TASKS: set = set()


async def _answer_and_deliver(competitor: str, question: str, response_url: str,
                               *, team_id: str, slack_user_id: str, channel_id: str,
                               raw_text: str, resolved_via: str | None):
    """PHASE 3+4: the real call, the LLM lock, the backstop timeout, the
    daily cap, per-workspace my_company, and the ask_log write. The whole
    body is wrapped in try/except: an exception in a fire-and-forget task is
    otherwise a silent void — the rep never learns it failed. Cap check and
    the earshot.answer import both happen in here (not at module scope) so
    this file still imports with no DB/Groq reachable — see _self_check()."""
    my_company = None
    try:
        # Sync pymongo — off the event loop, same reason as _known_companies.
        my_company = await asyncio.to_thread(_my_company, team_id)

        if not _daily_cap_room():
            result = {"confidence": "cap"}
        else:
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(_run_answer, question, competitor, my_company),
                    timeout=SLACK_ANSWER_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                # wait_for() cancels the COROUTINE awaiting to_thread — the
                # underlying OS thread is NOT cancelled and keeps running
                # answer(), burning Groq quota, until it finishes on its own.
                # _LLM_LOCK (held inside that thread) is the only thing
                # stopping a second concurrent answer() from stacking on top
                # of the orphan and racing heads/llm.py's pacer.
                result = {"confidence": "timeout"}
            _daily_cap_commit(result.get("confidence", ""))

        text = render(result, competitor, no_my_company=(my_company is None))
        # Mirror render()'s own evidence->none downgrade (empty citations) so
        # response_type never says in_channel for a message that actually
        # rendered as "no evidence".
        is_evidence = result.get("confidence") == "evidence" and bool(result.get("citations"))
        response_type = "in_channel" if is_evidence else "ephemeral"
    except Exception as e:
        result = {"confidence": "error", "error": str(e)}
        text = f":warning: {_NOT_ABSTENTION.format(c=esc(competitor))} ({esc(str(e))})"
        response_type = "ephemeral"

    await _log_ask_safe(
        source="slack", team_id=team_id, slack_user_id=slack_user_id,
        channel_id=channel_id, raw_text=raw_text, resolved_via=resolved_via,
        question=question, competitor=competitor, my_company=my_company,
        answer=result.get("answer", ""), citations=result.get("citations", []),
        confidence=result.get("confidence"), seconds=result.get("seconds"),
    )
    await _deliver(text, response_url, response_type)


async def _deliver(text: str, response_url: str, response_type: str = "ephemeral"):
    """Post to Slack's response_url, or print when it's absent (curl testing
    with no Slack install needed)."""
    if not response_url:
        print(f"[slack.app] (no response_url, response_type={response_type}) would deliver:\n{text}")
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(response_url, json={"text": text, "response_type": response_type})
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
    team_id = parsed["team_id"]
    slack_user_id = parsed["user_id"]
    channel_id = parsed["channel_id"]

    # get_collection uses sync pymongo (db/atlas.py), not motor — run it off
    # the event loop or a slow/cold Atlas round-trip blocks every concurrent
    # request and eats the 3s Slack budget, defeating the ack architecture.
    known = await asyncio.to_thread(_known_companies)
    competitor, question, reason, resolved_via = resolve_competitor(text, known)

    # Outcomes decided here, before answer() is ever reached. All three get
    # logged (fire-and-forget, same _TASKS pattern as the real answer path,
    # so the DB write never eats the 3s ack budget):
    #   - "no_match" -> confidence "unknown_competitor": the plan's own
    #     signal for which aliases to add — must not be silently dropped.
    #   - "no_question" and "help" are typo-shaped, not resolution failures
    #     (no_question: right competitor, nothing asked yet; help: not an
    #     attempt at all) — logged anyway per the plan ("make sure those get
    #     logged too") under their own confidence values, distinct from
    #     unknown_competitor, so A4 doesn't lump real resolution misses in
    #     with someone just exploring the command.
    log_confidence = {"help": "help", "no_match": "unknown_competitor", "no_question": "no_question"}
    if reason in log_confidence:
        log_task = asyncio.create_task(_log_ask_safe(
            source="slack", team_id=team_id, slack_user_id=slack_user_id,
            channel_id=channel_id, raw_text=text, resolved_via=resolved_via,
            question=question, competitor=competitor, my_company=None,
            answer="", citations=[], confidence=log_confidence[reason], seconds=None,
        ))
        _TASKS.add(log_task)
        log_task.add_done_callback(_TASKS.discard)

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

    # reason == "ok" — fire the real answer() in the background and ack
    # within Slack's 3s budget. Hold a strong reference: see _TASKS.
    task = asyncio.create_task(_answer_and_deliver(
        competitor, question, response_url,
        team_id=team_id, slack_user_id=slack_user_id, channel_id=channel_id,
        raw_text=text, resolved_via=resolved_via,
    ))
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
        ("weaviate they said they're cheaper", "Weaviate", "they said they're cheaper", "ok", "direct"),
        ("MONGODB pricing?", "MongoDB", "pricing?", "ok", "direct"),
        ("mongo how much", "MongoDB", "how much", "ok", "alias"),
        ("  weaviate  are they cheaper ", "Weaviate", "are they cheaper", "ok", "direct"),
        ("weaviate", "Weaviate", "", "no_question", "direct"),
        ("notacompany x", None, "", "no_match", None),
        ("help", None, "", "help", None),
        ("", None, "", "help", None),
        ("   ", None, "", "help", None),
        ("weaviate: pricing?", "Weaviate", "pricing?", "ok", "direct"),
        ("weaviate, are they cheaper", "Weaviate", "are they cheaper", "ok", "direct"),
    ]
    for text, exp_company, exp_question, exp_reason, exp_via in table:
        company, question, reason, resolved_via = resolve_competitor(text, ANSWERABLE)
        assert company == exp_company, (text, company)
        assert question == exp_question, (text, question)
        assert reason == exp_reason, (text, reason)
        assert resolved_via == exp_via, (text, resolved_via)

    # --- alias safety: an alias can't invent a company outside `known` -----------
    company, question, reason, resolved_via = resolve_competitor("mongo x", ["Weaviate"])
    assert company is None and reason == "no_match" and resolved_via is None, (company, reason, resolved_via)

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

    # --- _my_company: doc found -> its value; doc absent OR DB down ->
    # DEFAULT_MY_COMPANY env; neither -> None. Never raises. -----------------
    class _FakeWorkspaceCol:
        def __init__(self, doc):
            self._doc = doc
        def find_one(self, query):
            return self._doc

    _orig_get_collection2 = _atlas.get_collection
    _orig_default = os.environ.get("DEFAULT_MY_COMPANY")
    try:
        _atlas.get_collection = lambda name: _FakeWorkspaceCol({"team_id": "T1", "my_company": "MongoDB"})
        _my_company_cache.clear()
        assert _my_company("T1") == "MongoDB"

        os.environ["DEFAULT_MY_COMPANY"] = "Pinecone"
        _atlas.get_collection = lambda name: _FakeWorkspaceCol(None)
        _my_company_cache.clear()
        assert _my_company("T2") == "Pinecone"

        os.environ.pop("DEFAULT_MY_COMPANY", None)
        _atlas.get_collection = lambda name: _FakeWorkspaceCol(None)
        _my_company_cache.clear()
        assert _my_company("T3") is None

        # DB failure must still honour the env fallback: skipping it would tell
        # a workspace that IS configured that it isn't — a tool problem dressed
        # up as a settings statement.
        def _raise2(name):
            raise RuntimeError("simulated DB failure")
        _atlas.get_collection = _raise2
        os.environ["DEFAULT_MY_COMPANY"] = "Pinecone"
        _my_company_cache.clear()
        assert _my_company("T4") == "Pinecone"

        os.environ.pop("DEFAULT_MY_COMPANY", None)
        _my_company_cache.clear()
        assert _my_company("T5") is None
    finally:
        _atlas.get_collection = _orig_get_collection2
        if _orig_default is None:
            os.environ.pop("DEFAULT_MY_COMPANY", None)
        else:
            os.environ["DEFAULT_MY_COMPANY"] = _orig_default
        _my_company_cache.clear()

    # --- render(no_my_company=True) appends the footer to evidence/none only -
    footer_none = render({"confidence": "none"}, "Weaviate", no_my_company=True)
    assert _NO_MY_COMPANY_FOOTER.format(c="Weaviate") in footer_none
    footer_evidence = render({
        "confidence": "evidence", "answer": "x",
        "citations": [{"quote": "q", "source_url": "https://x.io/p", "captured_at": ""}],
    }, "Weaviate", no_my_company=True)
    assert _NO_MY_COMPANY_FOOTER.format(c="Weaviate") in footer_evidence
    for confidence in ("error", "timeout", "busy", "cap"):
        no_footer = render({"confidence": confidence, "error": "boom"}, "Weaviate", no_my_company=True)
        assert _NO_MY_COMPANY_FOOTER.format(c="Weaviate") not in no_footer, confidence
    assert _NO_MY_COMPANY_FOOTER.format(c="Weaviate") not in render({"confidence": "none"}, "Weaviate")

    # --- daily cap: "busy" never reached the LLM, so it must not be charged;
    # "timeout" left an orphaned thread still burning quota, so it must be ----
    _daily_cap_state.update({"date": None, "count": 0})
    assert _daily_cap_room()
    _daily_cap_commit("busy")
    assert _daily_cap_state["count"] == 0, "busy must not consume a cap slot"
    for c in ("evidence", "none", "error", "timeout"):
        _daily_cap_commit(c)
    assert _daily_cap_state["count"] == 4, _daily_cap_state
    _daily_cap_state["count"] = SLACK_DAILY_ANSWER_CAP
    assert not _daily_cap_room(), "cap must stop the next answer"
    _daily_cap_state.update({"date": None, "count": 0})

    print("✅ slack.app self-check passed (offline — no network)")


if __name__ == "__main__":
    _self_check()
