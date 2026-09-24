# Research Lab Radar

Daily public data feed for the independent Research Lab Radar page. It stores hiring snapshots, emits changes only after a successful baseline, and keeps paper *candidates* separate from verified hiring evidence.

Live page: https://dashboard.ai-research-wk.com/lab-radar/

Implementation phases and source strategy: [ROADMAP.md](ROADMAP.md).

## Run

Python 3.10+; no packages or API keys required.

```sh
python3 -m radar collect
```

SQLite is a local cache. The tracked `state/snapshot.json` preserves baseline/history for stateless runs, and `site/data.json` is the public data feed read by the dashboard domain. GitHub Actions runs collection daily at 16:17 UTC and publishes `site/` through GitHub Pages after each data commit. The old GitHub Pages landing page redirects visitors to the dashboard domain.

## Current coverage and limits

- Jobs: public Ashby boards for OpenAI and Physical Intelligence; public Greenhouse boards for Anthropic and Skild AI; NVIDIA's public Workday search; Google Careers' complete pagination for the targeted `research scientist` query; and Microsoft's public careers search for the targeted `researcher` query. Microsoft Research counts only positions explicitly named "Microsoft Research" and these are excluded from the general Microsoft row to avoid double-counting. NVIDIA, Google, Microsoft and MSR are **targeted searches**, not complete company-wide counts. Meta and Amazon remain unconnected.
- Role families are conservative title rules (`research`, `research_engineering`, `ai_engineering`, `ai_infrastructure`). Non-research roles such as internal communications are excluded. Topic labels also come only from matched title words, and each exported topic includes its evidence text. A missing topic means "not specified in title", not "no relevant research".
- The Microsoft careers site may rate-limit its public search endpoint. Retries are bounded; an incomplete or failed search is marked as an error and preserves the prior successful snapshot. A job is marked removed only after two successful snapshots omit it.
- Papers: OpenAlex institution matches for eight organizations, looking back 30 days, DOI required. These are **candidates** because affiliation indexing and publication dates can be wrong. Physical Intelligence and Skild AI have no verified OpenAlex institution entry yet.
- LinkedIn and X: manual live-search links only. There is no scraping or API ingestion and no claim of daily updates. An official X API connector can be added later with a monthly spend limit; it is intentionally off by default.
- Topic tags: deterministic keyword rules on titles, not LLM interpretation. Do not infer research strategy from one listing. First collection is a baseline and produces no “new job” events.

## Data model

`jobs` tracks active listings and first/last seen time. `events` records new, changed, reopened and removed listings after baseline. `sources` tracks last attempt, last success, failure and item count independently per company. Failed/empty responses preserve the last good snapshot. `papers` stores recent OpenAlex candidates and citation counts as reported at fetch time. The JSON snapshot is restored when a fresh runner has no SQLite cache.

## Source and cost notes

The connected careers pages and OpenAlex casual API access require no paid plan for this scale. The Workday search endpoint is a public page backend, not a documented third-party API; if it changes, the dashboard marks that source as failed and keeps the last successful snapshot. LinkedIn job-search pages are provided for manual research because general search is not offered as a public LinkedIn API. X search links are manual; official API ingestion is a separate, paid decision.
