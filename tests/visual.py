#!/usr/bin/env python3
"""Сравнение внешнего вида сайта «до» и «после».

  .venv/bin/python tests/visual.py baseline   # снять эталонные снимки (до изменений)
  .venv/bin/python tests/visual.py compare    # снять снимки сейчас и сравнить с эталоном

Снимки лежат в tests/screenshots/ (в git не попадают). Для страниц, которые
отличаются, в tests/screenshots/diff/ появится картинка: изменённые места — красным.
"""
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tests" / "screenshots"
PAGES = [
    "index.html", "catalog.html", "artists.html", "how-to-buy.html", "about.html", "contact.html",
    "painting/lomykin-winter-morning.html", "painting/shelyuto-above-the-dnipro.html", "artist/shelyuto.html",
]
VIEWPORTS = {"desktop": (1280, 800), "mobile": (375, 812)}
LANGS = ["en", "ua"]
# блоки, которые меняются сами по себе (случайные «похожие работы»)
MASK = ["#pg-also-grid"]
TOLERANCE = 0.001  # доля отличающихся пикселей, ниже которой считаем «без изменений»


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def name_for(path, vp, lang):
    return f"{path.replace('/', '__').replace('.html', '')}--{vp}--{lang}.png"


def capture(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    httpd, url = serve()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp, (w, h) in VIEWPORTS.items():
            for lang in LANGS:
                ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=(vp == "mobile"))
                ctx.add_init_script(f"localStorage.setItem('lang', '{lang}')")
                # одинаковая «случайность» при каждом запуске, чтобы снимки были сравнимы
                ctx.add_init_script("(() => { let s = 42; Math.random = () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646; })()")
                page = ctx.new_page()
                for path in PAGES:
                    page.goto(f"{url}/{path}", wait_until="networkidle")
                    page.evaluate("document.fonts.ready")
                    masks = [page.locator(m) for m in MASK if page.locator(m).count()]
                    page.screenshot(path=str(out_dir / name_for(path, vp, lang)), full_page=True,
                                    animations="disabled", mask=masks)
                ctx.close()
        browser.close()
    httpd.shutdown()


def compare():
    base, cur, diff_dir = SHOTS / "baseline", SHOTS / "current", SHOTS / "diff"
    if not base.exists():
        sys.exit("Нет эталонных снимков: сначала запустите  tests/visual.py baseline")
    capture(cur)
    diff_dir.mkdir(exist_ok=True)
    for old in diff_dir.glob("*.png"):
        old.unlink()
    changed = 0
    for b in sorted(base.glob("*.png")):
        c = cur / b.name
        if not c.exists():
            print(f"НЕТ СНИМКА  {b.name}")
            changed += 1
            continue
        a, bb = Image.open(b).convert("RGB"), Image.open(c).convert("RGB")
        if a.size != bb.size:
            print(f"ДРУГОЙ РАЗМЕР  {b.name}: {a.size} → {bb.size}")
            changed += 1
            continue
        d = ImageChops.difference(a, bb).convert("L").point(lambda v: 255 if v > 16 else 0)
        share = sum(d.histogram()[255:]) / (a.size[0] * a.size[1])
        if share > TOLERANCE:
            changed += 1
            red = Image.new("RGB", a.size, (255, 0, 0))
            Image.composite(red, bb, d).save(diff_dir / b.name)
            print(f"ИЗМЕНЕНО {share:6.2%}  {b.name}")
    print(f"\nИтого: изменилось {changed} из {len(list(base.glob('*.png')))} снимков."
          + (" Смотрите tests/screenshots/diff/." if changed else " Всё совпадает."))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "baseline":
        capture(SHOTS / "baseline")
        print(f"Эталонные снимки сохранены в {SHOTS / 'baseline'}")
    elif mode == "compare":
        compare()
    else:
        sys.exit(__doc__)
