"""CAPTURE.WebScraper as a library: `from apk_webscraper import crawl`.

The one polite crawler of the monorepo (robots.txt, per-host rate limit, size
cap, provenance manifests). CAPTURE.crawler's Web Crawler tab calls it; the CLI
is `Scraper.py` / `python3 -m apk_webscraper`.
"""
__version__ = "2.0.0"


def crawl(*args, **kwargs):
    from .engine import crawl as _crawl
    return _crawl(*args, **kwargs)
