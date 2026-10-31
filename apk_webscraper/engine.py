# Part of the APK.audio project — http://APK.audio — made by Anthony Kuzub
# MIT Licence. Free, for everyone, for ever. Full text in LICENSE at the root.
"""Mirror one website to Markdown under `scrapes/`, politely.

Owns: fetching a site's HTML (and, if asked, its media), converting each page
to Markdown with `markdownify`, writing both under `<out>/<folder>/` in a tree
that mirrors the URL path, a `<file>.provenance.json` beside every fetched
file, and the corpus index `<out>/INDEX.json`. A pool of page workers, one
Markdown worker, one `Fetcher` they all go through.

THE POLITENESS CONTRACT LIVES IN ONE PLACE, `Fetcher.fetch()`:
  * the target's own robots.txt, read with urllib.robotparser, is obeyed for
    every URL, page or media, and its Crawl-delay raises the delay;
  * one rate limiter PER HOST, shared by every worker: requests to a host are
    at least `request_delay` apart IN TOTAL, not per thread;
  * one timeout, one User-Agent, one size cap (`read_capped`);
  * every fetched file gets its manifest (`provenance.write`).
Per-site tunables -- delay, threads, size cap, UA, extra disallows, media
hosts, query handling -- are `config.ini` sections keyed by host; nothing
about any one site is compiled in here (house rule: tunables in config.ini).

SCOPE: pages at or below the start URL, on the start URL's host. Media only
from that host, or from a host the site's config lists in `media_hosts`;
media is saved under `<folder>-MEDIA/<host>/<path>` so two hosts' /logo.png
cannot overwrite each other (or each other's manifest).

EVERY FETCH LEAVES A MANIFEST, AND ONLY A FETCH DOES. The Markdown conversion
gets none: it was not fetched, and a manifest on it would assert a retrieval
that never happened. PLAN-314.01.

QUERY STRINGS are dropped by `normalize_url` by default -- deliberate, so
`?utm_source=` and session links do not multiply pages -- which also collapses
`?page=2`-style listings into one page. A site that paginates by query sets
`keep_query = true` in its config section; the query then becomes part of the
saved filename (`listing@page-2`).
"""
import argparse
import configparser
import json
import os
import queue
import re
import threading
import time
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

from . import __version__, provenance

FETCHER = f"Scraper.py {__version__}"
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(PACKAGE_DIR)
DEFAULT_CONFIG = os.path.join(PACKAGE_DIR, "config.ini")
DEFAULT_OUT = os.path.join(REPO_DIR, "scrapes")
INDEX_NAME = "INDEX.json"

# Link targets that are not pages, so should not be crawled as HTML. A wire
# fact about file types, not a site list.
NON_PAGE_EXTENSIONS = (
    ".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".mp3", ".wav", ".aif", ".aiff", ".mp4", ".mov", ".css", ".js", ".ico",
)


# --------------------------------------------------------------- config

@dataclass
class SiteRules:
    """One host's tunables, from config.ini (`[DEFAULT]` overlaid by `[<host>]`)."""
    host: str
    user_agent: str = "Mozilla/5.0 (X11; Linux x86_64) WebScraper (personal archive)"
    request_delay: float = 0.5
    threads: int = 4
    max_file_size_mb: float = 2
    timeout: float = 20
    respect_robots: bool = True
    keep_query: bool = False
    extra_disallow: tuple = ()
    media_hosts: tuple = ()

    @property
    def max_fetch_bytes(self) -> int:
        return int(self.max_file_size_mb * 1024 * 1024)


def _host_key(netloc: str) -> str:
    netloc = netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _list(value: str) -> tuple:
    return tuple(v.strip() for v in re.split(r"[,\n]", value or "") if v.strip())


def load_rules(host: str, config_path: str | None = None) -> SiteRules:
    """The rules for `host` (`www.` ignored; a port, if any, is part of the key
    but `[127.0.0.1]` also matches `127.0.0.1:8000`)."""
    config = configparser.ConfigParser()
    config.read(config_path or DEFAULT_CONFIG)
    host = _host_key(host)
    section = host if config.has_section(host) else host.split(":")[0]
    get = (lambda k, fb: config.get(section, k, fallback=fb)) if config.has_section(section) \
        else (lambda k, fb: config.defaults().get(k, fb))
    base = SiteRules(host=host)
    return SiteRules(
        host=host,
        user_agent=get("user_agent", base.user_agent),
        request_delay=float(get("request_delay", base.request_delay)),
        threads=max(1, int(get("threads", base.threads))),
        max_file_size_mb=float(get("max_file_size_mb", base.max_file_size_mb)),
        timeout=float(get("timeout", base.timeout)),
        respect_robots=str(get("respect_robots", "true")).lower() in ("1", "true", "yes", "on"),
        keep_query=str(get("keep_query", "false")).lower() in ("1", "true", "yes", "on"),
        extra_disallow=_list(get("extra_disallow", "")),
        media_hosts=tuple(_host_key(h) for h in _list(get("media_hosts", ""))),
    )


# ---------------------------------------------------------------- fetch

class TooLarge(Exception):
    """A fetch that would exceed the size cap."""


class Disallowed(Exception):
    """robots.txt or the site's extra_disallow forbids this URL."""


def read_capped(response, limit):
    """The body of a `stream=True` response, at most `limit` bytes.

    Raises TooLarge on a declared Content-Length over the limit (before reading
    anything) or once the streamed body passes it, and closes the response.
    """
    try:
        declared = int(response.headers.get("Content-Length") or 0)
    except ValueError:
        declared = 0
    if declared > limit:
        response.close()
        raise TooLarge(f"Content-Length {declared} > {limit} bytes")
    body = bytearray()
    for chunk in response.iter_content(chunk_size=8192):
        body += chunk
        if len(body) > limit:
            response.close()
            raise TooLarge(f"body passed {limit} bytes")
    return bytes(body)


class RateLimiter:
    """At most one request per `interval` seconds to one host, across every
    thread that shares this object. `wait()` reserves the next slot."""

    def __init__(self, interval: float, clock=time.monotonic, sleep=time.sleep):
        self.interval = interval
        self._next = 0.0
        self._lock = threading.Lock()
        self._clock, self._sleep = clock, sleep

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            slot = max(now, self._next)
            self._next = slot + self.interval
        if slot > now:
            self._sleep(slot - now)


@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    body: bytes
    encoding: str | None = None

    def text(self) -> str:
        return self.body.decode(self.encoding or "utf-8", errors="replace")


@dataclass
class _Host:
    rules: SiteRules
    limiter: RateLimiter
    robots: urllib.robotparser.RobotFileParser | None
    # Set once robots.txt is read: no request to the host goes out before it.
    ready: threading.Event = field(default_factory=threading.Event)


class Fetcher:
    """Every request goes through here. One per crawl; thread-safe."""

    def __init__(self, config_path: str | None = None, session=None):
        self.config_path = config_path
        self.session = session or requests.Session()
        self._hosts: dict[str, _Host] = {}
        self._lock = threading.Lock()

    def host(self, url: str) -> _Host:
        parsed = urlparse(url)
        key = _host_key(parsed.netloc)
        with self._lock:
            known = self._hosts.get(key)
            if known is None:
                rules = load_rules(key, self.config_path)
                entry = _Host(rules, RateLimiter(rules.request_delay), None)
                self._hosts[key] = entry
        if known is not None:
            known.ready.wait()
            return known
        try:
            if entry.rules.respect_robots:
                entry.robots = self._read_robots(f"{parsed.scheme}://{parsed.netloc}/robots.txt", entry)
                delay = entry.robots.crawl_delay(entry.rules.user_agent)
                if delay:
                    entry.limiter.interval = max(entry.limiter.interval, float(delay))
        finally:
            entry.ready.set()
        return entry

    def _read_robots(self, robots_url: str, entry: _Host):
        """RFC 9309: a 4xx robots.txt means no rules; a 5xx or no answer means
        assume everything is disallowed (the site could not say)."""
        parser = urllib.robotparser.RobotFileParser(robots_url)
        entry.limiter.wait()
        try:
            response = self.session.get(robots_url, headers={"User-Agent": entry.rules.user_agent},
                                        timeout=entry.rules.timeout, stream=True)
            status = response.status_code
            body = read_capped(response, entry.rules.max_fetch_bytes) if status < 400 else b""
        except (requests.RequestException, TooLarge) as error:
            print(f"[robots] {robots_url} unreadable ({error}): treating the site as disallowed")
            parser.disallow_all = True
            return parser
        if 400 <= status < 500:
            parser.allow_all = True
        elif status >= 500:
            print(f"[robots] {robots_url} answered {status}: treating the site as disallowed")
            parser.disallow_all = True
        else:
            parser.parse(body.decode("utf-8", errors="replace").splitlines())
        parser.modified()
        return parser

    def allowed(self, url: str) -> bool:
        entry = self.host(url)
        path = urlparse(url).path or "/"
        if any(path.startswith(p) for p in entry.rules.extra_disallow):
            return False
        if entry.robots is not None and not entry.robots.can_fetch(entry.rules.user_agent, url):
            return False
        return True

    def fetch(self, url: str, accept_html_only: bool = False) -> FetchResult:
        """GET `url` within the contract. Raises Disallowed, TooLarge, or
        requests.RequestException (non-2xx included)."""
        entry = self.host(url)
        if not self.allowed(url):
            raise Disallowed(url)
        entry.limiter.wait()
        response = self.session.get(url, headers={"User-Agent": entry.rules.user_agent},
                                    timeout=entry.rules.timeout, stream=True)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if accept_html_only and "html" not in (content_type or "text/html"):
            response.close()
            return FetchResult(url, response.status_code, content_type, b"", response.encoding)
        body = read_capped(response, entry.rules.max_fetch_bytes)
        return FetchResult(url, response.status_code, content_type, body, response.encoding)

    def save(self, result: FetchResult, filepath: str) -> str | None:
        """Write the body and its manifest. The manifest describes the bytes on
        disk, so it is written immediately after them."""
        with open(filepath, "wb") as handle:
            handle.write(result.body)
        return provenance.write(filepath, result.url, FETCHER, http_status=result.status,
                                content_type=result.content_type or None)


# ---------------------------------------------------------------- crawl

def sanitize_folder_name(url_part: str) -> str:
    """A URL part as a safe directory name."""
    safe_name = re.sub(r"[^a-zA-Z0-9]", "-", url_part)
    safe_name = re.sub(r"-+", "-", safe_name)
    return safe_name.strip("-")


# Characters Windows refuses in a file name (macOS Finder also shows `:` as `/`),
# plus the device names Windows reserves whatever the extension.
_ILLEGAL_IN_NAME = set('<>:"|?*\\')
_RESERVED_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                   *(f"lpt{i}" for i in range(1, 10))}


def portable_segment(segment: str) -> str:
    """One path segment as a name every OS can check out.

    URL paths carry `|` (RecordingHacks tag unions), `:` (product names such as
    DPA `d:facto`) and trailing dots, all illegal on Windows. Each offending
    character is percent-encoded rather than replaced, so the mapping is
    lossless (`unquote` reads the URL path back)."""
    out = "".join(f"%{ord(ch):02X}" if ch in _ILLEGAL_IN_NAME or ord(ch) < 32 else ch for ch in segment)
    if out and out[-1] in ". ":
        out = out[:-1] + f"%{ord(out[-1]):02X}"
    if out.split(".", 1)[0].lower() in _RESERVED_NAMES:
        out = f"%{ord(out[0]):02X}" + out[1:]
    return out


def portable_path(rel: str) -> str:
    """`portable_segment` applied to every segment of a `/`-separated path."""
    return "/".join(portable_segment(part) for part in rel.split("/"))


def extract_main_content(soup) -> str:
    """The page's main content, so boilerplate stays out of the Markdown."""
    for junk in soup.find_all(["script", "style", "noscript"]):
        junk.decompose()
    for selector in [{"id": "column"}, {"id": "content"}]:
        main = soup.find("div", attrs=selector)
        if main:
            return str(main)
    main = soup.find("main") or soup.find("article") or soup.body
    return str(main) if main else str(soup)


def plan(start_url: str) -> tuple[str, str]:
    """(effective base URL, output folder name) for a start URL. A trailing
    vN.N.N segment is dropped so every version of a spec lands in one folder."""
    parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}/"
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) > 1 and re.match(r"^v\d+(\.\d+){0,2}$", parts[-1]):
        parts = parts[:-1]
    base_path = "/".join(parts)
    effective = urljoin(base, base_path)
    folder = sanitize_folder_name(urlparse(effective).netloc + "/" + urlparse(effective).path.strip("/")) \
        if base_path else sanitize_folder_name(parsed.netloc)
    return effective, folder or "root"


@dataclass
class Crawl:
    """One run: its scope, its output folders, and the state its workers share.
    Nothing is module-global, so a test (or CAPTURE.crawler) can run several."""
    start_url: str
    out: str = DEFAULT_OUT
    media: bool = False
    config_path: str | None = None
    folder: str | None = None
    fetcher: Fetcher | None = None
    verbose: bool = True
    # Where progress lines go (a GUI's log, say); print when None.
    logger: object = None
    # Called with the path of every file written (pages, media, Markdown).
    on_file: object = None

    scheme: str = field(init=False)
    base_url: str = field(init=False)
    rules: SiteRules = field(init=False)

    def __post_init__(self):
        parsed = urlparse(self.start_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"not an http(s) URL: {self.start_url!r}")
        self.scheme = parsed.scheme
        self.fetcher = self.fetcher or Fetcher(self.config_path)
        self.rules = load_rules(parsed.netloc, self.config_path)
        effective, folder = plan(self.start_url)
        self.base_url = self.normalize_url(effective)
        self.folder = self.folder or folder
        self.html_dir = os.path.join(self.out, self.folder)
        self.md_dir = os.path.join(self.out, self.folder + "-MD")
        self.media_dir = os.path.join(self.out, self.folder + "-MEDIA")
        self.visited: set[str] = set()
        self.visited_lock = threading.Lock()
        self.fs_lock = threading.Lock()
        self.url_queue: queue.Queue = queue.Queue()
        self.md_queue: queue.Queue = queue.Queue()
        self.stats = {"pages": 0, "media": 0, "skipped": 0}
        self.stats_lock = threading.Lock()

    def log(self, message: str) -> None:
        if self.logger is not None:
            self.logger(message)
        elif self.verbose:
            print(message)

    def wrote(self, path: str) -> None:
        if self.on_file is not None:
            self.on_file(path)

    def count(self, key: str) -> None:
        with self.stats_lock:
            self.stats[key] += 1

    # -- URLs
    def normalize_url(self, url: str) -> str:
        """One spelling per page: the start URL's scheme (so an http-only site
        stays http), no `www.`, no trailing slash, no fragment; the query only
        when the site's config keeps it."""
        parsed = urlparse(url)
        netloc = _host_key(parsed.netloc)
        path = parsed.path.rstrip("/") or "/"
        keep = getattr(self, "rules", None) is not None and self.rules.keep_query
        query = f"?{parsed.query}" if keep and parsed.query else ""
        return f"{self.scheme}://{netloc}{path}{query}"

    def is_in_scope(self, url: str) -> bool:
        """A crawlable page at or below the base URL, on its host."""
        base = self.base_url.rstrip("/")
        bare = url.split("?", 1)[0]
        if bare != base and not bare.startswith(base + "/"):
            return False
        return not urlparse(url).path.lower().endswith(NON_PAGE_EXTENSIONS)

    def media_allowed_host(self, url: str) -> bool:
        host = _host_key(urlparse(url).netloc)
        return host == self.rules.host or host in self.rules.media_hosts

    def page_path(self, url: str) -> str:
        parsed = urlparse(url)
        rel = portable_path(parsed.path.lstrip("/")) or "index.html"
        if parsed.query:
            rel += "@" + sanitize_folder_name(parsed.query)
        return os.path.join(self.html_dir, rel)

    def claim(self, url: str) -> bool:
        with self.visited_lock:
            if url in self.visited:
                return False
            self.visited.add(url)
            return True

    # -- workers
    def page_worker(self) -> None:
        while True:
            url = self.url_queue.get()
            try:
                if url is None:
                    return
                self.process_page(url)
            finally:
                self.url_queue.task_done()

    def process_page(self, url: str) -> None:
        url = self.normalize_url(url)
        if not self.is_in_scope(url) or not self.claim(url):
            return
        self.log(f"[Downloader] Downloading: {url}")
        try:
            result = self.fetcher.fetch(url, accept_html_only=True)
        except Disallowed:
            self.log(f"[Downloader] robots/config disallow: {url}")
            self.count("skipped")
            return
        except TooLarge as error:
            self.log(f"[Downloader] Skipping page over {self.rules.max_file_size_mb} MB '{url}': {error}")
            self.count("skipped")
            return
        except requests.RequestException as error:
            self.log(f"[Downloader] Failed to download '{url}': {error}")
            self.count("skipped")
            return
        if not result.body:
            self.log(f"[Downloader] Skipping non-HTML response: {url}")
            return

        filepath = self.prepare_path(self.page_path(url))
        if filepath is None:
            return
        try:
            self.fetcher.save(result, filepath)
        except OSError as error:
            self.log(f"[Downloader] Error writing '{filepath}': {error}")
            return
        self.count("pages")
        self.wrote(filepath)

        page_text = result.text()
        soup = BeautifulSoup(page_text, "html.parser")
        if self.media:
            self.download_media(soup, url)
        for link in soup.find_all("a", href=True):
            next_url = self.normalize_url(urljoin(url, link["href"]))
            if self.is_in_scope(next_url):
                with self.visited_lock:
                    seen = next_url in self.visited
                if not seen:
                    self.url_queue.put(next_url)
        # extract_main_content() mutates `soup`, so it runs after the link scan.
        self.md_queue.put((extract_main_content(soup), os.path.relpath(filepath, self.html_dir)))

    def prepare_path(self, resolved: str) -> str | None:
        """Make room for `resolved`. A site path can be a page AND the parent of
        pages ('/mics/Alesis' and '/mics/Alesis/AM51'): whichever role comes
        second moves the page to '<dir>/index.html', and its manifest moves with
        it. The current page always keeps its own path."""
        try:
            with self.fs_lock:
                parent = os.path.dirname(resolved)
                if parent and os.path.isfile(parent):
                    self.log(f"[Downloader] '{parent}' is needed as a directory: moving it to its index.html")
                    temp = parent + ".tmp"
                    os.rename(parent, temp)
                    os.makedirs(parent, exist_ok=True)
                    moved_to = os.path.join(parent, "index.html")
                    os.rename(temp, moved_to)
                    old_manifest = provenance.manifest_path(parent)
                    if os.path.isfile(old_manifest):
                        os.rename(old_manifest, provenance.manifest_path(moved_to))
                if os.path.isdir(resolved):
                    resolved = os.path.join(resolved, "index.html")
                os.makedirs(os.path.dirname(resolved), exist_ok=True)
            return resolved
        except OSError as error:
            self.log(f"[Downloader] Filesystem error preparing '{resolved}': {error}")
            return None

    def download_media(self, soup, page_url: str) -> None:
        for tag in soup.find_all(["img", "video", "audio", "source"]):
            source = tag.get("src")
            if not source:
                continue
            media_url = urljoin(page_url, source).split("#")[0].split("?")[0]
            parsed = urlparse(media_url)
            if parsed.scheme not in ("http", "https") or not parsed.path.strip("/"):
                continue
            if not self.media_allowed_host(media_url):
                self.log(f"[Downloader] Media off the target host, not fetched: {media_url}")
                self.count("skipped")
                continue
            if not self.claim(media_url):
                continue
            try:
                result = self.fetcher.fetch(media_url)
            except (Disallowed, TooLarge, requests.RequestException) as error:
                self.log(f"[Downloader] Media not fetched '{media_url}': {error!r}")
                self.count("skipped")
                continue
            filepath = os.path.join(self.media_dir, _host_key(parsed.netloc).replace(":", "_"),
                                    portable_path(parsed.path.lstrip("/")))
            filepath = self.prepare_path(filepath)
            if filepath is None:
                continue
            try:
                self.fetcher.save(result, filepath)
                self.count("media")
            except OSError as error:
                self.log(f"[Downloader] Error writing media '{filepath}': {error}")

    def markdown_worker(self) -> None:
        while True:
            item = self.md_queue.get()
            try:
                if item is None:
                    return
                html, rel = item
                # Only strip a genuine HTML extension: 'microphones/t.bone' stays 't.bone.md'.
                stem, extension = os.path.splitext(rel)
                md_rel = (stem if extension.lower() in (".html", ".htm") else rel) + ".md"
                filepath = os.path.join(self.md_dir, md_rel)
                try:
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, "w", encoding="utf-8") as handle:
                        handle.write(markdownify(html, heading_style="ATX").strip())
                    self.wrote(filepath)
                    # DELIBERATELY no provenance sidecar: a derivative, not a fetch.
                except OSError as error:
                    self.log(f"[Markdown] Error writing '{filepath}': {error}")
            finally:
                self.md_queue.task_done()

    # -- run
    def run(self, stitch: bool = True) -> dict:
        for directory in (self.html_dir, self.md_dir) + ((self.media_dir,) if self.media else ()):
            os.makedirs(directory, exist_ok=True)
        self.log(f"Target URL: {self.start_url}\nBase URL: {self.base_url}\nOutput: {self.html_dir}")
        converter = threading.Thread(target=self.markdown_worker, daemon=True)
        converter.start()
        workers = [threading.Thread(target=self.page_worker, daemon=True) for _ in range(self.rules.threads)]
        for worker in workers:
            worker.start()
        self.url_queue.put(self.normalize_url(self.start_url))
        self.url_queue.join()
        for _ in workers:
            self.url_queue.put(None)
        for worker in workers:
            worker.join()
        self.md_queue.put(None)
        converter.join()
        if stitch:
            concatenate_markdown_files(self.md_dir, self.rules.max_fetch_bytes, self.log)
        update_index(self.out, self.folder, {
            "source_url": self.base_url,
            "html": self.folder, "markdown": self.folder + "-MD",
            "media": self.folder + "-MEDIA" if self.media else None,
            "last_run": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tool": FETCHER,
            "pages": self.stats["pages"],
        })
        return dict(self.stats)


def concatenate_markdown_files(md_directory: str, max_bytes: int = 2 * 1024 * 1024, log=print) -> int:
    """Stitch the Markdown into COMBINED_ARCHIVE_partN.md, a new part at `max_bytes`."""
    for old in os.listdir(md_directory):
        if old.startswith("COMBINED_ARCHIVE_part") and old.endswith(".md"):
            os.remove(os.path.join(md_directory, old))
    part, size, outfile = 1, 0, None
    for root, dirs, files in os.walk(md_directory):
        dirs.sort()
        for name in sorted(files):
            if not name.endswith(".md") or name.startswith("COMBINED_ARCHIVE"):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8") as infile:
                    content = infile.read()
            except OSError as error:
                log(f"Error reading '{path}': {error}")
                continue
            block = f"\n-----------------\n{os.path.relpath(path, md_directory)}\n------------------------\n\n{content}\n"
            block_bytes = len(block.encode("utf-8"))
            if outfile is not None and size + block_bytes > max_bytes and size > 0:
                outfile.close()
                part, size, outfile = part + 1, 0, None
            if outfile is None:
                outfile = open(os.path.join(md_directory, f"COMBINED_ARCHIVE_part{part}.md"), "w", encoding="utf-8")
            outfile.write(block)
            size += block_bytes
    if outfile is not None:
        outfile.close()
        return part
    return 0


def update_index(out: str, folder: str, entry: dict) -> str:
    """Record one corpus in `<out>/INDEX.json` (schema: corpus-index.schema.json).
    Consumers find a corpus by its folder key here instead of a hard-coded path."""
    path = os.path.join(out, INDEX_NAME)
    try:
        with open(path, encoding="utf-8") as handle:
            index = json.load(handle)
    except (OSError, ValueError):
        index = {"schemaVersion": 1, "corpora": {}}
    index.setdefault("corpora", {})[folder] = {**index["corpora"].get(folder, {}), **entry}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=1, sort_keys=True)
        handle.write("\n")
    return path


def crawl(start_url: str, out: str = DEFAULT_OUT, media: bool = False,
          config_path: str | None = None, folder: str | None = None, verbose: bool = True,
          logger=None, on_file=None) -> dict:
    """The importable entry point: mirror `start_url` into `out`. Returns the stats.
    `logger(line)` receives progress instead of stdout; `on_file(path)` each file written."""
    return Crawl(start_url, out=out, media=media, config_path=config_path, folder=folder,
                 verbose=verbose, logger=logger, on_file=on_file).run()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Mirror one site to HTML + Markdown, politely (robots.txt, "
                                                 "per-host rate limit, size cap, provenance manifests).")
    parser.add_argument("url", help="the starting URL")
    parser.add_argument("--media", dest="media", action="store_true",
                        help="also fetch images/video/audio from the target host (and its config's media_hosts)")
    parser.add_argument("--no-media", dest="media", action="store_false", help="pages only (default)")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"output folder (default: {DEFAULT_OUT})")
    parser.add_argument("--config", default=None, help=f"site rules (default: {DEFAULT_CONFIG})")
    parser.add_argument("--folder", default=None, help="output folder name (default: derived from the URL)")
    parser.add_argument("--version", action="version", version=FETCHER)
    parser.set_defaults(media=False)
    args = parser.parse_args(argv)
    stats = crawl(args.url, out=args.out, media=args.media, config_path=args.config, folder=args.folder)
    print(f"Done: {stats}")
    return 0
