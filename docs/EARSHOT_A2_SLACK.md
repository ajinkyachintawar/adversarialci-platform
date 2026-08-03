# A2 — Slack `/vs` slash command (EarshotCI)

> **Handoff note.** Self-contained; assumes no memory of the session that produced
> it. Every fact verified 2026-08-03. The narrative history of Phases 0–1 lives in
> `docs/EARSHOT_PHASE_0_1.md` (in-repo, committed, authoritative).

---

## Context

**The product.** A rep is on a call. The buyer says *"Weaviate is cheaper."* The
rep types `/vs weaviate they said they're cheaper` in Slack and gets a quote from
Weaviate's own pricing page, with a link and a capture date. Governing principle,
from `docs/PLAN_A.md`: **we surface evidence, we do not assert facts.** Honest
abstention — "no evidence found on their own pages" — is the differentiator
incumbents (Klue, Crayon, Kompyte) structurally cannot offer, because a
battlecard always has content.

**Where we are.** Phase 0 (corpus) and Phase 1 (`answer()` + `POST /api/ask`) are
complete and measured: **abstention 95%, answer rate 100%** on a 44-query eval
(`eval/results/abstention_eval_gptoss120b_*.json`, `contaminated: false`).
Everything works — but only through a JSON endpoint nobody calls. **A2 is the
first surface a rep can touch**, and the last PLAN_A step before A3 (real use)
and A4 (eval on real questions).

**Why the async ack is mandatory, not stylistic.** Measured latency is median
13–20s, p95 ~28s, max 31–49s. Slack requires a response in 3s. This was measured,
not assumed, and is why A2 waited until `answer()` was trustworthy.

**Working environment.** Branch `earshot` in the worktree `~/EarshotCI` (same repo
as `~/ad-ci`, pushed to `origin/earshot`). `.venv` is symlinked to
`~/ad-ci/.venv`. `config.py` hardcodes `DB_NAME = "war_room"`, so both folders
share one Atlas database — the worktree isolates code only, never data.

---

## Scope decisions (taken — do not re-litigate)

| Decision | Choice | Consequence |
|---|---|---|
| Slack auth | **`response_url` only, NO `SLACK_BOT_TOKEN`** | One secret, no OAuth scopes, no install flow. Valid 30 min / 5 uses; we use it once ~30s later. Deliberate deviation from `PLAN_A.md`. |
| Companies | **MongoDB, Pinecone, Weaviate only** | The only three with measured quality (445/207/169 chunks). The other 15 are unmeasured; Vald has 9 chunks and would abstain always. Expanding must be a **data change, not a code change**. |
| Quota cap | **Dev guard, env-overridable** | The ~40/day ceiling is *our* free-tier constraint, not a product feature — customers bring paid Groq keys. It exists to stop a runaway loop eating the day's budget. |
| Testing | **ngrok locally, then Render** | Fast iteration, quota spent deliberately. Free ngrok URLs change on restart — expect to re-paste the Slack Request URL. |

---

## Architecture

### The one fact that makes this cheap

`auth_middleware.py:70` returns `await call_next(request)` for **any path not
starting with `/api/`**. Mounting at `POST /slack/vs` is therefore unauthenticated
with **zero middleware changes**. Do *not* add it to `_PUBLIC_PATHS` — that set is
exact-match and only consulted for `/api/` paths, so putting it there is
misleading dead config.

### Files

**New `slack/app.py`** — the whole feature in one file, structured exactly like
`earshot/answer.py`: module docstring with the run recipe, constants carrying
their measured rationale, **pure functions first, I/O below**, `_self_check()`
under `if __name__ == "__main__"`.

```
constants
pure:  verify_slack_signature, parse_command, norm_company,
       resolve_competitor, esc, render
i/o:   _known_companies, _my_company, _run_answer, _deliver, _log, slack_vs
router = APIRouter()
```

Everything above the I/O line takes its inputs as arguments — no module-level DB
reads, no `os.environ` at import time. That is what makes Phase 1 verifiable with
no Slack, no Mongo, no Groq.

**New `slack/__init__.py`** — empty. Verified: `pip show slack` → not found, no
name conflict.

**Modified `server.py`** — two lines (import + `app.include_router`), plus
`"source": "api"` on the existing `ask_log` write so Slack and API traffic are
distinguishable. `POST /api/ask` (~line 547) is the template to copy.

**Modified `render.yaml`** — `SLACK_SIGNING_SECRET`, `DEFAULT_MY_COMPANY` as
`sync: false` with comments matching the file's existing style.

**Modified `db/atlas.py`** — one line inside the existing never-fatal try in
`_ensure_indexes()`: `db["slack_workspaces"].create_index("team_id", unique=True)`.

### Dependencies

**None to add.** `httpx` 0.28.1 is installed and already used async in
`auth_middleware.py`; `hmac` / `hashlib` / `urllib.parse` are stdlib.

### The `answer()` contract being consumed

```python
from earshot.answer import answer
result = answer(question, competitor, my_company=None, k=6)
# confidence ∈ {"evidence", "none", "error"}
# citations: [{"quote", "source_url", "captured_at"}]   captured_at like "18 Jul 2026"
# "error" key present ONLY when confidence == "error"
# seconds: float, always present
```

Three hazards, each handled below:

1. **No internal timeout.** Worst case ~6 min when Groq rate-limits (2 `call_llm`
   calls × model fallback × key rotation × 3×20s TPM retries).
2. **`confidence == "evidence"` can carry `citations == []`** in a rare path. An
   uncited paragraph is precisely the assert-a-fact failure this product exists to
   prevent — normalize to `"none"` before rendering.
3. **Company matching is exact and case-sensitive** (`retrieve()` uses
   `{"company": company}` as a hard Atlas filter). `docs/EARSHOT_PHASE_0_1.md`
   states explicitly that normalization belongs in the Slack handler.

---

## Phases

Each phase is verifiable by running one command and reading its output — written
so a cheaper model can implement them one at a time.

### Phase 1 — pure core + self-check (no route, no I/O)

**Signature verification** (Slack v0):
```python
base = b"v0:" + timestamp.encode() + b":" + raw_body   # BYTES, never re-encoded
expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
return hmac.compare_digest(expected, signature)
```
- Check `abs(now - ts) > 300` **before** the HMAC — a replay then costs no crypto,
  and `abs()` also catches a clock running ahead.
- Missing secret or headers → `False` (fail closed). Log the missing-secret case
  loudly once; otherwise a Render env typo presents as "Slack is broken".
- Never `raw.decode()` then re-encode for the HMAC — one non-UTF-8 byte silently
  breaks every signature.
- On failure return 401 without distinguishing stale-timestamp from bad-HMAC (free
  oracle); do distinguish them in the server log.

**Competitor resolution** — generic longest-prefix over a **list**, so growing to
the other 15 companies is a data change:
```python
ANSWERABLE = ["MongoDB", "Pinecone", "Weaviate"]      # expand HERE, not in code
ALIASES = {"mongo": "MongoDB", "mongodb atlas": "MongoDB"}   # keep tiny
```
`resolve_competitor(text, known) -> (canonical|None, question, reason)`,
`reason ∈ {"ok","no_match","no_question","help"}`. Longest-prefix (up to 4 tokens)
so multi-word names work when the list grows — 7 of the 18 corpus companies are
multi-word. An alias may **never** resolve to a company absent from `known`.

**Rendering** — mrkdwn `text`, not Block Kit (`response_url` takes
`{"text": ...}`; Blocks add a schema for identical output). One shared constant
carries the principle across every non-answer outcome:
```python
_NOT_ABSTENTION = "Nothing was checked — this is a tool problem, not an answer about {c}."
```

**`_self_check()`** (~120 lines, <50ms, zero network):
- Signature: valid; body tampered one byte; wrong secret; ts 301s old; ts 301s in
  the *future*; missing header; empty secret. All but the first → `False`.
- Resolution table: `"weaviate they said…"` → ok; `"MONGODB pricing?"` → ok;
  `"mongo how much"` → alias; `"  weaviate  are they cheaper "` → ok;
  `"weaviate"` → `no_question`; `"notacompany x"` → `no_match`; `"help"` → help.
- Safety: with `known=["Weaviate"]`, `"mongo x"` → `no_match` (aliases cannot
  invent companies).
- **Product-principle guard:** for each of `error`/`timeout`/`busy`/`cap`, assert
  `"no evidence" not in text.lower()` AND `_NOT_ABSTENTION` present. This pair is
  the strongest guard against the one lie this product cannot tell.
- `evidence` with `citations == []` renders as the `none` message.
- `esc("A & B <c>")` → `"A &amp; B &lt;c&gt;"`.

**Accept:** `.venv/bin/python -m slack.app` prints a pass line, exits 0, network
unplugged.

---

### Phase 2 — route, signature gate, 3s ack (stub answer)

Add `router`, `slack_vs`, `_known_companies()` (cached `distinct()`, 5-min TTL,
intersected with `ANSWERABLE`), `_TASKS`, and a stub `_answer_and_deliver`.
Register the router in `server.py`.

Read the body exactly once — required for HMAC, and sidesteps `Form()`:
```python
raw = await request.body()
fields = {k: v[0] for k, v in parse_qs(raw.decode(), keep_blank_values=True).items()}
```

**Hold strong task references.** The loop holds `create_task` results only weakly;
without a reference the task can be garbage-collected mid-flight and the rep gets
silence forever. `server.py:349` has this bug today — copy the shape, fix it:
```python
task = asyncio.create_task(...); _TASKS.add(task); task.add_done_callback(_TASKS.discard)
```
`_answer_and_deliver` wraps its entire body in `try/except Exception` and delivers
an error render — an exception in a fire-and-forget task is a silent void.

**Accept** (uvicorn running, `SLACK_SIGNING_SECRET` set):
1. signed curl → 200 in <200ms with the "Checking…" ack
2. one byte flipped → 401
3. timestamp 6 min old → 401
4. `text=notacompany what do they charge` → **200** with a friendly message listing
   the answerable companies (never an HTTP error — explicit PLAN_A criterion)
5. `git diff --stat auth_middleware.py` empty

---

### Phase 3 — real `answer()`, lock, timeouts, rendering

Three separate risks, three mechanisms. Conflating them is where this goes wrong.

**(a) Serialize LLM work with a lock held in thread-space.**
```python
_LLM_LOCK = threading.Lock()   # ponytail: global lock. Groq quota is the
                               # binding constraint, not throughput.
def _run_answer(...):
    if not _LLM_LOCK.acquire(timeout=SLACK_QUEUE_WAIT_S):   # 25
        return {"confidence": "busy"}
    try:     return answer(question, competitor, my_company)
    finally: _LLM_LOCK.release()
```
Acquired **inside the worker thread**, not around the `await` — so an orphaned
thread still owns its slot until it genuinely finishes. `heads/llm.py`'s
`_key_idx` / `_last_call_at` / `call_count` are unsynchronized module globals, and
`_pace_for()` sleeps a computed inter-call gap on entry; two concurrent callers
race the pacer into a 429 storm. One lock makes `llm.py`'s existing
single-threaded assumption true instead of rewriting it.

**(b) Backstop timeout.** `asyncio.wait_for(asyncio.to_thread(...), timeout=90)`.
`wait_for` **cancels the coroutine, not the OS thread** — an orphaned `answer()`
keeps running and burning quota; the thread-space lock is what stops orphans
*stacking*. 90s exceeds `ASK_TIMEOUT_S = 45` deliberately: no browser to 504, and
a Slack message at 70s beats nothing at all.

**(c) Daily cap** — module-level `(date, count)`, `SLACK_DAILY_ANSWER_CAP = 40`,
env-overridable. In-process state dies on redeploy; accept and comment it.

**Six renders.** `evidence` → `in_channel`; all others → `ephemeral`.
- `evidence`: one attributed paragraph, then each citation as `> "quote"` +
  `<url|host/path>` · date. Cap 4 citations, 300 chars/quote. Omit the date
  separator entirely when `captured_at == ""` (its documented empty fallback).
- `none`: must say **what was searched**, that this **is a result not a bug**, and
  give a next action. This message decides whether reps keep using the tool.
- `error`: visually obvious against `none` — `:warning:`, no `:mag:`, includes the
  `error` key text. **Must never read as "no evidence."**
- `timeout` / `busy` / `cap`: all carry `_NOT_ABSTENTION`.

If `response_url` is absent, `print()` the render instead of posting — two lines,
and local curl testing then needs no Slack at all.

**Accept:** local curl produces one render for each of `evidence` (Weaviate
pricing), `none` (ask Weaviate something it doesn't publish), `error` (unset
`GEMINI_API_KEYS`), `timeout` (budget → 1s), `busy` (two concurrent curls,
`SLACK_QUEUE_WAIT_S` → 1). Self-check still passes. Two concurrent requests show
**serialized** Groq calls — no interleaved `🔑 429` rotation in the log.

---

### Phase 4 — `slack_workspaces` + `ask_log`

`_my_company(team_id)`: `slack_workspaces.find_one({"team_id": ...})` →
`DEFAULT_MY_COMPANY` env → `None`. Cached 5 min; DB failure → `None`, never fatal.
`answer()` handles `my_company=None` natively (skips the comparison retrieval), so
**unconfigured degrades rather than fails** — add a footer line when it's `None`.

No setup slash command: one `insertOne` in Atlas, documented —
`{"team_id": "T…", "my_company": "MongoDB"}`.

**Reuse `ask_log`.** PLAN_A's A4 says "take 20 real questions from `ask_log`", and
after A3 Slack *is* where the real questions are; splitting collections would hide
the only traffic that matters. Add `source: "slack"`, `team_id`, `slack_user_id`,
`channel_id`, `raw_text` (the unparsed `/vs` text — the only way to debug
resolution), `resolved_via`.

Log **every** terminal outcome, including those that never reach `answer()`:
`confidence` gains `"unknown_competitor"`, `"busy"`, `"cap"`, `"timeout"`. A4
filters `confidence in {"evidence","none"}` for clean rates while resolution
failures stay visible — that is the signal telling you which aliases to add. Wrap
the write in `try/except`; the rep's answer is the product, the log is for A4.

**Accept:** after one local curl, `ask_log.find_one({"source":"slack"})` has
`raw_text`, `team_id`, `resolved_via`. With no workspace doc the answer still
returns with the "no us configured" footer; after inserting one, the footer
disappears and `my_company` is set.

---

### Phase 5 — real Slack

Slack app manifest + slash-command registration. `SLACK_SIGNING_SECRET` and
`DEFAULT_MY_COMPANY` into `render.yaml`. Dry run via `ngrok http 8000` → Request
URL `https://<id>.ngrok-free.app/slack/vs`, then repoint at Render.

**Accept — the four PLAN_A criteria:** `/vs weaviate they said they're cheaper`
returns a cited answer; bad signature → 401; replay >5 min → rejected; unknown
competitor → friendly message rather than a failure.

---

## Verification

```bash
cd ~/EarshotCI
.venv/bin/python -m slack.app          # offline self-check, no network
.venv/bin/python -m earshot.answer     # unchanged — must still pass
.venv/bin/python -m heads.llm          # unchanged — must still pass
.venv/bin/uvicorn server:app --port 8000
```
Then the signed-curl recipe (build `v0=` with
`openssl dgst -sha256 -hmac "$SLACK_SIGNING_SECRET"`), omitting `response_url` so
the render prints to stdout.

**Done when:** every quote in a Slack citation appears verbatim on the linked
page; `error` is visually distinct from `none` in a real client; an unknown
competitor gets a friendly reply; a bad signature 401s; `ask_log` holds a
`source: "slack"` document.

---

## Risks

1. **Render free tier spins down on idle.** Cold start is 30s+, so *the first
   `/vs` after any quiet period fails* with Slack's `operation_timeout` before our
   code runs. Most common real-world failure, and invisible locally. Mitigation:
   paid instance, or a cron pinging `/health` every 10 min. **Decide before A3.**
2. **PLAN_A's "under 10 seconds" A2 criterion is not achievable** on a free Groq
   key — median is 13–20s. Fix the spec, not the measurement; the ack copy should
   promise 20–30s.
3. **A redeploy silently kills in-flight answers** — rep gets "Checking…" then
   nothing, forever. Accept for A2 (30s window); don't deploy during a demo.
4. **A 6-minute worst-case `answer()` blocks the queue.** The bounded lock turns
   that into a *distinct* "busy" message. If "busy" ever rendered as "no
   evidence", a Groq stall would look like an empty corpus — exactly the confusion
   this product exists to prevent.
5. **Groq daily quota** (~16–40 LLM-reaching answers/day/model/key) makes our own
   A3 week quota-limited before anything else.

---

## Out of scope

`SLACK_BOT_TOKEN` / `chat.postMessage` / threading; the other 15 companies; a
`/vs-setup` command; any UI; CRM; change alerts; multi-tenancy beyond `team_id`;
MCP exposure. Touch nothing in `court/`, `heads/buyer.py`, `heads/analyst.py`,
`claims/`, `ui/`.

---

## Inherited open items (not blocking A2)

- **70B vs `gpt-oss-120b` is unresolved** — blocked on Groq daily tokens (all 3
  keys at ~98.7K/100K on 2026-08-03). Re-run when the window rolls:
  `GROQ_NO_FALLBACK=1 .venv/bin/python -u -m eval.abstention_eval llama70b_depunct`
  then the same pinned for `EARSHOT_MODEL=openai/gpt-oss-120b`. Preflight refuses
  to start when quota is short, so a blocked attempt costs nothing. The 95%/100%
  result still carries its confound: gate AND model both changed in that run.
- **Attributed framing** (measured, zero quota): 70B 60% vs gpt-oss-120b 95% on 20
  shared answers. If gpt-oss wins, change `MODEL` in `earshot/answer.py` **and**
  reorder `MODEL_FALLBACKS` in `heads/llm.py` — the 70B then leads *its* chain,
  having the larger TPM budget.
- `call_llm` is now `@lru_cache`d per key; verify no socket growth in the
  long-lived server process.
