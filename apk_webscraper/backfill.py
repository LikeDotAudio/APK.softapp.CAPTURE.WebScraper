# Part of the APK.audio project — http://APK.audio — made by Anthony Kuzub
# MIT Licence. Free, for everyone, for ever. Full text in LICENSE at the root.
"""Backfill `"provenance": "reconstructed"` manifests for a corpus fetched before
manifests existed.

    python3 -m apk_webscraper.backfill scrapes/specs-amwa-tv-is-07 https://specs.amwa.tv/ \
        [--alias NEWPREFIX=OLDPREFIX] [--exclude NAME] [--note TEXT] [--dry-run]

Every fetched file under the tree (not Markdown -- a derivative --, not an
existing manifest, not an `--exclude`d folder of authored files) gets a sidecar
whose fields are what can be known now and say so:
  * source_url  -- the URL the scraper's mirror rule maps this path back to
                   (`<prefix><path>`; `<dir>/index.html` is the page `<dir>`);
  * retrieved_at -- the date git first recorded the file: the fetch was at or
                   before it, never after (`--alias` lets a file that moved
                   between layouts use its old path's date);
  * http_status / content_type -- null: not observed;
  * content_length / sha256 -- of the bytes on disk now;
  * provenance  -- "reconstructed", with a note saying how.
A file that already has a manifest is left alone. Refusal over fabrication: a
reconstructed record never wears a fetched one's clothes.
"""
import argparse
import os
import subprocess
import sys

from . import provenance

FETCHER = "Scraper.py (before 2.0.0)"


def first_added(repo: str, paths_under: str) -> dict:
    """{path: ISO date} of the commit that first added each file under `paths_under`."""
    out = subprocess.run(
        ["git", "-c", "core.quotepath=off", "log", "--diff-filter=A", "--name-only",
         "--format=@%aI", "--", paths_under],
        cwd=repo, capture_output=True, text=True, check=True).stdout
    dates, current = {}, None
    for line in out.splitlines():
        if line.startswith("@"):
            current = line[1:]
        elif line.strip():
            dates[line] = current            # log is newest first: the last seen is the first add
    return dates


def to_utc_z(iso: str) -> str:
    from datetime import datetime, timezone
    return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def source_url(prefix: str, rel: str) -> str:
    if os.path.basename(rel) == "index.html":
        rel = os.path.dirname(rel)
    return prefix.rstrip("/") + "/" + rel if rel else prefix


def candidates(tree: str, exclude: tuple):
    for root, dirs, files in os.walk(tree):
        dirs[:] = sorted(d for d in dirs if d not in exclude)
        for name in sorted(files):
            if name.endswith(".md") or provenance.is_manifest(name):
                continue
            path = os.path.join(root, name)
            if os.path.isfile(provenance.manifest_path(path)):
                continue
            yield path


def backfill(repo: str, tree: str, prefix: str, aliases=(), exclude=(), note=None, dry_run=False) -> dict:
    tally = {"written": 0, "no_date": 0, "failed": 0}
    dates = first_added(repo, tree)
    for old_prefix in {old for _, old in aliases}:
        dates.update({k: v for k, v in first_added(repo, old_prefix).items() if k not in dates})
    for path in candidates(os.path.join(repo, tree), tuple(exclude)):
        rel_repo = os.path.relpath(path, repo)
        when = dates.get(rel_repo)
        for new, old in aliases:
            if when is None and rel_repo.startswith(new):
                when = dates.get(old + rel_repo[len(new):])
        if when is None:
            tally["no_date"] += 1
            continue
        rel = os.path.relpath(path, os.path.join(repo, tree))
        text = note or ("Backfilled 2026-10-30 by apk_webscraper.backfill: source_url is the URL the "
                        "mirror path maps back to, retrieved_at is the date git first recorded the file "
                        "(the fetch was at or before it), http_status and content_type were not recorded.")
        if dry_run:
            tally["written"] += 1
            continue
        target = provenance.write(path, source_url(prefix, rel), FETCHER, provenance="reconstructed",
                                  retrieved_at=to_utc_z(when), note=text)
        tally["written" if target else "failed"] += 1
    return tally


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tree", help="corpus folder, relative to the repo root (e.g. scrapes/specs-amwa-tv-is-07)")
    parser.add_argument("prefix", help="the URL the tree's root mirrors (e.g. https://specs.amwa.tv/)")
    parser.add_argument("--alias", action="append", default=[],
                        help="NEWPREFIX=OLDPREFIX: take a moved file's date from its old path")
    parser.add_argument("--exclude", action="append", default=[], help="folder name of authored files to skip")
    parser.add_argument("--note", default=None)
    parser.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    from .cli_problems import fail
    if not os.path.isdir(os.path.join(args.repo, args.tree)):
        fail("file_unreadable", detail=f"{os.path.join(args.repo, args.tree)}: no such folder", subject="tree",
             fix=["Give the corpus folder relative to the repo root (e.g. scrapes/specs-amwa-tv-is-07), "
                  "or point --repo at the checkout that holds it."])
    bad = [a for a in args.alias if "=" not in a]
    if bad:
        fail("bad_input", detail=f"--alias {bad[0]!r} has no '='", subject="--alias",
             fix=["Write it as NEWPREFIX=OLDPREFIX."])
    aliases = [tuple(a.split("=", 1)) for a in args.alias]
    try:
        print(backfill(args.repo, args.tree, args.prefix, aliases, args.exclude, args.note, args.dry_run))
    except subprocess.CalledProcessError as error:
        fail("bad_input", detail=f"git log failed in {args.repo}: {(error.stderr or '').strip()}", subject="--repo",
             fix=["Run it inside a git checkout of the corpus (or pass --repo with one): the dates come from git."])
    return 0


if __name__ == "__main__":
    # A common mistake prints apkaudio_contracts.problems' problem_text (cli_problems.py), not a traceback.
    from .cli_problems import guarded
    sys.exit(guarded(main))
