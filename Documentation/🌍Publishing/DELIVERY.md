# Delivery — CAPTURE.WebScraper

How it is built, tested and shipped, and where it lands.

← [Wiki home](../README.md)

| Step | What happens | Automated? |
|---|---|---|
| Build | None: plain Python 3 with `requests`, `beautifulsoup4`, `markdownify` (no `requirements.txt` here). | — |
| Test | None in the repo. `python3 -m py_compile Scraper.py provenance.py` and `python3 Scraper.py --help` are the checks; the provenance path was exercised by hand against a local fixture (see [ARCHITECTURE](../%F0%9F%A7%A9Manual%20and%20Artifacts/ARCHITECTURE.md)). | No CI (no `.github/`). |
| Run | By hand, on a workstation, from this folder. Output lands in `./scrapes/` and is committed here as the intake corpus. | No schedule, no container. |
| Image | The Softapps tree is copied into **WEB.Frontend-Assets** (`Portal-WebStatic`), but the root `.dockerignore` drops `**/scrapes` and `Softapps/**/*.py`, so only `display.json`, the schema, the README and the docs land there, at `/APK:Softapps/CAPTURE/CAPTURE.WebScraper/`. Nothing runs in the image. | Copy automatic on `up-stack.sh WEB.Frontend-Assets`; rebuild by hand. |
| Publish | `git push` to <https://github.com/LikeDotAudio/APK.softapp.CAPTURE.WebScraper>; `.apk.scripts/deploy_all.py` pushes every submodule. No public URL. | Run by hand. |
| Smoke | `.apk.scripts/smoke.py` checks HEAD is on origin ([SMOKE](../%F0%9F%A7%A9Manual%20and%20Artifacts/SMOKE.md)). | Run by hand. |

Not automated: the crawl itself, re-reading a new host's robots.txt, backfilling manifests for the existing `scrapes/` trees, and any test.
