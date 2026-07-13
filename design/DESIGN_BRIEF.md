# AdversarialCI — Design Brief

## What this product is

AdversarialCI runs adversarial, AI-driven vendor evaluations. A user picks a
vertical (database / cloud / crm) and a mode, describes their situation, and
the backend runs a multi-stage AI pipeline (research → argue → judge, or
research → shortlist → score) that produces a markdown report recommending
a winner with evidence and tradeoffs.

Four modes:
- **buyer** — "which vendor should I pick" — the primary flow
- **seller** — "how do I position against a competitor"
- **analyst** — neutral comparison, no declared winner
- **sourcing** — research/freshness check only, no court session

## Core entities (design around these fields, not generic placeholders)

**Vendor** — name, vertical, pricing_url, github_repo, blog sources,
migration/complaint queries, plus derived intel: research doc count per
source type (Pricing/Blog/GitHub/Tavily/HN/Migration/Complaints),
last_scraped date, freshness status (fresh/stale/new).

**Vertical config** — drives the intake form dynamically: each vertical
defines its own `plaintiff_questions` (e.g. company_name, team_size, budget,
use_case, scale, cloud, priority) and its own comparison dimensions (cost,
performance, scalability, simplicity, lock_in_risk, vector_capability,
ecosystem, ...). The UI should render this form from config, not hardcode
fields per vertical.

**Session / Report** — mode, vertical, vendors compared, the buyer's stated
profile, verdict (winner, confidence %, per-vendor scores across
dimensions, tradeoffs, ranking), and a markdown report body. Reports have
structured sections: Recommendation, Why-the-winner, Vendor Comparison
table, Tradeoffs, Next Steps.

## Screens to design

1. **Login** — single "Continue with Google" button (Supabase OAuth). No
   email/password. Minimal — logo, tagline, one button.
2. **Dashboard / Overview** — landing page, KPI summary (total vendors,
   intel docs, sessions run, top winner this month).
3. **Vendor Registry** — searchable/filterable-by-vertical list of vendors.
   Expandable rows show source breakdown (pricing/github/blog/etc. doc
   counts) + freshness. **Full CRUD is real and built** (add/edit/delete
   vendor, trigger a live re-scrape with streaming progress) — design it as
   a first-class admin surface, not a stub. Non-admin users see read-only.
4. **Evaluation Wizard** (the core flow) — multi-step, branches by mode:
   - buyer: vertical+mode → pick 2-4 vendors → fill profile form (from
     vertical config) → run
   - seller: vertical+mode → pick my company → pick 1-3 competitors → fill
     prospect profile → run
   - analyst: vertical+mode → pick vendors → optional focus areas → run
   - A "brief" free-text mode also exists on the backend (buyer pipeline
     parses a natural-language brief instead of a structured form) —
     worth designing an alternate "describe your situation" entry point
     alongside the structured form, not instead of it.
   - **Run step**: currently a raw streaming log/terminal display (SSE of
     literal print statements, no structured progress %). Design this as a
     proper staged progress UI (e.g. "Researching vendors → Scoring →
     Writing report") that can still show live log detail underneath for
     transparency, since real percentage progress isn't available from the
     backend today.
5. **Report View** — structured rendering: winner card, per-vendor
   scorecards across dimensions, tradeoffs section, comparison table,
   profile summary pills. This already exists as componentized structure
   (WinnerCard, VendorScorecard, TradeoffsSection, etc.) — refine, don't
   reinvent the structure.
6. **History / Intelligence Tracker** — filterable list of past sessions
   (by mode/vertical/date range), trend insights (win distribution per
   vendor over time), stats (total verdicts, this month, avg confidence).

## Auth state

Real auth (Supabase Google OAuth) exists in code but isn't wired into the
app yet. Treat "logged out" as read-only browsing (vendor list, reports,
history) and "logged in" as required to run evaluations or mutate the
vendor registry. This is a proposed convention, not existing behavior —
today everything is open except vendor-mutation endpoints (gated by a
shared admin key, not per-user auth).

## Design constraints / notes for Claude Design

- Existing visual identity: dark theme, "glass-panel" cards, cyan accent
  (`--accent-cyan`), terminal/monospace touches for the AI-pipeline feel
  (this is a security/intelligence-tool aesthetic — lean into it, don't
  make it generic SaaS pastel).
- Needs loading/empty/error states everywhere — especially the run step
  (long-running, 30s-2min+) and vendor refresh (SSE streaming).
- Needs to support 3 verticals now, more later — component design should
  read config, not branch on vertical name.
- Report rendering must handle markdown + structured data side by side.

## Open questions to flag back to engineering (don't design around silently)

- `pipeline/buyer` (brief→shortlist→research→score, RAG-backed) vs
  `pipeline/court_session` (structured form→adversarial argue→judge) are
  two different backend flows. Confirm which is canonical before deciding
  whether the wizard needs one entry point or two.
- `PUT /api/vendors` (edit) has no admin-key check while POST/DELETE do —
  access-control gap, flag before shipping the edit UI as unrestricted.
