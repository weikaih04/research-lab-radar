# Research Lab Radar: implementation plan

## Product question

For each tracked organization, what *observable* evidence suggests a change in research hiring or publication activity, and how useful is it for internships, full-time roles, startup ideas, or understanding research direction? Every claim must link to a source, carry a collection date, and separate observation from interpretation.

## Phase 1: reliable baseline (implemented)

- Ten organizations in a fixed registry. Public boards are connected for five organizations; Google, Microsoft and the named MSR subset use complete pagination of explicitly targeted official-careers searches. Meta and Amazon remain unconnected. Targeted searches are never presented as company-wide counts.
- Daily snapshots, first-run baseline, job additions/changes/two-run-confirmed removals, source health, preserved last-good data, static site, and free scheduled refresh/publish. Title-based role families and matched title evidence replace the broad initial relevance rule.
- OpenAlex AI-topic paper candidates with date/DOI filtering. They are *not* verified organization publications.
- Manual LinkedIn and X live-search shortcuts. No API-based social monitoring yet.

## Phase 2: complete official hiring coverage

For Meta and Amazon, inspect each official careers site's accessible search/export interface. Expand Google and Microsoft beyond their current targeted queries only when full pagination can be verified. MSR currently means postings whose official Microsoft title explicitly says "Microsoft Research"; it is a narrow subset, not all MSR hiring. For every connector: record exact query scope, page count and last successful collection, and never turn a partial query into a whole-company number. Compare normalized listing IDs over time. Two-run confirmation now prevents an unstable result page from immediately producing a false removal.

Acceptance: each connected company has a source URL, successful full or explicitly partial baseline, and a test proving that a fetch failure cannot create false removal events.

## Phase 3: social discovery without false completeness

LinkedIn: begin with saved company/job searches and official company pages reviewed manually, then optionally use user-owned alert emails or a search provider to discover public result URLs. Record link, publication time *as displayed*, discovery time, search query, and whether the result was opened and verified. General LinkedIn people/job search is not available through the public developer API; do not automate logged-in scraping or claim employee counts from sampled profiles.

X: keep a small allowlist of official lab/researcher accounts and a few topic queries. Add the official API only behind a configurable monthly spend cap of $5, a per-run cap, and a hard stop when remaining budget is zero. A free search-index fallback can find occasional public X URLs but cannot provide reliable daily coverage. On failed or skipped days show “X 今日未更新” and the last successful X timestamp.

Discovery results enter a review queue, not the verified evidence store. Confirm original URL, author/account and date before promoting them. Store source provenance and deduplicate cross-posts.

## Phase 4: careful interpretation

Use a language model only after deterministic collection and source verification. Feed it a compact set of new evidence with URLs; require structured output with `observation`, `hypothesis`, `alternatives`, `confidence`, and `supporting_ids`. Reject an inference that cites missing IDs. Prefer a local model for optional daily drafts; otherwise keep the rules-only system fully functional at zero model cost. Do not conclude “company is pivoting to robotics” from one job or viral post. Escalate a theme only after repeat hiring signals plus independent paper, product or official-statement evidence.

For papers, verify author affiliations or official lab publication pages before calling one an organization output. Compare impact within publication year and field; show citations and citations/month with an indexing caveat, and avoid a single company leaderboard based on raw totals. Add weekly summaries only after at least two weeks of stable daily data.

## Cost and operations

Current operating cost is $0 in API charges, using public careers pages, OpenAlex casual access, GitHub Actions and GitHub Pages. GitHub/free-tier limits and source rate policies still apply. The jobs collector requests only public pages and runs once daily. Review connector failures and OpenAlex candidates weekly. If the optional X API is enabled later, default to a $5/month hard stop; do not silently switch to old results or unverified search snippets.
