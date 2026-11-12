# Smoke test — CAPTURE.WebScraper

Is `CAPTURE.WebScraper` deployed? Written by `.apk.scripts/smoke.py` from the module's own shape; what each check means is in that script's header.

← [Wiki home](../README.md)

**❌ FAIL** — 1/2 checks, since 2026-11-12 00:15 EST

| Check | Target | Result | Detail |
|---|---|---|---|
| pushed | [APK.softapp.CAPTURE.WebScraper](https://github.com/LikeDotAudio/APK.softapp.CAPTURE.WebScraper.git) | ✅ | HEAD is on origin |
| web | [Scraper.py](https://apk.audio/APK%3ASoftapps/CAPTURE/CAPTURE.WebScraper/Scraper.py) | ❌ | HTTPError: HTTP Error 404: Not Found |

Re-run: `python3 .apk.scripts/smoke.py PODS/POD.THIN/Softapps/CAPTURE/CAPTURE.WebScraper`

<!-- smoke:sig 3fea02e86105 since 2026-11-12 00:15 EST -->
