"""A local site for the crawler: no external request is ever made by these tests."""
import http.server
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Site:
    """Serves `pages` ({path: (status, content_type, body)}) and records every request."""

    def __init__(self, pages):
        self.pages = pages
        self.requests = []          # (monotonic time, path)
        site = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                site.requests.append((time.monotonic(), self.path))
                status, ctype, body = site.pages.get(self.path, (404, "text/plain", b"not found"))
                if isinstance(body, str):
                    body = body.encode()
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def paths(self):
        return [p for _, p in self.requests]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def make_site():
    sites = []

    def make(pages):
        site = Site(pages)
        sites.append(site)
        return site
    yield make
    for site in sites:
        site.close()


@pytest.fixture
def config(tmp_path):
    """Site rules for 127.0.0.1: fast but still rate limited."""
    def write(extra=""):
        path = tmp_path / "config.ini"
        path.write_text("[DEFAULT]\nrequest_delay = 0.05\nthreads = 4\nmax_file_size_mb = 0.01\ntimeout = 5\n"
                        "[127.0.0.1]\n" + extra)
        return str(path)
    return write
