# 🛣 Improvements — CAPTURE.WebScraper (from the 2026-10-30 architecture audit)

What this repo should change to meet the standard, most valuable first. Source: [🔍Audits/ARCHITECTURE-AUDIT.md](../%F0%9F%94%8DAudits/ARCHITECTURE-AUDIT.md).
← [Roadmap](INDEX.md)

| # | Improvement | Category | Effort (S/M/L) | Evidence |
|---|---|---|---|---|
| 1 | SCANALYZER `Crawler.Like.Audio` calls `apk_webscraper.crawl()` instead of its own downloader/parser — **Waiting on SCANALYZER.Like.audio (handoff filed)**. This repo's side (the importable package, CAPTURE.crawler converted) is done. | Duplication Control | M | `Crawler.Like.Audio/Thick/src/tabs/WebCrawler/` |
| 2 | `OS/system/pipeline.json` and LIB.NCP cite corpora through `scrapes/INDEX.json` — **Waiting on root/OS and LIB.NCP (handoffs filed)**; the index exists and the paths they use are unchanged. Release tags: **Needs owner**. | Change management | S | `scrapes/INDEX.json` |
