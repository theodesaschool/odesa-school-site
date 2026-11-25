"""Общие настройки тестов: поднимаем локальный сервер с сайтом на свободном порту."""
import functools
import http.server
import json
import socketserver
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def site_url():
    handler = functools.partial(_QuietHandler, directory=str(ROOT))
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="session")
def base_url(site_url):
    # pytest-playwright подставляет base_url в page.goto("/...")
    return site_url


def load_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def paintings():
    return load_json("paintings.json")


@pytest.fixture(scope="session")
def artists():
    return load_json("artists.json")


@pytest.fixture(scope="session")
def seo_config():
    return load_json("tools/seo.config.json")
