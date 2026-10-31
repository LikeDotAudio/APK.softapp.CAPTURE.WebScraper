# Principles — CAPTURE.WebScraper

The principles this code keeps, each pointed at the line that keeps it. Ecosystem rules are cited, not copied: [Refusal over fabrication](../../../../../../../Documentation/%F0%9F%8F%9BPhilosophy/Doctrine/readme.Refusal%20over%20fabrication.md), [Timestamps are local time](../../../../../../../Documentation/%F0%9F%8F%9BPhilosophy/Doctrine/readme.Timestamps%20are%20local%20time.md).

← [Wiki home](../README.md)

| # | Principle | Kept by |
|---|---|---|
| 1 | **Every fetch leaves a manifest, and only a fetch does.** Each saved page and media file gets `<file>.provenance.json` (URL, UTC time, status, type, length, SHA-256); the Markdown conversion gets none, because it was not fetched. | `Scraper.py:330` (pages), `Scraper.py:219` (media), the deliberate absence in `markdown_worker` `Scraper.py:137` |
| 2 | **A manifest follows its file.** When a page file must become a directory, it moves to `<dir>/index.html` and its manifest moves with it. | `engine.py` `Crawl.prepare_path` |
| 3 | **No half-records.** A manifest that breaks the schema in any way raises instead of being written; digest and length are read back off the bytes on disk; a backfilled record says `"reconstructed"` and why. | `provenance.py` `build`/`validate`, `backfill.py` |
| 4 | **The schema is the single source.** Records are validated against `harvest-manifest.schema.json` itself, not a restatement of it. | `provenance.py` `VALIDATOR` |
| 5 | **The site says what may be fetched.** Its robots.txt is read and obeyed for every URL; per-site tunables live in `config.ini` keyed by host; nothing about one site is compiled in. | `engine.py` `Fetcher`, `load_rules`; `apk_webscraper/config.ini` |
| 6 | **Politeness is per host, not per thread.** One rate limiter per host is shared by every worker. | `engine.py` `RateLimiter`, `Fetcher.host` |
| 7 | **One canonical URL per page.** `normalize_url` forces the start URL's scheme, drops `www.`, one trailing-slash form, the query unless configured; URLs are claimed under `visited_lock`. | `engine.py` `Crawl.normalize_url`, `claim` |
| 8 | **Keep going on errors.** A failed fetch, unwritable path or bad file is logged and skipped. | `Crawl.process_page`, `markdown_worker` |
| 9 | **Machine timestamps carry their zone.** `retrieved_at` is Z-suffixed UTC. | `provenance.py` `build` |
| 10 | **No single fetch exceeds the cap.** A declared `Content-Length` over the cap is refused unread; a body that streams past it is dropped. | `engine.py` `read_capped`, `TooLarge` |
| 11 | **Stay on the target.** Pages under the start URL only; media from the target host or a configured media host only, saved under that host. | `Crawl.is_in_scope`, `media_allowed_host` |
| 12 | **One crawler.** Other tools crawl through `apk_webscraper.crawl()` rather than carrying their own. | `apk_webscraper/__init__.py` |

## Where the code still falls short

- SCANALYZER's `Crawler.Like.Audio` still carries its own crawler (handoff filed).
- No release tags (Needs owner).
