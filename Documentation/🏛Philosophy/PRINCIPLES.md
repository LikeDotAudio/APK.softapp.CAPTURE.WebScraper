# Principles — CAPTURE.WebScraper

The principles this code keeps, each pointed at the line that keeps it. Ecosystem rules are cited, not copied: [Refusal over fabrication](../../../../../../../Documentation/%F0%9F%8F%9BPhilosophy/Doctrine/readme.Refusal%20over%20fabrication.md), [Timestamps are local time](../../../../../../../Documentation/%F0%9F%8F%9BPhilosophy/Doctrine/readme.Timestamps%20are%20local%20time.md).

← [Wiki home](../README.md)

| # | Principle | Kept by |
|---|---|---|
| 1 | **Every fetch leaves a manifest, and only a fetch does.** Each saved page and media file gets `<file>.provenance.json` (URL, UTC time, status, type, length, SHA-256); the Markdown conversion gets none, because it was not fetched. | `Scraper.py:330` (pages), `Scraper.py:219` (media), the deliberate absence in `markdown_worker` `Scraper.py:137` |
| 2 | **A manifest follows its file.** When a page file must become a directory, it moves to `<dir>/index.html` and its manifest moves with it. | `Scraper.py:305–307` |
| 3 | **No half-records.** A manifest missing a required field raises instead of being written; digest and length are read back off the bytes on disk; a backfilled record says `"reconstructed"`. | `provenance.py:74–78`, `:50` `build`, `:82` `write` |
| 4 | **The schema is the single source.** Required fields are read from `harvest-manifest.schema.json` at import. | `provenance.py:37` |
| 5 | **Politeness is a constant.** Delay, thread count, disallowed paths and non-page extensions are module constants with their reasons beside them. | `Scraper.py:46–80` |
| 6 | **One canonical URL per page.** `normalize_url` forces one scheme, drops `www.`, one trailing-slash form; `visited_urls` is claimed under `visited_lock`. | `Scraper.py:94`, `:248` |
| 7 | **Keep going on errors.** A failed fetch, unwritable path or bad file is printed and skipped. | `download_page_worker` `Scraper.py:230`, `markdown_worker` |
| 8 | **Machine timestamps carry their zone.** `retrieved_at` is Z-suffixed UTC. | `provenance.py:50` `build` |
| 9 | **No single fetch exceeds 2 MB.** A declared `Content-Length` over `MAX_FETCH_BYTES` is refused unread; a body that streams past it is dropped; pages and media alike. | `Scraper.py` `read_capped`, `TooLarge` |
| 10 | **One scheme per site, the start URL's.** `http://`, `https://` and `//` links collapse to it, so an http-only site mirrors. | `Scraper.py` `normalize_url`, `site_scheme` |

## Where the code still falls short

- **`DISALLOWED_PATHS` is one site's robots.txt** (`Scraper.py:68`); it is wrong for every other host and the code does not read robots.txt.
- **Interactive.** The media question is `input()` on stdin (`Scraper.py:453`), so it cannot run unattended.
- The trees already in `scrapes/` predate the manifests and carry none.
