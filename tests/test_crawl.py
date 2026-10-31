"""The crawl against a local three-page site: tree, robots, scope, cap, rate, manifests."""
import json
import os

import jsonschema
import pytest

from apk_webscraper import engine as c
from apk_webscraper import provenance

HTML = "text/html; charset=utf-8"


def page(body, links=(), imgs=()):
    a = "".join(f'<a href="{h}">{h}</a>' for h in links)
    i = "".join(f'<img src="{s}">' for s in imgs)
    return f"<html><body><div id='content'><h1>{body}</h1>{a}{i}</div></body></html>"


def three_pages(robots="User-agent: *\nDisallow: /private\n", other=None):
    other_img = f"{other}/logo.png" if other else "/x.png"
    return {
        "/robots.txt": (200, "text/plain", robots),
        "/": (200, HTML, page("home", ["/a", "/private/secret", "/big", "https://elsewhere.invalid/"],
                              ["/img/logo.png", other_img])),
        "/a": (200, HTML, page("A", ["/a/b", "/?page=2"])),
        "/a/b": (200, HTML, page("B", ["/", "/a"])),
        "/private/secret": (200, HTML, page("secret")),
        "/big": (200, HTML, "x" * 20000),           # over the 0.01 MB cap
        "/img/logo.png": (200, "image/png", b"\x89PNG-same-host"),
        "/logo.png": (200, "image/png", b"\x89PNG-other-host"),
    }


def run(site, tmp_path, config_path, media=False):
    out = tmp_path / "scrapes"
    stats = c.crawl(site.url + "/", out=str(out), media=media, config_path=config_path, verbose=False)
    return out, stats


def test_mirror_tree_robots_scope_and_cap(make_site, tmp_path, config):
    site = make_site(three_pages())
    out, stats = run(site, tmp_path, config())
    folder = out / c.sanitize_folder_name(f"127.0.0.1:{site.port}")
    # The /a page became /a/index.html once /a/b needed /a as a directory.
    assert (folder / "index.html").is_file()
    assert (folder / "a" / "index.html").is_file()
    assert (folder / "a" / "b").is_file()
    # its manifest moved with it
    assert (folder / "a" / "index.html.provenance.json").is_file()
    assert not (folder / "a.provenance.json").exists()
    assert "/private/secret" not in site.paths()          # robots.txt obeyed
    assert not (folder / "big").exists()                  # size cap
    assert stats["pages"] == 3
    assert (out / (folder.name + "-MD") / "a" / "b.md").read_text().startswith("# B")
    assert list((out / (folder.name + "-MD")).glob("COMBINED_ARCHIVE_part*.md"))


def test_every_manifest_validates_against_the_schema(make_site, tmp_path, config):
    site = make_site(three_pages())
    out, _ = run(site, tmp_path, config(), media=True)
    manifests = list(out.rglob("*" + provenance.SUFFIX))
    assert len(manifests) == 4                              # 3 pages + 1 same-host image
    for path in manifests:
        record = json.loads(path.read_text())
        provenance.validate(record)
        jsonschema.Draft202012Validator(provenance.SCHEMA).validate(record)
        assert record["fetcher"] == c.FETCHER and record["provenance"] == "fetched"
    assert not list(out.rglob("*.md" + provenance.SUFFIX))   # derivatives carry none


def test_media_is_scoped_to_the_target_host_and_keeps_the_host(make_site, tmp_path, config):
    other = make_site({"/robots.txt": (404, "text/plain", ""), "/logo.png": (200, "image/png", b"other")})
    site = make_site(three_pages(other=other.url))
    out, stats = run(site, tmp_path, config(), media=True)
    media = out / (c.sanitize_folder_name(f"127.0.0.1:{site.port}") + "-MEDIA")
    assert (media / f"127.0.0.1_{site.port}" / "img" / "logo.png").read_bytes() == b"\x89PNG-same-host"
    assert other.paths() == []                             # never touched the other host
    # ...unless that host is listed for the site
    out2 = tmp_path / "second"
    c.crawl(site.url + "/", out=str(out2), media=True, verbose=False,
            config_path=config(f"media_hosts = 127.0.0.1:{other.port}\n"))
    # 127.0.0.1 with another port is another host; media_hosts names it explicitly
    assert "/logo.png" in other.paths()


def test_rate_limit_is_per_host_across_all_workers(make_site, tmp_path, config):
    pages = {"/robots.txt": (200, "text/plain", "")}
    pages["/"] = (200, HTML, page("hub", [f"/p{i}" for i in range(12)]))
    for i in range(12):
        pages[f"/p{i}"] = (200, HTML, page(f"p{i}"))
    site = make_site(pages)
    run(site, tmp_path, config("request_delay = 0.1\nthreads = 4\n"))
    times = sorted(t for t, p in site.requests)
    assert len(times) == 14
    # 14 requests at one per 0.1 s take >= 1.3 s however many workers there are;
    # a per-worker delay with 4 workers would finish in about a quarter of that.
    # (Arrival gaps are noisy -- connection setup -- so the span is what is asserted.)
    assert times[-1] - times[0] >= 0.9 * 13 * 0.1, times[-1] - times[0]


def test_rate_limiter_reserves_one_slot_per_interval_across_threads():
    import threading
    clock = [0.0]
    slept = []
    limiter = c.RateLimiter(0.5, clock=lambda: clock[0], sleep=slept.append)
    threads = [threading.Thread(target=limiter.wait) for _ in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert sorted(slept) == [0.5 * i for i in range(1, 8)]   # first goes now, the rest queue


def test_crawl_delay_raises_the_interval(make_site, config):
    site = make_site({"/robots.txt": (200, "text/plain", "User-agent: *\nCrawl-delay: 2\n")})
    fetcher = c.Fetcher(config())
    assert fetcher.host(site.url + "/").limiter.interval == 2.0


def test_robots_5xx_disallows_and_4xx_allows(make_site, config):
    down = make_site({"/robots.txt": (503, "text/plain", "")})
    assert not c.Fetcher(config()).allowed(down.url + "/anything")
    none = make_site({})
    assert c.Fetcher(config()).allowed(none.url + "/anything")


def test_extra_disallow_from_config(make_site, config):
    site = make_site({"/robots.txt": (404, "text/plain", "")})
    fetcher = c.Fetcher(config("extra_disallow = /feed/, /wp-admin/\n"))
    assert not fetcher.allowed(site.url + "/feed/x")
    assert fetcher.allowed(site.url + "/docs")


def test_query_dropped_by_default_kept_when_configured(make_site, tmp_path, config):
    site = make_site(three_pages())
    crawl = c.Crawl(site.url + "/", out=str(tmp_path), config_path=config(), verbose=False)
    assert crawl.normalize_url(site.url + "/list?page=2") == site.url + "/list"
    keep = c.Crawl(site.url + "/", out=str(tmp_path), config_path=config("keep_query = true\n"), verbose=False)
    assert keep.normalize_url(site.url + "/list?page=2") == site.url + "/list?page=2"
    assert keep.page_path(site.url + "/list?page=2").endswith("list@page-2")


def test_corpus_index_is_written_and_valid(make_site, tmp_path, config):
    site = make_site(three_pages())
    out, _ = run(site, tmp_path, config())
    index = json.loads((out / "INDEX.json").read_text())
    schema = json.load(open(os.path.join(os.path.dirname(c.PACKAGE_DIR), "corpus-index.schema.json")))
    jsonschema.Draft202012Validator(schema).validate(index)
    (entry,) = index["corpora"].values()
    assert entry["source_url"] == site.url + "/" and entry["tool"] == c.FETCHER and entry["pages"] == 3


def test_cli_has_no_prompt(make_site, tmp_path, config, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("prompted"))
    site = make_site(three_pages())
    assert c.main([site.url + "/", "--no-media", "--out", str(tmp_path / "o"), "--config", config()]) == 0


def test_two_crawls_share_no_state(make_site, tmp_path, config):
    site = make_site(three_pages())
    first = c.Crawl(site.url + "/", out=str(tmp_path / "1"), config_path=config(), verbose=False)
    second = c.Crawl(site.url + "/", out=str(tmp_path / "2"), config_path=config(), verbose=False)
    first.run()
    assert second.visited == set()
    assert second.run()["pages"] == 3


def test_plan_names_folders_like_the_kept_corpora():
    assert c.plan("https://specs.amwa.tv/is-07/") == ("https://specs.amwa.tv/is-07", "specs-amwa-tv-is-07")
    assert c.plan("https://specs.amwa.tv/is-12/v1.0.0")[1] == "specs-amwa-tv-is-12"
