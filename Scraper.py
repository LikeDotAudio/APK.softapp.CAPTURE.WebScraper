# Part of the APK.audio project — http://APK.audio — made by Anthony Kuzub
# MIT Licence. Free, for everyone, for ever. Full text in LICENSE at the root.
"""CLI entry (display.json `entry`). The crawler itself is apk_webscraper/engine.py.

    python3 Scraper.py https://specs.amwa.tv/is-07/ [--media] [--out DIR] [--config FILE]
"""
import sys

from apk_webscraper.engine import main

if __name__ == "__main__":
    sys.exit(main())
