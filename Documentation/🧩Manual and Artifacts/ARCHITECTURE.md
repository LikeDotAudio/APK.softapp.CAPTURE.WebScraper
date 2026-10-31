# Architecture — CAPTURE.WebScraper

How to use it and how it works inside.

← [Wiki home](../README.md)

## Use

```bash
pip install --user -r requirements.txt        # or: pip install .   (package apk_webscraper, CLI apk-webscrape)
python3 Scraper.py https://specs.amwa.tv/is-07/                 # pages only, into ./scrapes beside this file
python3 Scraper.py https://specs.amwa.tv/is-07/ --media --out /tmp/s --config my-sites.ini
python3 -m pytest -q tests                                      # 21 tests, local fixtures only, no external request
```

From code (CAPTURE.crawler's Web Crawler tab does this):

```python
import apk_webscraper
stats = apk_webscraper.crawl(url, out="scrapes", media=False, logger=print, on_file=None)
```

A new host needs nothing in code: its robots.txt is read; add a `[<host>]` section to `apk_webscraper/config.ini` only for extra disallows, a different delay, media hosts or `keep_query`.

## Files

| Path | Role |
|---|---|
| `Scraper.py` | CLI shim (the `display.json` entry) → `apk_webscraper.engine.main`. |
| `apk_webscraper/engine.py` | `Fetcher` (the politeness contract), `RateLimiter`, `SiteRules`/`load_rules`, `Crawl` (one run's state), `crawl()`, `concatenate_markdown_files`, `update_index`, `main`. |
| `apk_webscraper/provenance.py` | `build()` / `write()` / `validate()` of `<file>.provenance.json`, validated against the whole schema (jsonschema, Draft 2020-12, formats). |
| `apk_webscraper/harvest-manifest.schema.json` | JSON Schema for the sidecars, `schemaVersion: 1`. |
| `apk_webscraper/backfill.py` | `python3 -m apk_webscraper.backfill` — `"reconstructed"` sidecars for files fetched before manifests existed. |
| `apk_webscraper/config.ini` | Per-site rules: `[DEFAULT]` + `[<host>]` sections. |
| `corpus-index.schema.json` | Schema of `scrapes/INDEX.json`. |
| `scrapes/` | The tracked corpus: `microphones`, `specs-amwa-tv-is-07`, `specs-amwa-tv-is-12` (+ `-MD`), `INDEX.json`. Not source. |
| `tests/` | pytest: a local `http.server` site (`conftest.py`), crawl/robots/scope/cap/rate/index tests, provenance, corpus contracts. |
| `pyproject.toml`, `requirements.txt` | Package metadata; pinned deps. |

## Flow

```
url ─▶ Crawl(start_url): plan() → base URL + folder (<host>-<path>, trailing vN.N.N dropped); rules = load_rules(host)
        url_queue ◀── start URL
        rules.threads × page_worker:
            normalize_url (start scheme, no www., no trailing /, query only if keep_query) → scope (under base) → claim (visited_lock)
            Fetcher.fetch():  host entry (rules, ONE RateLimiter per host, robots.txt read first — every other
                              request to that host waits until it is) → extra_disallow / robots.can_fetch →
                              limiter.wait() → GET (one timeout, one UA) → read_capped(max_file_size_mb)
            prepare_path (page that must become a dir → <dir>/index.html, manifest moves too)
            Fetcher.save() → bytes + provenance.write()          (fetched files only)
            links → url_queue;  media (--media): target host or media_hosts only → <folder>-MEDIA/<host>/<path> (+ manifest)
            extract_main_content → md_queue
        1 × markdown_worker → <folder>-MD/<path>.md            (no manifest: a derivative)
  join → concatenate_markdown_files (COMBINED_ARCHIVE_partN.md, max_file_size_mb parts) → update_index(scrapes/INDEX.json)
```

robots.txt per RFC 9309: a 4xx means no rules; a 5xx or no answer means everything is disallowed. `Crawl-delay` raises the host's interval, never lowers it.

## A manifest

```json
{"schemaVersion": 1, "source_url": "https://…", "retrieved_at": "2026-10-30T16:57:01Z",
 "http_status": 200, "content_type": "text/html", "content_length": 1234,
 "sha256": "…", "fetcher": "Scraper.py 2.0.0", "provenance": "fetched", "note": null}
```

A backfilled one says `"provenance": "reconstructed"`, `"fetcher": "Scraper.py (before 2.0.0)"`, nulls for status and type, `retrieved_at` = the date git first recorded the file, and a note saying how it was derived.

## The corpus index

`scrapes/INDEX.json` (`corpus-index.schema.json`) lists each corpus by folder key: `source_url`, `html`, `markdown`, `media`, `last_run`, `tool`, `pages`, `note`. Other repos cite a corpus by key (`specs-amwa-tv-is-07`, `specs-amwa-tv-is-12`) so the folder can move with one edit here.

No ports, no MQTT.
