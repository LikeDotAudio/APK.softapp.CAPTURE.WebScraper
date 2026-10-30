# CAPTURE.WebScraper

> 📷 **Capture Webscraper** — a polite single-site mirror: fetch one website's HTML, convert each page to Markdown, and stitch the Markdown into size-capped archives.

---

## 🧩 Architectural Role
* **Family**: Softapps · `CAPTURE` (data capture, ingestion and scrapers)
* **Category**: `CAPTURE` (`display.json` `"category"`); no `group`/`subGroup`
* **Pipeline Stage**: none declared. Its output is intake material — the `01 · Event` lane in the doctrine's terms — but nothing files it there.

---

## ⚙️ Repository Overview
Three authored files, and a large corpus of other people's pages:

| Path | What it is |
|---|---|
| `Scraper.py` | The command-line scraper. |
| `provenance.py` | Builds and writes `<file>.provenance.json` sidecars (source URL, retrieval time, HTTP status, length, SHA-256) against the schema below. Reads its required-field list *from* the schema at import. |
| `harvest-manifest.schema.json` | JSON Schema (draft 2020-12) for those sidecars, `schemaVersion: 1`. Hand-written, and deliberately not in `contracts/` (its `$comment` says why). |
| `scrapes/` | Output, tracked: ~342 MB, 8,945 files — `microphones` (3,978) and `microphones-MD` (3,972), AMWA `is-07` / `is-07-MD`, `specs-amwa-tv-is-07` / `-MD`, `specs-amwa-tv-is-12` / `-MD`. 3,245 paths under `scrapes/microphones*/` contain `\|` or `+` (counted with `git ls-files`, 2026-10-30); quote them. The older `scrapes/is-07*` trees encode the source URL in the path (`scrapes/is-07/https:/specs.amwa.tv/…`). None of it carries a `.provenance.json` yet. |
| `display.json` | Manifest for the OS application walker. |

### What `Scraper.py` does
1. Takes one positional `url`. Derives a base URL and an output folder name from its path (a trailing `vN.N.N` segment is dropped so every version of a spec lands in one folder).
2. **Asks on stdin** whether to also fetch media (`y/n`).
3. Runs four `download_page_worker` threads over a URL queue and one `markdown_worker` thread over a Markdown queue. Each page is converted with `markdownify` after `extract_main_content()` strips scripts, styles and site chrome.
4. Writes, relative to the **current directory**:
   * `scrapes/<folder>/…` — the HTML, mirroring the URL path (a path that is both file and directory is moved to `…/index.html`),
   * `scrapes/<folder>-MD/…` — one Markdown file per page,
   * `scrapes/<folder>-MEDIA/…` — media, only if you answered `y`.
5. Stitches every Markdown file into `scrapes/<folder>-MD/COMBINED_ARCHIVE_partN.md`, starting a new part at 2 MB.

Hard limits, each a constant at the top of `Scraper.py`: 2 MB per fetch (`MAX_FILE_SIZE_MB`), 0.5 s between a worker's requests (`REQUEST_DELAY`), 4 download threads (`NUMBER_DOWNLOAD_THREADS`), no URL whose path starts with a `DISALLOWED_PATHS` prefix, no `NON_PAGE_EXTENSIONS` target parsed as HTML. **`DISALLOWED_PATHS` is one microphone site's `robots.txt`** — replace it before pointing the scraper at any other host.

---

## 🚀 Usage & Integration
* **Run it** (from this folder, so `scrapes/` lands here):
  ```bash
  pip install --user requests beautifulsoup4 markdownify
  python3 Scraper.py https://specs.amwa.tv/is-07/
  ```
  `python3 Scraper.py --help` prints the one-argument usage.
* **Tests**: none.
* **Web Portal Entry**: none that opens. `display.json` declares `"entry": "main.py"`, which does not exist, so the OS application walker (`PODS/POD.THIN/WEB.OsApi/SRC/server.py`, `walk_project()`) falls through and lists the folder as a **folder** app.
* **Ports / MQTT**: none. It is a client of whatever site it is pointed at and nothing else.
* **Remote Repository**: `https://github.com/LikeDotAudio/APK.softapp.CAPTURE.WebScraper.git`

---

## 🏛 Philosophy
What the code actually does, in the ecosystem's vocabulary (`Documentation/🏛Philosophy`):

* **Politeness is a constant, not a habit.** Size cap, delay, thread count and the disallow list are module-level constants with the reasons written beside them (`Scraper.py`, top of file).
* **One canonical URL per page.** `normalize_url()` forces one scheme, drops `www.` and one trailing-slash style so `visited_urls` (guarded by `visited_lock`) really deduplicates (`Scraper.py`).
* **A manifest records a fetch, never a derivative.** `provenance.py` refuses to describe a file it cannot read, fails a record with a missing required field rather than writing a half-record, reads digest and length back off the bytes on disk, and marks anything backfilled `"provenance": "reconstructed"` (`provenance.build()` / `write()`). This is refusal over fabrication applied to provenance.
* **The schema is the single source.** The required fields are read from `harvest-manifest.schema.json` at import, so the schema and the writer cannot silently disagree (`provenance.py`).
* **Keep going on errors.** A failed fetch, an unwritable directory or a bad file is printed and skipped; the crawl continues (`download_page_worker`, `markdown_worker`, `concatenate_markdown_files`).
* **Machine timestamps are UTC.** `retrieved_at` is Z-suffixed UTC (`provenance.py`). The doctrine's *Timestamps are local time* rule covers hand-written stamps; this is a machine-written one and says its zone.

---

## ⚠️ Known gaps
* `Scraper.py` imports `provenance` and its docstring says every fetch leaves a manifest, but no code path calls `provenance.write()`; no sidecars are produced.
* The media prompt makes it unusable unattended.

## 🛣 Plans
Plans live only in `Documentation/🛣Roadmap/roadmap.htm` at the APK.audio root.
