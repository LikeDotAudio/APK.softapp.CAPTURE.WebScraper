# CAPTURE.WebScraper

> 📷 **Capture Webscraper** — a polite single-site mirror: fetch one website's HTML, convert each page to Markdown, and stitch the Markdown into size-capped archives.

📚 **Wiki:** [Documentation/README.md](Documentation/README.md) — [principles](Documentation/%F0%9F%8F%9BPhilosophy/PRINCIPLES.md), [architecture](Documentation/%F0%9F%A7%A9Manual%20and%20Artifacts/ARCHITECTURE.md), [delivery](Documentation/%F0%9F%8C%8DPublishing/DELIVERY.md).

---

## 🧩 Architectural Role
* **Family**: Softapps · `CAPTURE` (data capture, ingestion and scrapers)
* **Category**: `CAPTURE` (`display.json` `"category"`); no `group`/`subGroup`
* **Pipeline Stage**: none declared. Its output is intake material — the `01 · Event` lane in the doctrine's terms — but nothing files it there.

---

## ⚙️ Repository Overview
A small package and a large corpus of other people's pages:

| Path | What it is |
|---|---|
| `Scraper.py` | The CLI (`display.json` entry): a shim over `apk_webscraper.engine.main`. |
| `apk_webscraper/` | The crawler as a package — `engine.py` (`Fetcher`, `RateLimiter`, `Crawl`, `crawl()`), `provenance.py` (sidecars, validated against the schema), `harvest-manifest.schema.json`, `backfill.py` (reconstructed sidecars), `config.ini` (per-site rules). `import apk_webscraper; apk_webscraper.crawl(url, ...)`. |
| `corpus-index.schema.json` | Schema of `scrapes/INDEX.json`. |
| `scrapes/` | Output, tracked: `microphones` / `-MD` (RecordingHacks), `specs-amwa-tv-is-07` / `-MD`, `specs-amwa-tv-is-12` / `-MD`, and `INDEX.json`. Every fetched file has a `.provenance.json` (the pre-2026-10-30 ones `"reconstructed"`). Characters Windows refuses in a name (`<>:"\|?*`, a trailing dot or space, device names) are percent-encoded per path segment (`tag/603s%7Cend-address`, `DPA/d%3Afacto`; `engine.portable_segment`), so the tree checks out on Windows and macOS; `+` stays as is. The old URL-as-path `scrapes/is-07*` trees were folded into `specs-amwa-tv-is-07*` on 2026-10-30. |
| `tests/` | pytest, local `http.server` fixtures only. |
| `pyproject.toml`, `requirements.txt` | Package metadata; pinned deps. |
| `display.json` | Manifest for the OS application walker. |

### What a crawl does
1. Takes one `url`. Derives the base URL and output folder `<host>-<path>` (a trailing `vN.N.N` segment is dropped so every version of a spec lands in one folder).
2. Reads the host's **robots.txt** before any other request to it, and the host's section of `apk_webscraper/config.ini`.
3. Runs `threads` page workers over a URL queue and one Markdown worker. Every request goes through `Fetcher.fetch()`: robots + `extra_disallow`, **one rate limiter per host shared by all workers** (`request_delay`, raised by `Crawl-delay`), one timeout, the size cap.
4. Writes `scrapes/<folder>/…` (HTML, mirroring the URL path with illegal characters percent-encoded; a page that must also be a directory moves to `…/index.html`), a `.provenance.json` beside each, `scrapes/<folder>-MD/…` (Markdown, no manifest), and with `--media` `scrapes/<folder>-MEDIA/<host>/…` (target host or `media_hosts` only).
5. Stitches the Markdown into `COMBINED_ARCHIVE_partN.md` and records the corpus in `scrapes/INDEX.json` (source URL, folders, last run, tool version, pages).

Query strings are dropped by default (so tracking and session links do not multiply pages); `keep_query = true` for a site that paginates by `?page=`.

---

## 🚀 Usage & Integration
* **Run it**:
  ```bash
  pip install --user -r requirements.txt
  python3 Scraper.py https://specs.amwa.tv/is-07/            # pages only; --media for its media; --out, --config, --folder
  ```
  No prompt: it runs unattended.
* **As a library**: `pip install .` then `apk_webscraper.crawl(url, out=..., media=..., logger=..., on_file=...)` — CAPTURE.crawler's Web Crawler tab and SCANALYZER's Crawler.Like.Audio do this.
* **Tests**: `python3 -m pytest -q tests` — 21 passed on 2026-10-30, no external request.
* **Backfill**: `python3 -m apk_webscraper.backfill <tree> <url-prefix> [--alias NEW=OLD] [--exclude NAME]`.
* **Web Portal Entry**: none that opens in a browser. `display.json` names `"entry": "Scraper.py"` (`"tech": "python"`), a CLI.
* **Ports / MQTT**: none.
* **Remote Repository**: `https://github.com/LikeDotAudio/APK.softapp.CAPTURE.WebScraper.git`

---

## 🏛 Philosophy
What the code actually does, in the ecosystem's vocabulary (`Documentation/🏛Philosophy`):

* **The site says what may be fetched.** Its robots.txt is obeyed; per-site tunables are `config.ini` sections; the rate limit is per host across all workers (`apk_webscraper/engine.py` `Fetcher`).
* **One canonical URL per page.** `Crawl.normalize_url()` forces one scheme, drops `www.` and one trailing-slash style so the visited set (guarded by `visited_lock`) really deduplicates.
* **A manifest records a fetch, never a derivative.** `provenance.py` refuses to describe a file it cannot read, fails a record with a missing required field rather than writing a half-record, reads digest and length back off the bytes on disk, and marks anything backfilled `"provenance": "reconstructed"` (`provenance.build()` / `write()`). This is refusal over fabrication applied to provenance.
* **The schema is the single source.** Every record is validated against `harvest-manifest.schema.json` itself before it is written (`apk_webscraper/provenance.py`).
* **Keep going on errors.** A failed fetch, an unwritable directory or a bad file is printed and skipped; the crawl continues (`download_page_worker`, `markdown_worker`, `concatenate_markdown_files`).
* **Machine timestamps are UTC.** `retrieved_at` is Z-suffixed UTC (`provenance.py`). The doctrine's *Timestamps are local time* rule covers hand-written stamps; this is a machine-written one and says its zone.

---

## ⚠️ Known gaps
* `OS/system/pipeline.json` still cites `scrapes/specs-amwa-tv-is-07` by path rather than through `scrapes/INDEX.json` (handoff filed).

## 🛣 Plans
Plans live only in `Documentation/🛣Roadmap/roadmap.htm` at the APK.audio root.

<!-- wiki:smoke -->
**Smoke test** — ✅ PASS 1/1 since 2026-10-30 12:51 EDT — [results](Documentation/%F0%9F%A7%A9Manual%20and%20Artifacts/SMOKE.md)
<!-- /wiki:smoke -->
