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

#### Phase 1 result — DONE 2026-08-05

`slack/__init__.py` + `slack/app.py` (pure layer + `_self_check()`, stdlib only,
no route/DB/httpx/env). Accept criterion met; `earshot.answer` and `heads.llm`
self-checks unchanged and still pass.

Implemented by a worker model, then audited against an **independent** probe the
implementer never saw (26 checks, kept out of the repo — the four real defects it
caught are now in `_self_check()`, which is the committed test). Everything the
plan named held on the first pass: HMAC over raw bytes (a non-UTF-8 body still
verifies), the timestamp window, alias-cannot-invent-a-company under a shrunk
`known`, and the not-abstention guard — the last one also with no `error` key, an
unknown `confidence`, and an empty dict.

Four defects found and fixed:

1. **A 500 where a 401 was promised.** `hmac.compare_digest` raises `TypeError`
   on a non-ASCII `str`, and `X-Slack-Signature` is attacker-controlled. Now
   compared as bytes. The self-check missed it because it only ever fed
   well-formed hex — *the hostile input at a trust boundary is malformed, not
   wrong*.
2. **Bare `/vs` returned `no_match`** — the likeliest first interaction in the
   product answered with "not a company I recognise". Now `help`.
3. **`/vs weaviate, are they cheaper` returned `no_match`.** Punctuation on the
   company token killed the match, and no alias list fixes that
   combinatorially. `norm_company` now strips `.,:;!?` per token — prefix
   matching only, the question remainder is still sliced from the raw text, so
   `"MONGODB pricing?"` still yields exactly `"pricing?"`.
4. **`source_url` was the one unescaped field in `render`** while the answer and
   quote were escaped. A `|` broke `<url|label>` into extra segments.

One reported failure was the *audit's* bug, not the code's: an exact `±300s`
boundary assertion trips on the wall-clock tick between signing and checking.
The `> 300` comparison is correct as written.

**Carried into Phase 3, deliberately not fixed here:** `render()` returns a bare
`str` and so carries no `in_channel` / `ephemeral` signal. That is the caller's
decision (see "Six renders"), and widening the Phase 1 contract to anticipate it
would have been speculative.

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

#### Phase 2 result — DONE 2026-08-05

I/O layer appended below the pure functions in `slack/app.py` (`_known_companies`,
`_TASKS`, stub `_answer_and_deliver`, `_deliver`, `router`, `slack_vs`), plus 8
lines in `server.py` (import, `include_router`, `"source": "api"` on `ask_log`).
`auth_middleware.py` untouched, as designed.

Audited with an independent signed-curl harness (26 requests) the implementer
never saw. All five accept criteria met, and:

| Probe | Result |
|---|---|
| Valid signed request → ack | 200, **0.065s** warm (Slack's budget is 3s) |
| 8 gate cases: flipped byte, wrong secret, missing sig, missing ts, ±6 min, non-ASCII sig, garbage ts | all 401, all **0.065–0.066s** — no timing oracle either |
| Log distinguishes stale-vs-bad while the response does not | holds (6 bad / 2 stale) |
| 7 resolution outcomes incl. unknown competitor | all **200**, never an HTTP error |
| 4 malformed signed bodies (empty, non-form, invalid UTF-8, duplicate keys) | no 500s |
| 5 concurrent requests | **10/10** background tasks delivered — the strong-ref fix works |

Five defects found and fixed:

1. **The self-check hit the network while printing "offline — no network".** The
   new `_known_companies` assertion called real Atlas (`✅ Atlas connected`
   appeared above the pass line) and its comment claimed the process had no
   Mongo connection. A pass line that asserts something untrue is worse than a
   missing test. Now monkeypatches `db.atlas.get_collection` — importing the
   module opens no socket, it connects lazily inside `get_collection()`.
2. **Sync pymongo blocking the event loop.** `db/atlas.py` is the sync driver,
   and `_known_companies()` was called directly inside `async def slack_vs`.
   Measured 0.41s cold vs 0.066s warm — on a Render cold start that eats the 3s
   budget and stalls every concurrent request, defeating the reason the ack
   architecture exists. Now `await asyncio.to_thread(...)`, matching `/api/ask`.
3. **An empty corpus∩ANSWERABLE presented a tool problem as an answer.** Wrong
   DB, empty collection or a renamed field made every rep see "I don't recognize
   that competitor... (none configured)". Now degrades to `ANSWERABLE` with a
   loud log, exactly like a DB failure — the distinction this product is built on.
4. `no_question` echoed raw user `text` while escaping `competitor`. Now `esc`'d.
5. `_deliver` ignored a non-2xx from `response_url`, so an expired URL looked
   identical to success and the rep got silence forever — the precise failure
   `_TASKS` exists to prevent. Now logs status and body.

**Residual, accepted:** the first request after a cold cache still costs ~0.45s
of the 3s budget on the Atlas `distinct()`. It no longer blocks other requests,
which was the actual hazard. Revisit only if Render's cold Atlas latency makes
it bite — see Risk 1, which dominates it anyway.

**Known gap in the offline check, by design:** `_self_check()` is pure, so it
cannot see the route boundary. The worker's first draft 500'd because `parse_qs`
returns lists and `parse_command` expects scalars; only a live curl caught it.
Phase 3's accept criteria must stay curl-based for the same reason.

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

#### Phase 3 result — DONE 2026-08-05

All six outcomes verified against **real rendered text**, total spend **3
LLM-reaching answers**. `git diff --stat` touched only `slack/app.py`.

| Outcome | How forced | Result |
|---|---|---|
| `evidence` | Weaviate serverless pricing, real call | `in_channel`, attributed framing, 4 citations (cap hit exactly), dated `1 Aug 2026` |
| `none` | Weaviate legal-department headcount, real retrieval | `ephemeral`, abstention gate fired before any LLM call |
| `error` | `embed_query` → `None` (see correction below) | `:warning:`, carries the embedder's "This is NOT an empty corpus" text |
| `timeout` | stubbed 6s sleeper, `SLACK_ANSWER_TIMEOUT_S=1` | rep answered at **1.00s** |
| `busy` | lock pre-held, `SLACK_QUEUE_WAIT_S=1` | gave up at **1.13s** |
| `cap` | `SLACK_DAILY_ANSWER_CAP=0` | never reached `answer()` |
| serialization | 2 concurrent real requests, default 25s wait | both cited; **0** `🔑`/`429` events, 0 tracebacks |

The product-principle guard was re-checked against live output rather than
fixtures: none of `busy`/`error`/`timeout`/`cap` contains "no evidence", and all
four carry `_NOT_ABSTENTION`.

**The orphaned thread is real, and now measured.** With a 1s timeout over a 6s
call, the rep was answered at 1.00s while the OS thread ran on to 6.01s — visible
because `asyncio.run()` blocks in `shutdown_default_executor()` joining it. This
is exactly what the plan warns about: `wait_for` bounds *how long a rep waits*,
never *how much quota is spent*, and the thread-space lock is the only thing
stopping orphans from stacking.

**Correction to this phase's own accept criteria.** "`error` (unset
`GEMINI_API_KEYS`)" does **not** exercise the error path. With no key,
`embed_texts` raises a bare `IndexError` from `GEMINI_API_KEYS[_key_idx]`, which
`answer()` does not catch (it catches only `RetrievalUnavailable`), so the result
is an unhandled exception rather than `confidence == "error"`. The Slack layer
still degrades correctly — `_answer_and_deliver`'s outer `try/except` renders an
error — but via the generic path, not the designed one. The *real* production
failure is quota exhaustion: `embed_texts` returns `None` → `embed_query` returns
`None` → `retrieve` raises `RetrievalUnavailable` → `confidence == "error"`. That
is what was tested. **Use `embed_query → None` for this criterion, not an unset
key.**

**Latent bug found while testing, left for a separate change** (outside A2's
scope): `ingest/embedder.py:_require_key()` exists solely to turn the missing-key
case into a readable error — its docstring names the bare `IndexError` verbatim —
and it is **never called from anywhere**. Wiring it into `embed_texts` is one line.

**Fixed during audit:** `_daily_cap_ok()` charged a slot before the outcome was
known, so a `busy` result — which makes zero LLM calls — consumed budget. A burst
of lock contention could have eaten the whole day's cap without a single Groq
call, in the one mechanism whose entire job is counting quota. Split into
`_daily_cap_room()` (read-only) and `_daily_cap_commit(confidence)`, which skips
`busy` and still charges `timeout` (whose orphan genuinely is spending).

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

#### Phase 4 result — DONE 2026-08-05

`_my_company` (5-min cache **per team_id**), `_log_ask`/`_log_ask_safe`,
`resolved_via` threaded through `resolve_competitor`, the footer, and one index
line in `db/atlas.py`. **0 LLM calls spent** — every test used a question that
abstains before the LLM gate.

All four accept criteria met. Verified against the live shared Atlas DB:

| Probe | Result |
|---|---|
| No workspace doc | answer returned, footer present |
| After inserting `{"team_id":"T1","my_company":"MongoDB"}` | footer gone, `my_company: "MongoDB"` in the log |
| `ask_log` doc shape | `source`, `team_id`, `slack_user_id`, `channel_id`, `raw_text`, `resolved_via` all present |
| Outcomes that never reach `answer()` | all logged: `unknown_competitor`, `help`, `no_question` |
| `resolved_via` | `"direct"` / `"alias"` / `None`, matching how the name was matched |
| Test data cleanup | 1 workspace + 5 `ask_log` rows deleted; only the 2 pre-existing `source: "api"` rows remain |

**Fixed during audit — the footer could lie.** `_my_company` skipped the
`DEFAULT_MY_COMPANY` env fallback when the DB threw, so an Atlas blip made a
workspace that *is* configured render "nobody has told me which company we are".
That is a tool problem dressed up as a settings statement — the same class of
error as Phase 2's empty-intersection bug. `DEFAULT_MY_COMPANY` is a deploy-time
constant that needs no DB to read, so a DB failure now falls through to it.
Demonstrated before and after; self-check assertion updated (it had encoded the
old behaviour as correct).

**Also fixed:** the footer pointed reps at `docs/EARSHOT_A2_SLACK.md Phase 4`. A
salesperson in Slack cannot act on a repo path — it now says to ask their admin.

**Judgement call, kept:** `help` and `no_question` are logged under their own
confidence values rather than folded into `unknown_competitor`. A4's signal is
"which aliases should exist", and someone typing `/vs help` is not a failed
alias lookup — merging them would dilute the one number this log exists to
produce.

**Setup is one manual insert**, no `/vs-setup` command:
```js
db.slack_workspaces.insertOne({team_id: "T…", my_company: "MongoDB"})
```

---

### Phase 5 — real Slack

Slack app manifest + slash-command registration. `SLACK_SIGNING_SECRET` and
`DEFAULT_MY_COMPANY` into `render.yaml`. Dry run via `ngrok http 8000` → Request
URL `https://<id>.ngrok-free.app/slack/vs`, then repoint at Render.

**Accept — the four PLAN_A criteria:** `/vs weaviate they said they're cheaper`
returns a cited answer; bad signature → 401; replay >5 min → rejected; unknown
competitor → friendly message rather than a failure.

#### Phase 5 — code ready 2026-08-05, install is manual

`slack/manifest.yaml` and the two `render.yaml` entries are committed. The rest
of this phase happens in Slack's and Render's dashboards and **cannot be done or
verified from here** — the steps below are the runbook.

Criteria 2 and 3 (bad signature → 401, replay → rejected) were already proven in
Phase 2 against 8 hostile cases, all returning 401 in 0.065–0.066s with no timing
oracle. What real Slack adds is criteria 1 and 4 end to end.

**1 — create the app.** https://api.slack.com/apps → *Create New App* → *From an
app manifest* → pick the workspace → paste `slack/manifest.yaml`. Copy the
**Signing Secret** from *Basic Information*; that is `SLACK_SIGNING_SECRET`.

**2 — local dry run.**
```bash
SLACK_SIGNING_SECRET=<secret> .venv/bin/uvicorn server:app --port 8000
ngrok http 8000
```
Put `https://<id>.ngrok-free.app/slack/vs` in *Slash Commands → /vs → Request
URL*, then *Install to Workspace*. Free ngrok URLs change on every restart —
expect to re-paste. Run the four criteria in a real channel.

**3 — tell it who you are.** One insert, no setup command; `team_id` is in the
`ask_log` row your first `/vs` just wrote:
```js
db.slack_workspaces.insertOne({team_id: "T…", my_company: "MongoDB"})
```
Without it the answer still works and says the comparison is missing.

**4 — repoint at Render.** Set `SLACK_SIGNING_SECRET` (and optionally
`DEFAULT_MY_COMPANY`) in the Render dashboard — both are `sync: false`, so
`render.yaml` declares them but never carries the value. Change the Request URL
to `https://<service>.onrender.com/slack/vs` and re-run the four criteria.

**Watch on first real use:** `ask_log` rows with `confidence:
"unknown_competitor"` are the alias backlog — `raw_text` shows exactly what reps
typed. That feedback loop is the reason Phase 4 logs non-answers at all.

##### Risk 1 — RESOLVED 2026-08-05

Render's free tier sleeps on idle, so the first `/vs` after a quiet period would
fail Slack's 3s timeout during a 30s+ cold start — before any of our code ran.
**Decision: paid instance ($7/mo Starter), matching what AdversarialCI already
runs on.** No cron ping needed, and no `/health` keep-alive hack to maintain.
This was the plan's most likely real-world failure and it is invisible locally,
so paying for always-on removes the single biggest A3 risk for the price of a
coffee. Set `plan: starter` on the service, or switch it in the dashboard.

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

1. ~~**Render free tier spins down on idle.**~~ **RESOLVED 2026-08-05 — paid
   Starter instance**, same as AdversarialCI. Cold start would have made *the
   first `/vs` after any quiet period fail* with Slack's `operation_timeout`
   before our code ran: the most likely real-world failure, and invisible
   locally. See Phase 5 above.
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

- ~~**70B vs `gpt-oss-120b` is unresolved**~~ **RESOLVED 2026-08-04 (`74d7ade`)**
  — `openai/gpt-oss-120b` is now the primary `MODEL`, and the 70B leads its own
  fallback chain. Decided on **attributed framing (65% → 92%)**; the abstention
  and answer-rate gaps were one query each at n=20/24, i.e. noise. Full
  three-way table and the accepted costs are in `docs/EARSHOT_PHASE_0_1.md`.
  **What this changes for A2:** the ack copy should still promise 20–30s (the
  new primary measured 17.0s mean vs the 70B's 10.1s — slower, and accepted,
  because free-tier queueing dominates and attribution is the product).
- `call_llm` is now `@lru_cache`d per key; verify no socket growth in the
  long-lived server process.
