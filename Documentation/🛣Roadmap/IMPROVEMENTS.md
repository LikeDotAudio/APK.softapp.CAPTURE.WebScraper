# 🛣 Improvements — CAPTURE.WebScraper (from the 2026-10-30 architecture audit)

What this repo should change to meet the standard, most valuable first. Source: [🔍Audits/ARCHITECTURE-AUDIT.md](../%F0%9F%94%8DAudits/ARCHITECTURE-AUDIT.md).
← [Roadmap](INDEX.md)

| # | Improvement | Category | Effort (S/M/L) | Evidence |
|---|---|---|---|---|
| 1 | `OS/system/pipeline.json` cites the corpus through `scrapes/INDEX.json` (key `specs-amwa-tv-is-07`) rather than the raw folder — **Waiting on root/OS (handoff filed; root/OS is the peer session's)**. pipeline.json is a placement map keyed by folder path, so this may need a WEB.OsApi rule rather than a JSON edit; the path it uses is unchanged, nothing is broken. Release tags: **Needs owner**. | Change management | S | `OS/system/pipeline.json:353` |
