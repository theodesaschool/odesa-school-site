#!/usr/bin/env python3
"""Генерация SEO-файлов сайта.

Что делает:
  0. Вставляет общие шапку и подвал (tools/partials/), заголовки вкладок и название сайта
     (site_name из tools/seo.config.json) во все страницы и в js/data.js.
  1. Вставляет мета-теги (description, Open Graph, canonical, favicon) в статические страницы.
  2. Создаёт отдельную страницу для каждой картины (painting/<id>.html) и художника (artist/<id>.html)
     с текстом, который видят поисковики, и разметкой schema.org.
  3. Пишет sitemap.xml и robots.txt.

Запуск из корня сайта:  python3 tools/build_seo.py
Адрес сайта берётся из tools/seo.config.json (поле site_url).
ВАЖНО: после любой правки paintings.json / artists.json запускайте скрипт заново.
Скрипт можно запускать повторно: результат тот же.
"""
import argparse
import html
import json
import os
import re
import sys
from urllib.parse import quote

START, END = "<!-- seo:start -->", "<!-- seo:end -->"
PLACEHOLDER = "https://YOUR-DOMAIN.example"
# Название сайта задаётся в tools/seo.config.json (site_name) и подставляется в main()
SITE_NAME = ""
# Почта для кнопки Enquire в версии страницы для поисковиков (та же, что GALLERY_EMAIL в js/main.js)
CONTACT_EMAIL = "nataliiavas.uk@gmail.com"
CSS_LINK = '<link rel="stylesheet" href="css/style.css">'
PRICE_RX = re.compile(r"[$€₴£]|грн|\b(USD|EUR|UAH|GBP)\b|\bprice\b", re.I)

STATIC_PAGES = {
    "index.html": ("/", None),
    "catalog.html": ("catalog.html", "Browse {n} original paintings of the Odesa School, 1930s–1980s. Every work is documented, with provenance. Price on request."),
    "artists.html": ("artists.html", "{a} Odesa School painters, 1930s–1980s: biographies and their works in the collection."),
    "how-to-buy.html": ("how-to-buy.html", "How to buy a painting from {site}: six steps from enquiry to delivery, with payment and shipping options."),
    "about.html": ("about.html", "{site}: a privately held collection of Odesa painting from the 1930s–1980s, selected, researched and documented by its owner."),
    "contact.html": ("contact.html", "Contact {site}: email, phone and Instagram. We reply within 2 hours."),
}
INDEX_DESC = ("A small, privately held collection of original Odesa School paintings, 1930s–1980s: "
              "luminous color, free brushwork, the light and sea of Odesa.")
DEFAULT_IMAGE = "images/hero-odesa-opera.jpg"

# Общие шапка и подвал: образцы лежат в tools/partials/, скрипт вставляет их во все страницы
# между метками <!-- header:start --> … <!-- header:end --> (и так же для footer).
HEADER_START, HEADER_END = "<!-- header:start -->", "<!-- header:end -->"
FOOTER_START, FOOTER_END = "<!-- footer:start -->", "<!-- footer:end -->"
# Заголовок вкладки браузера: «<раздел> — <название сайта>»; None — только название сайта
PAGE_TITLES = {
    "index.html": None,
    "catalog.html": "Catalog",
    "artists.html": "Artists",
    "how-to-buy.html": "How to Buy",
    "about.html": "About",
    "contact.html": "Contact",
    "painting.html": "Painting",
    "artist.html": "Artist",
    "404.html": "Page not found",
}
# Название сайта для кода страниц (js/data.js), между метками
SITE_JS_START = "/* site:start — создаётся tools/build_seo.py из tools/seo.config.json, не править вручную */"
SITE_JS_END = "/* site:end */"


def esc(s):
    return html.escape(str(s), quote=True)


def trim(text, n=155):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(",;:—- ") + "…"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class Builder:
    def __init__(self, root, site_url, check_images):
        self.root = root
        self.site = site_url.rstrip("/")
        self.check_images = check_images
        self.warnings = []
        self.paintings = json.loads(read(os.path.join(root, "paintings.json")))
        self.artists = json.loads(read(os.path.join(root, "artists.json")))
        self.artist_by_id = {a["id"]: a for a in self.artists}

    def url(self, path):
        path = path.lstrip("/")
        return self.site + "/" + quote(path) if path else self.site + "/"

    def warn(self, msg):
        self.warnings.append(msg)

    # ---------- head block ----------
    def head_block(self, title, desc, path, image=None, jsonld=None, noindex=False):
        lines = [START]
        if noindex:
            lines.append('<meta name="robots" content="noindex">')
        else:
            lines += [
                f'<meta name="description" content="{esc(desc)}">',
                f'<link rel="canonical" href="{esc(self.url(path))}">',
                f'<meta property="og:site_name" content="{SITE_NAME}">',
                '<meta property="og:type" content="website">',
                '<meta property="og:locale" content="en_US">',
                '<meta property="og:locale:alternate" content="uk_UA">',
                f'<meta property="og:title" content="{esc(title)}">',
                f'<meta property="og:description" content="{esc(desc)}">',
                f'<meta property="og:url" content="{esc(self.url(path))}">',
                f'<meta property="og:image" content="{esc(self.url(image or DEFAULT_IMAGE))}">',
                '<meta name="twitter:card" content="summary_large_image">',
            ]
        lines.append('<link rel="icon" href="/favicon.svg" type="image/svg+xml">')
        if jsonld:
            data = json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")
            lines.append(f'<script type="application/ld+json">{data}</script>')
        lines.append(END)
        return "\n".join(lines)

    @staticmethod
    def strip_block(text):
        return re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", "", text, flags=re.S)

    def inject(self, text, block):
        if START in text:
            return re.sub(re.escape(START) + r".*?" + re.escape(END),
                          lambda m: block, text, count=1, flags=re.S)
        assert CSS_LINK in text, "не найден <link> на css/style.css"
        return text.replace(CSS_LINK, CSS_LINK + "\n" + block, 1)

    # ---------- общая разметка: шапка, подвал, заголовки, название в JS ----------
    @staticmethod
    def put_region(text, start, end, tag, content):
        block = f"{start}\n{content.rstrip()}\n{end}"
        if start in text:
            return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda m: block, text, count=1, flags=re.S)
        found = re.findall(rf"<{tag}\b[^>]*>.*?</{tag}>", text, re.S)
        assert len(found) == 1, f"ожидался ровно один <{tag}>, найдено {len(found)}"
        return text.replace(found[0], block, 1)

    def build_layout(self):
        fill = lambda name: read(os.path.join(self.root, "tools", "partials", name)).replace("{site_name}", esc(SITE_NAME))
        header, footer = fill("header.html"), fill("footer.html")
        for fname, section in PAGE_TITLES.items():
            fp = os.path.join(self.root, fname)
            text = read(fp)
            text = self.put_region(text, HEADER_START, HEADER_END, "header", header)
            text = self.put_region(text, FOOTER_START, FOOTER_END, "footer", footer)
            title = f"{section} — {SITE_NAME}" if section else SITE_NAME
            text, c = re.subn(r"<title>.*?</title>", lambda m: f"<title>{esc(title)}</title>", text, count=1, flags=re.S)
            assert c == 1, f"{fname}: нет <title>"
            write(fp, text)
        fp = os.path.join(self.root, "js", "data.js")
        text = read(fp)
        block = f"{SITE_JS_START}\nconst SITE_NAME = {json.dumps(SITE_NAME, ensure_ascii=False)};\n{SITE_JS_END}"
        assert SITE_JS_START in text, "js/data.js: нет метки site:start"
        text = re.sub(re.escape(SITE_JS_START) + r".*?" + re.escape(SITE_JS_END), lambda m: block, text, count=1, flags=re.S)
        write(fp, text)

    # ---------- static pages & app shells ----------
    def build_static(self):
        n, a = len(self.paintings), len(self.artists)
        for fname, (path, desc) in STATIC_PAGES.items():
            fp = os.path.join(self.root, fname)
            text = read(fp)
            title = re.search(r"<title>(.*?)</title>", text, re.S).group(1)
            d = INDEX_DESC if desc is None else desc.format(n=n, a=a, site=SITE_NAME)
            write(fp, self.inject(text, self.head_block(title, d, path)))
        # Шаблоны painting.html / artist.html и страницу 404 не индексируем (канонические — страницы в painting/ и artist/)
        for fname in ("painting.html", "artist.html", "404.html"):
            fp = os.path.join(self.root, fname)
            write(fp, self.inject(read(fp), self.head_block("", "", "", noindex=True)))

    # ---------- generated pages ----------
    def make_page(self, template, title, block, var, value, static_html):
        t = self.strip_block(template)
        steps = [
            (r"<title>.*?</title>", f"<title>{esc(title)}</title>", True),
        ]
        t, c = re.subn(steps[0][0], lambda m: steps[0][1], t, count=1, flags=re.S)
        assert c == 1, "title"
        pairs = [
            ('<meta charset="UTF-8">', '<meta charset="UTF-8">\n<base href="/">'),
            (CSS_LINK, CSS_LINK + "\n" + block +
             '\n<style>html.js #seo-static{display:none}</style>'
             '\n<script>document.documentElement.className+=" js"</script>'),
            ('<script src="js/data.js"></script>',
             f'<script>window.{var}={json.dumps(value)};</script>\n<script src="js/data.js"></script>'),
            (HEADER_END + "\n", HEADER_END + "\n\n" + static_html + "\n"),
        ]
        for old, new in pairs:
            assert t.count(old) == 1, f"шаблон: не найден фрагмент {old!r}"
            t = t.replace(old, new, 1)
        return t

    def painting_desc(self, p, artist):
        desc = (p.get("description") or {}).get("en", "")
        if desc and PRICE_RX.search(desc):
            self.warn(f"{p['id']}: в описании похоже на цену, использую шаблонное описание")
            desc = ""
        if desc:
            return trim(desc)
        year = self.year_label(p)
        return trim(f"{p['title']['en']}, {year}. {p['medium']['en']}, {p['size']}, by {artist['name']['en']}. "
                    f"Original Odesa School painting, price on request.", 200)

    @staticmethod
    def year_label(p):
        if p.get("yearNote"):
            return p["yearNote"]["en"]
        return str(p["year"]) if p.get("year") is not None else ""

    def build_paintings(self):
        template = read(os.path.join(self.root, "painting.html"))
        out_dir = os.path.join(self.root, "painting")
        ids = set()
        for p in self.paintings:
            pid = p["id"]
            ids.add(pid)
            artist = self.artist_by_id.get(p["artistId"])
            if not artist:
                self.warn(f"{pid}: нет художника {p['artistId']}")
                continue
            title_txt = p["title"]["en"]
            year = self.year_label(p)
            page_title = f"{title_txt} — {artist['name']['en']} — {SITE_NAME}"
            desc = self.painting_desc(p, artist)
            photos = p.get("photos") or {}
            front = photos.get("front")
            if self.check_images:
                for k, v in photos.items():
                    if v and not os.path.exists(os.path.join(self.root, v)):
                        self.warn(f"{pid}: нет файла {v}")
            path = f"painting/{pid}.html"
            imgs = [self.url(photos[k]) for k in ("front", "framed") if photos.get(k)]
            ld = {"@context": "https://schema.org", "@type": "VisualArtwork", "name": title_txt,
                  "artform": "Painting", "artMedium": p["medium"]["en"],
                  "creator": {"@type": "Person", "name": artist["name"]["en"]},
                  "description": desc, "url": self.url(path)}
            if p.get("year") is not None:
                ld["dateCreated"] = str(p["year"])
            if imgs:
                ld["image"] = imgs
            block = self.head_block(page_title, desc, path, image=front, jsonld=ld)
            rows = [("Medium", p["medium"]["en"]), ("Size", p["size"]), ("Year", year),
                    ("Signature", (p.get("signature") or {}).get("en")),
                    ("Inscription", (p.get("inscription") or {}).get("en")),
                    ("Condition", (p.get("condition") or {}).get("en")),
                    ("Price", "Price on request")]
            rows_html = "\n".join(f"    <li><b>{esc(k)}:</b> {esc(v)}</li>" for k, v in rows if v)
            full_desc = (p.get("description") or {}).get("en") or ""
            prov = [x.get("en") for x in (p.get("provenance") or []) if x.get("en")]
            img_html = (f'\n  <img src="{esc(front)}" alt="{esc(title_txt)}" style="max-width:100%;height:auto;">'
                        if front else "")
            static_html = (
                f'<main id="seo-static" class="bordered">\n'
                f'  <h2>{esc(title_txt)}, {esc(year)}</h2>\n'
                f'  <p><a href="artist/{esc(artist["id"])}.html">{esc(artist["name"]["en"])}</a>'
                f' {esc(artist.get("years") or "")}</p>{img_html}\n'
                f'  <ul>\n{rows_html}\n  </ul>\n'
                + (f'  <p>{html.escape(re.sub(r"<[^>]+>", "", full_desc))}</p>\n' if full_desc else "")
                + ("  <h3>Provenance</h3>\n  <ul>\n" +
                   "\n".join(f"    <li>{html.escape(re.sub(r'<[^>]+>', '', x))}</li>" for x in prov) +
                   "\n  </ul>\n" if prov else "")
                + '  <p><a href="catalog.html">← Back to Catalog</a> · '
                  f'<a href="mailto:{esc(CONTACT_EMAIL)}?subject={quote("Enquiry: " + title_txt)}">Enquire by email</a></p>\n'
                  '</main>'
            )
            page = self.make_page(template, page_title, block, "PAINTING_ID", pid, static_html)
            write(os.path.join(out_dir, f"{pid}.html"), page)
        self.stale_warning(out_dir, ids)

    def build_artists(self):
        template = read(os.path.join(self.root, "artist.html"))
        out_dir = os.path.join(self.root, "artist")
        ids = set()
        for a in self.artists:
            aid = a["id"]
            ids.add(aid)
            name = a["name"]["en"]
            bio = [b.get("en") for b in (a.get("bio") or []) if b.get("en")]
            desc = trim(bio[0], 155) if bio else trim(
                f"{name} ({a.get('years') or ''}), Odesa School painter. Works in The Odesa School collection.", 200)
            path = f"artist/{aid}.html"
            page_title = f"{name} — {SITE_NAME}"
            works = [p for p in self.paintings if p["artistId"] == aid]
            first_front = next(((p.get("photos") or {}).get("front") for p in works
                                if (p.get("photos") or {}).get("front")), None)
            ld = {"@context": "https://schema.org", "@type": "Person", "name": name,
                  "description": desc, "url": self.url(path)}
            m = re.match(r"\s*(\d{4})\s*\D+\s*(\d{4})\s*$", a.get("years") or "")
            if m:
                ld["birthDate"], ld["deathDate"] = m.group(1), m.group(2)
            if a.get("photo"):
                ld["image"] = self.url(a["photo"])
            block = self.head_block(page_title, desc, path, image=a.get("photo") or first_front, jsonld=ld)
            bio_html = "\n".join(f"  <p>{esc(b)}</p>" for b in bio)
            works_html = "\n".join(
                f'    <li><a href="painting/{esc(p["id"])}.html">{esc(p["title"]["en"])}, {esc(self.year_label(p))}</a></li>'
                for p in works)
            static_html = (
                f'<main id="seo-static" class="bordered">\n'
                f'  <h2>{esc(name)}</h2>\n'
                f'  <p>{esc(a.get("years") or "")} {esc((a.get("title") or {}).get("en") or "")}</p>\n'
                f'{bio_html}\n  <h3>Works in the Collection</h3>\n  <ul>\n{works_html}\n  </ul>\n'
                f'  <p><a href="catalog.html">← Back to Catalog</a></p>\n</main>'
            )
            page = self.make_page(template, page_title, block, "ARTIST_ID", aid, static_html)
            write(os.path.join(out_dir, f"{aid}.html"), page)
        self.stale_warning(out_dir, ids)

    def stale_warning(self, out_dir, ids):
        if os.path.isdir(out_dir):
            for f in os.listdir(out_dir):
                if f.endswith(".html") and f[:-5] not in ids:
                    self.warn(f"лишний файл {os.path.basename(out_dir)}/{f}: такой записи больше нет в JSON, удалите вручную")

    # ---------- sitemap / robots ----------
    def build_sitemap(self):
        paths = [v[0] for v in STATIC_PAGES.values()]
        paths += [f"artist/{a['id']}.html" for a in self.artists]
        paths += [f"painting/{p['id']}.html" for p in self.paintings]
        body = "\n".join(f"  <url><loc>{esc(self.url(p))}</loc></url>" for p in paths)
        write(os.path.join(self.root, "sitemap.xml"),
              '<?xml version="1.0" encoding="UTF-8"?>\n'
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "\n</urlset>\n")
        write(os.path.join(self.root, "robots.txt"),
              f"User-agent: *\nAllow: /\n\nSitemap: {self.site}/sitemap.xml\n")
        return len(paths)


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--root", default=os.path.dirname(here))
    ap.add_argument("--skip-image-check", action="store_true")
    args = ap.parse_args()
    cfg = json.loads(read(os.path.join(args.root, "tools", "seo.config.json")))
    site = cfg.get("site_url", PLACEHOLDER)
    global SITE_NAME
    SITE_NAME = (cfg.get("site_name") or "").strip()
    if not SITE_NAME:
        print("ОСТАНОВЛЕНО: в tools/seo.config.json не задано название сайта (site_name).")
        return 1
    b = Builder(args.root, site, not args.skip_image_check)
    b.build_layout()
    b.build_static()
    b.build_paintings()
    b.build_artists()
    n = b.build_sitemap()
    print(f"Готово: {len(b.paintings)} страниц картин, {len(b.artists)} страниц художников, "
          f"{n} адресов в sitemap.xml. Адрес сайта: {site}, название: {SITE_NAME}")
    if site.rstrip("/") == PLACEHOLDER:
        print("ВНИМАНИЕ: в tools/seo.config.json указан адрес-заглушка. Впишите реальный домен и запустите скрипт снова.")
    for w in b.warnings:
        print("ПРЕДУПРЕЖДЕНИЕ:", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
