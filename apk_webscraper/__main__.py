# Part of the APK.audio project — http://APK.audio — made by Anthony Kuzub
# MIT Licence. Free, for everyone, for ever. Full text in LICENSE at the root.
"""`python3 -m apk_webscraper URL` — the same CLI as Scraper.py. A common mistake
prints apkaudio_contracts.problems' problem_text, not a traceback (cli.py)."""
import sys

from .cli import main

sys.exit(main())
