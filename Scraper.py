# Part of the APK.audio project — http://APK.audio — made by Anthony Kuzub
# MIT Licence. Free, for everyone, for ever. Full text in LICENSE at the root.
"""CLI entry (display.json `entry`). The crawler itself is apk_webscraper/engine.py.

    python3 Scraper.py https://specs.amwa.tv/is-07/ [--media] [--out DIR] [--config FILE]

A common mistake (a module not installed, an unreachable host, a --config that
is not there) prints the plain problem and exits 1; see apk_webscraper/cli.py.
"""
import sys

from apk_webscraper.cli import main

if __name__ == "__main__":
    sys.exit(main())
