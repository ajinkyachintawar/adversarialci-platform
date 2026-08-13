# AdversarialCI

**Competitive intelligence that has to show its evidence.**

Two LLM advocates argue for their vendor from retrieved evidence, a judge decides, and every
claim that reaches the verdict has been checked against a real source chunk first. Claims that
cite nothing are dropped before anyone reads them.

**Live:** [adversarialci-platform.vercel.app](https://adversarialci-platform.vercel.app)
**Paper:** *AdversarialCI: A Buyer-Adaptive Multi-Agent Framework for Evidence-Grounded Competitive
Intelligence* — ScienceOpen preprint, Feb 2026, [10.14293/PR2199.003028.v1](https://doi.org/10.14293/PR2199.003028.v1)

---

## The problem

Ask an LLM to compare two vendors and you get fluent, confident, unfalsifiable prose. It reads
like analysis. You cannot tell which parts came from a pricing page and which came from the
model's priors, and neither can the model.

AdversarialCI makes that separation structural rather than optional:

1. **Evidence is retrieved before anything is argued.** No claim originates in the model.
2. **Every claim carries evidence IDs**, and a deterministic gate drops any claim whose IDs do not
   resolve to a real stored chunk. That gate makes zero LLM calls.
3. **The verdict is checked against itself** by code, not by another model. If the judge declares a
   winner it did not actually support, the check fires.
4. **Confidence is computed, never generated.** The judge's own confidence number is discarded and
   recomputed deterministically from the per-dimension results.

---

## What it does

Pick a mode, describe yourself, name the vendors. You get a verdict with per-dimension reasoning
and a source URL behind each claim.

| Mode | Question it answers | Output |
|---|---|---|
| **Buyer** | Which of these should I actually buy, given my budget, scale and priority? | Recommendation, per-dimension winner, confidence |
| **Seller** | How do I position against them, and what objections will I hit? | Battlecard with objections and cited rebuttals |
| **Analyst** | How do these compare without a buyer's thumb on the scale? | Neutral per-dimension comparison |

There are **two surfaces over the same evidence corpus**: the full adversarial session above, and
`POST /api/ask` for a single cited question with an explicit abstention path — see
[Ask](#ask--single-question-answers-with-a-real-abstention-path).

The buyer profile is not decoration — it changes which evidence is weighted and which dimensions
decide the verdict. A cost-led buyer and a compliance-led buyer get different answers from the
same corpus, which is the "buyer-adaptive" part of the paper.

**Coverage — 18 vendors across 3 verticals:**

- **Database (9):** MongoDB, Pinecone, Weaviate, Apache Cassandra, Amazon DocumentDB, Qdrant,
  Milvus, ChromaDB, Vald
- **Cloud (5):** AWS, Microsoft Azure, Google Cloud, Oracle Cloud, DigitalOcean
- **CRM (4):** Salesforce, HubSpot, Microsoft Dynamics 365, Zoho CRM

---

## Architecture

There are **two pipelines in this repo**. This is deliberate and the reason is documented below —
please read the note before assuming the newer one is what serves the live site.

### v1 — the orchestration path (currently live)

A LangGraph `StateGraph` with conditional edges, so a session skips work it does not need:

```
db_check ──needs_scraping?──┬── scrape ──> source_router ──> verifier ──┬── court ──> court_session ──> END
                            └── verify ─────────────────────>          └── end ────────────────────> END
```

- **`db_check`** — is the stored evidence for these companies fresh enough to reuse? If yes, the
  entire scrape phase is skipped.
- **`source_router`** — fans out across six source agents: Tavily search, Hacker News, direct
  pricing-page scrape, GitHub, engineering blogs, and migration/complaint queries.
- **`verifier`** — quality gate before anything reaches the debate.
- **`court_session`** — builds the challenge from the buyer profile, routes each evidence bullet to
  a dimension, runs one advocate per company, then a judge deliberates and a verdict is processed.

Evidence bullets are weighted by provenance through a `SOURCE_PRIORITY` table — a scraped pricing
page outranks a search-engine snippet, because one is the vendor stating its own terms and the
other is somebody's blog post about them.

### v2 — the trust core (`AGENTS_V2=1`)

This is the part the paper is about. It replaces free-form argument with structured claims that
must survive verification.

```
retrieve (per company × dimension)
        │
        ▼
extract_claims          ← LLM emits structured claims, each citing evidence_ids
        │
        ▼
gate_claims             ← DETERMINISTIC, ZERO LLM CALLS
        │                 every evidence_id must resolve to a real content_hash
        │                 in rag_chunks for that company, or the claim is dropped
        ▼
mode head               ← buyer/seller/analyst; buyer runs a 2-round debate
        │                 (claim selection + attack, then rebuttal) before judging
        ▼
recompute_confidence    ← judge's own number discarded; confidence recomputed as
        │                 round(100 × dimensions_won_by_winner / total_dimensions)
        ▼
consistency.check       ← DETERMINISTIC post-hoc checks:
        │                 · every cited evidence_id is valid
        │                 · the declared winner actually won the most dimensions
        │                 · the confidence matches the formula exactly
        │                 · no duplicated dimensions
        │                 · seller objections cite evidence from the right dimension
        ▼
one re-ask on failure   ← the failure text is quoted back verbatim to the model
        │
        ▼
persist (flagged `inconsistent: true` if it still fails)
```

**The design principle:** anything that can be checked by code is checked by code. The LLM
proposes; deterministic logic disposes. `claims/gate.py` and `heads/consistency.py` between them
contain no model calls at all, and both ship with self-checks that run without a database
(`python -m claims.gate`).

**It works.** On a real run (`eval/results/heads_smoke_buyer_20260721_193858.json`) the 70B judge
declared Pinecone the winner while Weaviate had actually won more per-dimension entries on a 3-3-1
split. The consistency checker caught it. That is the entire point of the layer.

### ⚠️ Why v2 is switched off in production

`render.yaml` sets `AGENTS_V2=0`, deliberately:

> v2 sessions run 8–10 minutes as an in-process background task with no checkpointing, so a deploy
> or restart kills them mid-flight.

Shipping a correctness layer on top of an execution model that loses work on every deploy would
trade one kind of wrongness for another. The fix is a checkpointed job worker, which is the next
phase of work, not a flag flip. Until then the live site runs v1 and this README says so rather
than letting the architecture diagram imply otherwise.

**What this means for anyone reading the code:** `claims/`, `heads/`, and the evaluation harness in
`eval/` are the most interesting parts of this repository, and they are not what is currently
serving traffic.

---

## Ask — single-question answers with a real abstention path

`POST /api/ask`, implemented in `earshot/answer.py`. Same corpus, different surface: instead of a
full adversarial session, ask one question about one competitor and get a short cited answer — or
an explicit refusal.

**Abstention here is not a confidence threshold on the output.** It is three independent gates,
any one of which can end the request:

1. **Score floor** — `SCORE_FLOOR = 0.85` on retrieval score. **Zero LLM calls.** If nothing
   retrieved clears the floor, the request is refused before a model is ever invoked. In the
   reference eval this alone saved 6 LLM calls outright.
2. **The model** — retrieval passes, the model answers with required verbatim citations.
3. **The citation gate** — every quoted span must match its source chunk. Unsupported quotes are
   dropped, and an answer left with no surviving citation becomes a refusal.

**Confidence is a three-state enum, not a number:** `evidence` | `none` | `error`.

The third state is the interesting one. A failed tool call is *not* an abstention — a system that
reports "no evidence" when what actually happened was a provider outage is lying about its own
corpus. Separating them means the abstention rate measures the corpus, and the error rate measures
the infrastructure.

### The quote matcher

Scraped pricing tables arrive without delimiters, and a model re-inserts the punctuation a human
would write. A byte-exact match therefore rejects genuine evidence. The fallback strips separator
punctuation — but never between two digits:

```python
_SEP_PUNCT = re.compile(r"(?<!\d)[.,:;\-–—*_|]|[.,:;\-–—*_|](?!\d)")

def _depunct(s: str) -> str:
    """_squash() with separator punctuation removed. Second-chance matching only."""
    return _SEP_PUNCT.sub("", _squash(s))
```

The lookarounds are the whole design. Without them `$56.94` and `$5.694` collapse to the same
string and two different prices become interchangeable — a matcher that recovers evidence by
making the numbers meaningless. It runs only after an exact match has already failed, and there is
an assertion in the module holding that boundary.

---

## Evidence layer

Retrieval sits on MongoDB Atlas Vector Search over a `rag_chunks` collection.

- **Embeddings:** Google `gemini-embedding-001`, 768 dimensions, cosine similarity.
- **Batching:** 20 per request with a 15-second pause — a 100-item batch returns an immediate 429,
  which is a measured limit rather than a guessed one.
- **Key rotation:** both Gemini and Groq rotate across a comma-separated key pool on 429, because
  the free tiers cap at roughly 1K embeddings per key per day.
- **Filtering:** a hard company filter is applied *before* vector search rather than after, so
  cross-vendor contamination is impossible by construction rather than by ranking.
- **Ingestion:** Firecrawl for scraping, Tavily for URL discovery, with a domain blocklist.
- **Identity:** every chunk carries a `content_hash`, which is what the citation gate resolves
  against. Citations are verified against stored content, not against a URL string.

---

## Evaluation

Every number below is reproducible from the harness in `eval/`, and every one is reported with
its limits.

### Retrieval — `eval/retrieval_eval.py`

16-query golden set (`eval/golden_retrieval.json`), full corpus:

| Metric | Result |
|---|---|
| hit@1 | 16/16 |
| hit@5 | 16/16 |
| MRR | 1.0 |

**Limit:** the golden set covers MongoDB and Pinecone only. This is not a corpus-wide retrieval
guarantee and should not be read as one. Extending it across verticals is open work.

### Citation survival — `eval/claims_eval.py`

Latest run (`claims_eval_20260721_184236.json`), 3 database companies:

| Metric | Result |
|---|---|
| Claims extracted | 83 |
| Claims surviving the gate | 83 (100%) |
| Dimension coverage | 100% |
| Pass bar (`SURVIVAL_BAR`) | 0.90 |

**Limit:** run against a 3-company, single-vertical fixture. Generalisation beyond it is unverified.

### Abstention — `eval/abstention_eval.py`

Two hand-authored sets with **different denominators**, which is the only way this measurement
means anything:

- **Positives** (`eval/golden_retrieval_v2.json`) — questions the corpus *can* answer.
  **Answer rate** = share of those actually answered.
- **Negatives** (`eval/golden_abstain.json`) — questions it structurally *cannot* answer: churn
  rate, headcount, roadmap, unredacted pen-test findings.
  **Abstention rate** = share of those correctly refused.

Reference run (`abstention_eval_clean_20260803_153010.json`), `llama-3.3-70b-versatile`,
`SCORE_FLOOR = 0.85`:

| Metric | Result |
|---|---|
| Answer rate (positives) | 83.3% |
| Correct abstention (negatives) | 90% |
| Refused at the score floor, no LLM call | 6 |
| Refused at the citation gate | 12 |
| Mean latency | 10.25s |

The two numbers move against each other. Any change that raises the answer rate while dropping
abstention has not improved the system, it has just made it more willing to guess — so both are
always reported together.

**On a contaminated run, the harness reports nothing.** In
`abstention_eval_llama70b_depunct_20260803_172542.json` six rows errored, and the output carries
`contaminated: true` with `answer_rate: null` and `abstention_rate: null` rather than a rate
computed over a partial denominator. A number derived from a run that half-failed is worse than no
number, because it looks usable.

### Scraper selection — `eval/scraper_benchmark.py`

Raw BeautifulSoup vs Firecrawl on pricing-page extraction, measured before choosing. Firecrawl won
and production moved to it. Results in `eval/results/scraper_benchmark_20260717_132352.json`.

### Judge prompt A/B — `eval/results/ab_judge_reason_*.json`

Changing one line of judge-prompt guidance moved mean reason length from 63.3 to 157.1 characters,
and to 133.1 after label-stripping. Verified stable with a same-prompt control re-run that produced
byte-identical output.

**Limit, stated in the result file itself:** mean reason length is a proxy for completeness, not a
correctness metric. It measures whether the judge explained itself, not whether it was right.

---

## Tech stack

| Layer | Choice |
|---|---|
| Runtime | Python 3.11, FastAPI, Uvicorn, Docker |
| Orchestration | LangGraph (`StateGraph` with conditional edges) |
| Generation | Groq — `llama-3.1-8b-instant` for extraction and debate, `llama-3.3-70b-versatile` for judging |
| Embeddings | Google `gemini-embedding-001` (768d) |
| Storage & retrieval | MongoDB Atlas + Atlas Vector Search |
| Ingestion | Firecrawl (scrape), Tavily (discovery) |
| Validation | Pydantic schemas on every verdict |
| Frontend | React 19, Vite, TanStack Query, Tailwind, React Router 7 |
| Auth | Supabase JWT middleware |
| Hosting | Render (API), Vercel (UI) |
| Monitoring | Sentry, 10% trace sampling |

Model tiering is a cost decision: the cheap 8B model does high-volume extraction and debate turns,
and the 70B model is reserved for the single judging call where reasoning quality actually changes
the output.

---

## Repository layout

```
main.py               LangGraph wiring for the v1 pipeline
server.py             FastAPI app, routes, Sentry
config.py             model names, DB config, feature flags

claims/               v2 — structured claim extraction and the citation gate
  extractor.py          LLM → claims with evidence_ids
  gate.py               deterministic verification (no LLM calls)

heads/                v2 — mode heads and verification
  evidence.py           per company × dimension retrieval
  buyer.py              2-round debate, judging, confidence recompute
  seller.py             battlecard head
  analyst.py            neutral comparison head
  consistency.py        deterministic post-hoc verdict checks
  runner.py             re-ask loop on consistency failure
  citations.py          citation-label handling in prose

court/                v1 — advocates, judge, verdict processing
pipeline/             v1 — db_check, verifier, court_session
sources/              six source agents behind the v1 router

earshot/              single-question answering
  answer.py             three gates, three-state confidence, quote matching
  calibrate_floor.py    picks SCORE_FLOOR from labelled retrieval scores

ingest/               chunking, embedding, retrieval, Atlas storage
verticals/            vertical registry and dimension definitions
ui/                   React frontend
docs/                 architecture and phase plans

eval/                 harnesses + timestamped result files
  retrieval_eval.py     hit@k / MRR against golden_retrieval.json
  abstention_eval.py    answer rate + abstention on two separate golden sets
  claims_eval.py        citation survival through the gate
  heads_smoke.py        end-to-end v2 runs with consistency checking
  corpus_snapshot.py    corpus composition + truncation detection
  rag_chunks_census.py  first-party vs third-party source composition
  source_quality.py     provenance scoring
  scraper_benchmark.py  BeautifulSoup vs Firecrawl
```

---

## Running locally

```bash
cp .env.example .env        # fill in the keys below
docker compose up
```

Required: `MONGODB_URI`, `GROQ_API_KEY` (or `GROQ_API_KEYS`), `GEMINI_API_KEY` (or
`GEMINI_API_KEYS`), `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`.
Optional: `SENTRY_DSN`, `GITHUB_TOKEN`, `ADMIN_KEY`, `AGENTS_V2`.

Run the deterministic self-checks without any database or API keys:

```bash
python -m claims.gate
python -m heads.consistency
```

Run the evaluation harnesses (these need a populated Atlas corpus):

```bash
python -m eval.retrieval_eval
python -m eval.claims_eval
```

---

## Known limitations

Written down because a system about evidence quality should be honest about its own.

1. **v2 is off in production.** See the note above. The live site runs v1.
2. **v1 confidence scores are heuristic buckets**, not calibrated against outcomes. They are
   author-chosen thresholds in `court/verdict.py`. The v2 recompute is deterministic and asserted,
   but neither has been validated against real purchase decisions.
3. **The citation gate verifies resolution, not faithfulness.** It proves a claim cites a real
   stored chunk. It does not prove the chunk supports the claim. Those are different problems and
   only the first is solved here.
4. **Retrieval evaluation covers two companies.** Claims evaluation covers three, in one vertical.
5. **The abstention sets are authored, not sampled from real usage.** Real questions are shaped
   differently from questions written by the person building the system, and the answer rate on
   real logged traffic is materially lower than on these sets. The eval is not wrong; it is
   narrower than it looks, and the honest reading of 83.3% is "on questions I wrote."
6. **`SCORE_FLOOR = 0.85` is calibrated, not derived.** `earshot/calibrate_floor.py` picks it from
   labelled retrieval scores (AUC 0.875 on that set). It is a good separator on the data it was
   fitted to and will need re-fitting as the corpus grows.
7. **Bullet-to-dimension routing in v1 is keyword-based**, not semantic. It is fast and legible and
   it will mis-route edge cases.
8. **LLM outputs are not deterministic.** Single-run numbers should be treated as directional.
   Conclusions here come from repeated runs or from deterministic checks, not from one execution.
9. **No human-labelled ground truth for verdict correctness.** The evaluation measures citation
   integrity, retrieval accuracy and internal consistency — not whether the recommendation was the
   right one. That would need a labelled set of real purchase outcomes.

---

## Citation

```bibtex
@misc{chintawar2026adversarialci,
  title  = {AdversarialCI: A Buyer-Adaptive Multi-Agent Framework for
            Evidence-Grounded Competitive Intelligence},
  author = {Chintawar, Ajinkya},
  year   = {2026},
  doi    = {10.14293/PR2199.003028.v1},
  note   = {ScienceOpen preprint}
}
```

Built at [CogniGTM](https://cognigtm.com).
