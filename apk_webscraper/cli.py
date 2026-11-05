# Part of the APK.audio project — http://APK.audio — made by Anthony Kuzub
# MIT Licence. Free, for everyone, for ever. Full text in LICENSE at the root.
"""The command line: `Scraper.py`, `python3 -m apk_webscraper` and the
`apk-webscrape` console script all land here.

The crawler (engine.py) imports requests, bs4 and markdownify at the top, so
it is imported INSIDE the guard: a module not installed, an unreachable host,
an output folder that cannot be made print apkaudio_contracts.problems'
problem_text with the fix and exit 1 (cli_problems.guarded), not a traceback
(ROAD-3522). APK_DEBUG=1 keeps the traceback of anything unexpected.
"""
import sys

from .cli_problems import guarded


def main(argv=None) -> int:
    def run():
        from .engine import main as crawl_main
        return crawl_main(argv)
    return guarded(run)


if __name__ == "__main__":
    sys.exit(main())
