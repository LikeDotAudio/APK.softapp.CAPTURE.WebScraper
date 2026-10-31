# 🔍 Architecture audit — CAPTURE.WebScraper (2026-10-30)

Audited against the APK.audio multi-repo architecture standard: coupling, boundaries, duplication, contracts.
← [Audits](INDEX.md) · Improvements: [🛣Roadmap/IMPROVEMENTS.md](../%F0%9F%9B%A3Roadmap/IMPROVEMENTS.md)

## Bounded context
Polite single-site web mirror: fetch one site's HTML (and optionally its own media) within its robots.txt and a per-host rate limit, write a `<file>.provenance.json` sidecar per fetch, convert pages to Markdown, stitch archive parts, index the corpora. Python package `apk_webscraper` (engine, provenance, backfill, config) behind a `Scraper.py` CLI shim, beside a tracked output corpus in `scrapes/` (`microphones`, `specs-amwa-tv-is-07`, `specs-amwa-tv-is-12`, each with `-MD`, every fetched file with a manifest, `INDEX.json`).

## Context map
| Talks to | How (topic / endpoint / file / import) | Relationship |
|---|---|---|
| Target websites | HTTP GET through `Fetcher` (robots.txt, per-host limiter, UA/limits from `config.ini`) | Conformist (to each site's robots policy) |
| CAPTURE.crawler | `import apk_webscraper` (Web Crawler tab) | Supplier |
| SCANALYZER Crawler.Like.Audio | `apk_webscraper.crawl` (SCANALYZER 7d0c59d) | Customer |
| OS pipeline walker (`PODS/POD.THIN/OS/system/pipeline.json`) | file path `…/scrapes/specs-amwa-tv-is-07` | Customer–Supplier by path; `scrapes/INDEX.json` offered (handoff) |
| LIB.NCP README | cites corpus key `specs-amwa-tv-is-12` in `scrapes/INDEX.json` (LIB.NCP 80717ab) | Customer via the index |
| OS app walker | [display.json](../../display.json) (`entry: Scraper.py`, `tech: python`) | Published Language |
| MQTT bus / HTTP gateway | none | n/a |

## Scorecard
| Category | Score (0–3) | Finding |
|---|---|---|
| Coupling & Cohesion | 3 | Self-contained package; run state in a `Crawl` object; consumers import it or read the corpus index. |
| Boundary Integrity | 3 | One `Fetcher` holds the politeness contract; robots.txt read from the site; media host-scoped; provenance validated against its schema. |
| Duplication Control | 3 | One IS-07 layout; CAPTURE.crawler and SCANALYZER Crawler.Like.Audio both crawl through `apk_webscraper`. |
| Testing & Contracts | 3 | 21 pytest tests on local fixtures; full schema validation of every sidecar, written or committed; corpus index has a schema. |
| Change management | 2 | Tool version in every manifest and the index; consumers' move to the index is handed off; no release tags (Needs owner). |
Score key: 3 meets the standard · 2 minor gaps · 1 significant gaps · 0 absent / violated.

## Findings
1. **GOOD — provenance is a real contract, single-sourced.** Records are validated against `harvest-manifest.schema.json` itself; digest/length are read off the bytes on disk; derivatives get none; a migrated page's manifest moves with it; backfilled ones say `reconstructed`.
2. **GOOD — politeness is enforced in one place.** `Fetcher.fetch()`: robots.txt, one limiter per host across workers, size cap, one timeout and UA.
3. **`OS/system/pipeline.json` still cites the corpus folder by path — waiting on root/OS (handoff filed).** LIB.NCP now cites the index key; the pipeline path is unchanged and works.
4. **No release tags — Needs owner.**
