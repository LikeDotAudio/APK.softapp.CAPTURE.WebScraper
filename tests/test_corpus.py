"""The committed corpus keeps its contracts: one layout, a valid index, valid manifests."""
import json
import os
import subprocess

import jsonschema

from apk_webscraper import backfill, provenance

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRAPES = os.path.join(REPO, "scrapes")


def test_index_is_valid_and_names_folders_that_exist():
    index = json.load(open(os.path.join(SCRAPES, "INDEX.json")))
    jsonschema.Draft202012Validator(json.load(open(os.path.join(REPO, "corpus-index.schema.json")))).validate(index)
    for key, entry in index["corpora"].items():
        assert os.path.isdir(os.path.join(SCRAPES, entry["html"])), key
        assert os.path.isdir(os.path.join(SCRAPES, entry["markdown"])), key
    # the two folders other repos cite by name
    assert "specs-amwa-tv-is-07" in index["corpora"] and "specs-amwa-tv-is-12" in index["corpora"]


def test_old_url_as_path_layout_is_gone():
    assert not os.path.exists(os.path.join(SCRAPES, "is-07"))
    assert not os.path.exists(os.path.join(SCRAPES, "is-07-MD"))


def test_every_manifest_in_the_corpus_validates():
    count = 0
    for root, _, files in os.walk(SCRAPES):
        for name in files:
            if provenance.is_manifest(name):
                provenance.validate(json.load(open(os.path.join(root, name), encoding="utf-8")))
                assert os.path.isfile(os.path.join(root, name[: -len(provenance.SUFFIX)])), name
                count += 1
    assert count > 4000


def test_every_fetched_file_in_an_indexed_corpus_has_a_manifest():
    index = json.load(open(os.path.join(SCRAPES, "INDEX.json")))
    for entry in index["corpora"].values():
        missing = list(backfill.candidates(os.path.join(SCRAPES, entry["html"]), ("Datamodel",)))
        assert missing == [], missing[:5]


def test_backfill_writes_reconstructed_records_dated_by_git(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_DATE": "2025-05-06T07:08:09+00:00",
                            "GIT_COMMITTER_DATE": "2025-05-06T07:08:09+00:00"})
    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    (tmp_path / "scrapes" / "site" / "docs").mkdir(parents=True)
    (tmp_path / "scrapes" / "site" / "docs" / "index.html").write_text("<p>docs</p>")
    (tmp_path / "scrapes" / "site" / "docs" / "page.md").write_text("derivative")
    git("add", ".")
    git("commit", "-q", "-m", "x")
    tally = backfill.backfill(str(tmp_path), "scrapes/site", "https://example.invalid/")
    assert tally == {"written": 1, "no_date": 0, "failed": 0}
    record = json.load(open(tmp_path / "scrapes" / "site" / "docs" / "index.html.provenance.json"))
    assert record["source_url"] == "https://example.invalid/docs"
    assert record["retrieved_at"] == "2025-05-06T07:08:09Z"
    assert record["provenance"] == "reconstructed" and record["http_status"] is None
    assert not (tmp_path / "scrapes" / "site" / "docs" / "page.md.provenance.json").exists()
