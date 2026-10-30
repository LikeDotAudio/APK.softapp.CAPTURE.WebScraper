# Architecture — CAPTURE.WebScraper

How to use it and how it works inside.

← [Wiki home](../README.md)

## Use

```bash
pip install --user requests beautifulsoup4 markdownify
cd PODS/POD.THIN/Softapps/CAPTURE/CAPTURE.WebScraper     # scrapes/ lands in the current directory
python3 Scraper.py https://specs.amwa.tv/is-07/
# answers y/n on stdin: also fetch media?
```

Before pointing it at a new host, replace `DISALLOWED_PATHS` with that host's robots.txt.

## Files

| Path | Role |
|---|---|
| `Scraper.py` | The CLI: crawl, convert, stitch. |
| `provenance.py` | `build()` / `write()` of `<file>.provenance.json`; `manifest_path()` = full file name + `.provenance.json`. |
| `harvest-manifest.schema.json` | JSON Schema (2020-12, `schemaVersion: 1`) for those sidecars; `provenance.py` reads `required` from it. |
| `scrapes/` | Tracked output corpus (~342 MB, 8,945 files); not source. |
| `display.json` | OS walker manifest (its `entry: main.py` does not exist). |

## Flow

```
url ──▶ normalize + base/folder name ──▶ url_queue
             4 × download_page_worker:
               scope check (base prefix, DISALLOWED_PATHS, NON_PAGE_EXTENSIONS)
               claim url under visited_lock → GET (20 s timeout) → sleep REQUEST_DELAY
               resolve file/dir conflicts under fs_lock (page + its manifest move to index.html)
               write scrapes/<folder>/<path>  →  provenance.write()
               extract_main_content → md_queue;  links → url_queue;  media → download_media (+ manifest)
             1 × markdown_worker: md_queue → scrapes/<folder>-MD/<path>.md   (no manifest)
  url_queue.join() → stop workers → concatenate_markdown_files → COMBINED_ARCHIVE_partN.md (2 MB parts)
```

## A manifest

```json
{"schemaVersion": 1, "source_url": "https://…", "retrieved_at": "2026-10-30T16:57:01Z",
 "http_status": 200, "content_type": "text/html", "content_length": 1234,
 "sha256": "…", "fetcher": "Scraper.py", "provenance": "fetched", "note": null}
```

Verified 2026-10-30 against a local three-page fixture (`/`, `/a`, `/a/b`): every HTML file got a manifest, and `/a`'s manifest moved to `a/index.html.provenance.json` when `/a/b` forced the migration.

No ports, no MQTT.
