"""provenance validates the whole schema, not only the required list."""
import pytest

from apk_webscraper import provenance


def test_build_validates_types_patterns_and_extra_fields(tmp_path):
    f = tmp_path / "x.html"
    f.write_bytes(b"hello")
    record = provenance.build(str(f), "https://example.invalid/x", "test", http_status=200)
    provenance.validate(record)
    for bad in ({"http_status": 99}, {"sha256": "XYZ"}, {"retrieved_at": "yesterday"},
                {"provenance": "guessed"}, {"surprise": 1}):
        with pytest.raises(ValueError):
            provenance.validate({**record, **bad})
    with pytest.raises(ValueError):
        provenance.build(str(f), "https://example.invalid/x", "test", http_status=700)


def test_reconstructed_record_takes_its_date(tmp_path):
    f = tmp_path / "x.html"
    f.write_bytes(b"hello")
    r = provenance.build(str(f), "https://example.invalid/x", "Scraper.py", provenance="reconstructed",
                         retrieved_at="2025-01-02T03:04:05Z", note="backfilled")
    assert r["retrieved_at"] == "2025-01-02T03:04:05Z" and r["provenance"] == "reconstructed"


def test_write_refuses_an_unreadable_file(tmp_path):
    assert provenance.write(str(tmp_path / "missing"), "https://example.invalid/", "t") is None
