#!/usr/bin/env python3
"""Генерация SEO-файлов сайта.

Что делает:
  0. Вставляет общие шапку и подвал (tools/partials/), заголовки вкладок и название сайта
     (site_name из tools/seo.config.json) во все страницы и в js/data.js.
  1. Вставляет мета-теги (description, Open Graph, canonical, favicon) в статические страницы.
  2. Создаёт отдельную страницу для каждой картины (painting/<id>.html) и художника (artist/<id>.html)
     с текстом, который видят поисковики, и разметкой schema.org.
  3. Создаёт украинские версии всех страниц в папке ua/ (ua/index.html, ua/catalog.html,
     ua/painting/<id>.html …): украинский текст записывается в страницу заранее, поэтому его видят
     поисковики и ИИ. Переводы берутся из js/data.js (I18N_COMMON) и из window.PAGE_I18N страниц.
     Страницы связаны пометками hreflang (en ↔ uk).
  4. Пишет sitemap.xml, robots.txt и llms.txt (справка о сайте для ИИ-поисковиков).

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from js_i18n import read_dict  # noqa: E402

START, END = "<!-- seo:start -->", "<!-- seo:end -->"
PLACEHOLDER = "https://YOUR-DOMAIN.example"
# Название сайта задаётся в tools/seo.config.json (site_name) и подставляется в main()
SITE_NAME = ""
# Почта для кнопки Enquire в версии страницы для поисковиков (та же, что GALLERY_EMAIL в js/main.js)
CONTACT_EMAIL = "nataliiavas.uk@gmail.com"
CSS_LINK = '<link rel="stylesheet" href="css/style.css">'
# Текст описания картины (description) не должен содержать цену: цена — только в поле price
PRICE_RX = re.compile(r"[$€₴£]|грн|\b(USD|EUR|UAH|GBP)\b|\bprice\b", re.I)
PRICE_CURRENCY = "USD"  # все цены в paintings.json (поле price) — в долларах США


def format_price(price, lang):
    """$6,000 (en) / 6 000 $ (ua) — тот же формат, что priceLabel() в js/main.js."""
    if lang == "ua":
        return f"{price:,}".replace(",", " ") + " $"
    return f"${price:,}"


STATIC_PAGES = {
    "index.html": ("", None),
    "catalog.html": ("catalog.html", "Browse {n} original paintings of the Odesa School, 1930s–1980s. Every work is documented, with provenance. Prices in US dollars."),
    "artists.html": ("artists.html", "{a} Odesa School painters, 1930s–1980s: biographies and their works in the collection."),
    "how-to-buy.html": ("how-to-buy.html", "How to buy a painting from {site}: six steps from enquiry to delivery, with payment and shipping options."),
    "about.html": ("about.html", "{site}: a privately held collection of Odesa painting from the 1930s–1980s, selected, researched and documented by its owner."),
    "contact.html": ("contact.html", "Contact {site}: email, phone and Instagram. We reply within 2 hours."),
}
INDEX_DESC = ("A small, privately held collection of original Odesa School paintings, 1930s–1980s: "
              "luminous color, free brushwork, the light and sea of Odesa.")
DEFAULT_IMAGE = "images/hero-odesa-opera.jpg"
# Украинские описания тех же страниц (для мета-тегов украинских версий в ua/)
STATIC_DESC_UA = {
    "index.html": "Невелика приватна колекція оригінальних картин одеської школи 1930–1980-х: світлоносний колір, "
                  "вільний мазок, світло й море Одеси.",
    "catalog.html": "{n} оригінальних картин одеської школи 1930–1980-х. Кожна робота задокументована, з провенансом. "
                    "Ціни в доларах США.",
    "artists.html": "{a} художників одеської школи 1930–1980-х: біографії та їхні роботи в колекції.",
    "how-to-buy.html": "Як купити картину в {site}: шість кроків від запиту до доставки, способи оплати й доставки.",
    "about.html": "{site} — приватна колекція одеського живопису 1930–1980-х: кожну роботу відібрано, досліджено "
                  "й задокументовано.",
    "contact.html": "Зв'яжіться з {site}: пошта, телефон та Instagram. Відповідаємо протягом 2 годин.",
}
# Тип страницы для разметки schema.org
STATIC_SCHEMA = {"index.html": "WebPage", "catalog.html": "CollectionPage", "artists.html": "CollectionPage",
                 "how-to-buy.html": "WebPage", "about.html": "AboutPage", "contact.html": "ContactPage"}
INSTAGRAM = "https://instagram.com/theodesaschool"

# Языки: en — в корне сайта, ua — в папке ua/. hreflang и og:locale — стандартные коды (украинский = uk)
LANGS = ("en", "ua")
HREFLANG = {"en": "en", "ua": "uk"}
OG_LOCALE = {"en": "en_US", "ua": "uk_UA"}
# Ключ перевода для названия раздела во вкладке браузера
SECTION_KEYS = {"catalog.html": "nav_catalog", "artists.html": "nav_artists", "how-to-buy.html": "nav_howtobuy",
                "about.html": "nav_about", "contact.html": "nav_contact"}
# Подписи в тексте для поисковиков (блок #seo-static)
LABELS = {
    "en": {"medium": "Medium", "size": "Size", "year": "Year", "signature": "Signature",
           "inscription": "Inscription", "condition": "Condition", "price": "Price", "price_val": "Price on request",
           "status": "Status", "provenance": "Provenance", "back": "← Back to Catalog", "enquire": "Enquire by email",
           "works": "Works in the Collection", "home": "Home", "by": "by",
           "desc": "{title}, {year}. {medium}, {size}, by {artist}. Original Odesa School painting{price}.",
           "desc_price": ", {price}", "desc_sold": ", sold",
           "artist_desc": "{name} ({years}), Odesa School painter. Works in the {site} collection."},
    "ua": {"medium": "Техніка", "size": "Розмір", "year": "Рік", "signature": "Підпис",
           "inscription": "Напис", "condition": "Стан", "price": "Ціна", "price_val": "за запитом",
           "status": "Статус", "provenance": "Провенанс", "back": "← До каталогу", "enquire": "Написати листом",
           "works": "Роботи в колекції", "home": "Головна", "by": "автор —",
           "desc": "{title}, {year}. {medium}, {size}. Автор — {artist}. Оригінальна картина одеської школи{price}.",
           "desc_price": ", ціна {price}", "desc_sold": ", продана",
           "artist_desc": "{name} ({years}), художник одеської школи. Роботи в колекції {site}."},
}
SEO_STATIC_START, SEO_STATIC_END = "<!-- seo-static:start -->", "<!-- seo-static:end -->"
# Прячет текст для поисковиков, когда работает JavaScript (посетитель видит обычную страницу)
HIDE_STATIC = ('<style>html.js #seo-static{display:none}</style>\n'
               '<script>document.documentElement.className+=" js"</script>')
PAGE_LINK_RX = re.compile(r'(<a\b[^>]*?\shref=")(?![a-z]+:|#|/|ua/)([\w\-/]+\.html)([?#][^"]*)?"', re.I)
I18N_RX = re.compile(r'<(\w+)(\s[^>]*?\bdata-i18n="([\w-]+)"[^>]*)>(.*?)</\1>', re.S)

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


def lang_path(path, lang):
    """Путь страницы на нужном языке: catalog.html -> ua/catalog.html, "" (главная) -> ua/"""
    return path if lang == "en" else "ua/" + path


def outside_scripts(text, fn):
    """Применяет fn только к HTML вне <script>…</script> (код страниц не трогаем)."""
    parts = re.split(r"(<script\b.*?</script>)", text, flags=re.S)
    return "".join(p if i % 2 else fn(p) for i, p in enumerate(parts))


def parse_size(size):
    """«50 × 80 cm (…)» -> (50, 80): высота × ширина, как принято для картин."""
    m = re.match(r"\s*([\d.,]+)\s*[×x]\s*([\d.,]+)\s*cm", size or "")
    return (float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))) if m else None


class Builder:
    def __init__(self, root, site_url, check_images):
        self.root = root
        self.site = site_url.rstrip("/")
        self.check_images = check_images
        self.warnings = []
        self.paintings = json.loads(read(os.path.join(root, "paintings.json")))
        self.artists = json.loads(read(os.path.join(root, "artists.json")))
        self.artist_by_id = {a["id"]: a for a in self.artists}
        self.common = read_dict(read(os.path.join(root, "js", "data.js")), "const I18N_COMMON",
                                {"SITE_NAME": SITE_NAME})
        assert self.common and set(self.common) >= set(LANGS), "js/data.js: не найден словарь I18N_COMMON"
        self.sitemap = []  # (path, [картинки]) — для sitemap.xml

    def t(self, lang, key, page_dict=None):
        return ((page_dict or {}).get(lang) or {}).get(key) or self.common[lang].get(key) or ""

    def page_dict(self, text):
        return read_dict(text, "window.PAGE_I18N", {"SITE_NAME": SITE_NAME}) or {}

    def localize(self, text, lang, page_dict):
        """Готовая английская страница -> та же страница на украинском (для папки ua/)."""
        if lang == "en":
            return text
        dict_ = dict(self.common[lang], **(page_dict.get(lang) or {}))
        text, c = re.subn(r'<html lang="[^"]*">', '<html lang="uk">', text, count=1)
        assert c == 1, "нет <html lang>"
        if "<base " not in text:
            text = text.replace('<meta charset="UTF-8">', '<meta charset="UTF-8">\n<base href="/">', 1)
        missing = set()

        def tr(m):
            key = m.group(3)
            if key not in dict_:
                missing.add(key)
                return m.group(0)
            return f"<{m.group(1)}{m.group(2)}>{dict_[key]}</{m.group(1)}>"

        def links(m):
            page = m.group(2)
            if page in ("painting.html", "artist.html", "404.html"):
                return m.group(0)
            new = "ua/" if page == "index.html" else "ua/" + page
            return f'{m.group(1)}{new}{m.group(3) or ""}"'

        text = outside_scripts(text, lambda s: PAGE_LINK_RX.sub(links, I18N_RX.sub(tr, s)))
        text = text.replace('<button id="btn-en" class="active">EN</button>', '<button id="btn-en">EN</button>', 1)
        text = text.replace('<button id="btn-ua">UA</button>', '<button id="btn-ua" class="active">UA</button>', 1)
        if missing:
            self.warn(f"нет украинского перевода для ключей: {', '.join(sorted(missing))}")
        return text

    def alternates(self, path):
        return [f'<link rel="alternate" hreflang="{HREFLANG[l]}" href="{esc(self.url(lang_path(path, l)))}">'
                for l in LANGS] + [f'<link rel="alternate" hreflang="x-default" href="{esc(self.url(path))}">']

    def url(self, path):
        path = path.lstrip("/")
        return self.site + "/" + quote(path) if path else self.site + "/"

    def warn(self, msg):
        self.warnings.append(msg)

    # ---------- head block ----------
    def head_block(self, title, desc, path, image=None, jsonld=None, noindex=False, lang="en"):
        """path — адрес английской версии; lang — для какой версии блок."""
        lines = [START]
        if noindex:
            lines.append('<meta name="robots" content="noindex">')
        else:
            own = lang_path(path, lang)
            other = "ua" if lang == "en" else "en"
            # Язык страницы задан адресом. Если посетитель раньше сам выбрал другой язык (кнопкой EN/UA),
            # сразу открываем ему версию на этом языке. У поисковиков выбора нет — они видят страницу как есть.
            target = "/" + lang_path(path, other)
            lines += [
                f'<meta name="description" content="{esc(desc)}">',
                f'<link rel="canonical" href="{esc(self.url(own))}">',
                *self.alternates(path),
                f'<meta property="og:site_name" content="{SITE_NAME}">',
                '<meta property="og:type" content="website">',
                f'<meta property="og:locale" content="{OG_LOCALE[lang]}">',
                f'<meta property="og:locale:alternate" content="{OG_LOCALE[other]}">',
                f'<meta property="og:title" content="{esc(title)}">',
                f'<meta property="og:description" content="{esc(desc)}">',
                f'<meta property="og:url" content="{esc(self.url(own))}">',
                f'<meta property="og:image" content="{esc(self.url(image or DEFAULT_IMAGE))}">',
                '<meta name="twitter:card" content="summary_large_image">',
                HIDE_STATIC,
                f'<script>window.PAGE_LANG="{lang}";try{{var l=localStorage.getItem("lang");'
                f'if(l&&l!=="{lang}")location.replace({json.dumps(target)}+location.hash)}}catch(e){{}}</script>',
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
            pdict = self.page_dict(text)
            for lang in LANGS:
                if lang == "en":
                    title = re.search(r"<title>(.*?)</title>", text, re.S).group(1)
                    d = INDEX_DESC if desc is None else desc.format(n=n, a=a, site=SITE_NAME)
                else:
                    key = SECTION_KEYS.get(fname)
                    title = f"{self.t(lang, key)} — {SITE_NAME}" if key else SITE_NAME
                    d = STATIC_DESC_UA[fname].format(n=n, a=a, site=SITE_NAME)
                jsonld = self.static_jsonld(fname, path, title, d, lang)
                block = self.head_block(html.unescape(title), d, path, jsonld=jsonld, lang=lang)
                page = self.put_static(self.inject(text, block), self.static_listing(fname, lang))
                if lang == "en":
                    write(fp, page)
                    text = page
                else:
                    page = re.sub(r"<title>.*?</title>", lambda m: f"<title>{esc(title)}</title>", page, count=1, flags=re.S)
                    write(os.path.join(self.root, "ua", fname), self.localize(page, lang, pdict))
            self.sitemap.append((path, []))
        # Шаблоны painting.html / artist.html и страницу 404 не индексируем (канонические — страницы в painting/ и artist/)
        for fname in ("painting.html", "artist.html", "404.html"):
            fp = os.path.join(self.root, fname)
            write(fp, self.inject(read(fp), self.head_block("", "", "", noindex=True)))

    @staticmethod
    def put_static(text, content):
        """Блок с текстом для поисковиков сразу после шапки (на каталоге и списке художников)."""
        text = re.sub(r"\n*" + re.escape(SEO_STATIC_START) + r".*?" + re.escape(SEO_STATIC_END), "", text, flags=re.S)
        if not content:
            return text
        assert text.count(HEADER_END) == 1, "нет метки конца шапки"
        return text.replace(HEADER_END, f"{HEADER_END}\n\n{SEO_STATIC_START}\n{content}\n{SEO_STATIC_END}", 1)

    def static_listing(self, fname, lang):
        L = LABELS[lang]
        if fname == "catalog.html":
            items = []
            for p in self.paintings:
                a = self.artist_by_id.get(p["artistId"])
                if not a:
                    continue
                status = self.t(lang, "status_" + p.get("status", "available"))
                items.append(f'    <li><a href="painting/{esc(p["id"])}.html">{esc(p["title"][lang])}, '
                             f'{esc(self.year_label(p, lang))}</a> — {esc(a["name"][lang])}. '
                             f'{esc(p["medium"][lang])}, {esc(p["size"])}. {esc(status)}.</li>')
            head = f'{self.t(lang, "nav_catalog")}: {len(items)}'
        elif fname == "artists.html":
            items = []
            for a in self.artists:
                bio = [b.get(lang) for b in (a.get("bio") or []) if b.get(lang)]
                first = trim(bio[0], 200) if bio else ""
                items.append(f'    <li><a href="artist/{esc(a["id"])}.html">{esc(a["name"][lang])}</a> '
                             f'({esc(a.get("years") or "")}). {esc(first)}</li>')
            head = self.t(lang, "nav_artists")
        else:
            return ""
        return (f'<main id="seo-static" class="bordered">\n  <h2>{esc(head)}</h2>\n  <ul>\n'
                + "\n".join(items) + f'\n  </ul>\n</main>')

    def website_ld(self):
        return {"@type": "WebSite", "@id": self.url("") + "#website", "name": SITE_NAME, "url": self.url(""),
                "inLanguage": [HREFLANG[l] for l in LANGS], "publisher": {"@id": self.url("") + "#org"}}

    def org_ld(self):
        return {"@type": "Organization", "@id": self.url("") + "#org", "name": SITE_NAME, "url": self.url(""),
                "email": CONTACT_EMAIL, "sameAs": [INSTAGRAM], "description": INDEX_DESC}

    def static_jsonld(self, fname, path, title, desc, lang):
        page = {"@type": STATIC_SCHEMA[fname], "name": html.unescape(title), "description": desc,
                "url": self.url(lang_path(path, lang)), "inLanguage": HREFLANG[lang],
                "isPartOf": {"@id": self.url("") + "#website"}}
        if fname == "catalog.html":
            page["mainEntity"] = {"@type": "ItemList", "numberOfItems": len(self.paintings), "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": p["title"][lang],
                 "url": self.url(lang_path(f"painting/{p['id']}.html", lang))}
                for i, p in enumerate(self.paintings)]}
        if fname == "artists.html":
            page["mainEntity"] = {"@type": "ItemList", "numberOfItems": len(self.artists), "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": a["name"][lang],
                 "url": self.url(lang_path(f"artist/{a['id']}.html", lang))}
                for i, a in enumerate(self.artists)]}
        graph = [page]
        if fname == "index.html":
            graph += [self.website_ld(), self.org_ld()]
        return {"@context": "https://schema.org", "@graph": graph}

    def breadcrumbs(self, lang, *crumbs):
        """crumbs: (название, путь английской версии)"""
        items = [(LABELS[lang]["home"], "")] + list(crumbs)
        return {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": self.url(lang_path(path, lang))}
            for i, (name, path) in enumerate(items)]}

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
            (CSS_LINK, CSS_LINK + "\n" + block),
            ('<script src="js/data.js"></script>',
             f'<script>window.{var}={json.dumps(value)};</script>\n<script src="js/data.js"></script>'),
            (HEADER_END + "\n", HEADER_END + "\n\n" + static_html + "\n"),
        ]
        for old, new in pairs:
            assert t.count(old) == 1, f"шаблон: не найден фрагмент {old!r}"
            t = t.replace(old, new, 1)
        return t

    def painting_desc(self, p, artist, lang="en"):
        desc = (p.get("description") or {}).get(lang, "")
        if desc and PRICE_RX.search(desc):
            self.warn(f"{p['id']}: в описании похоже на цену, использую шаблонное описание")
            desc = ""
        if desc:
            return trim(desc)
        L = LABELS[lang]
        if p.get("status") == "sold":
            price = L["desc_sold"]
        elif isinstance(p.get("price"), int):
            price = L["desc_price"].format(price=format_price(p["price"], lang))
        else:
            price = ""
        return trim(L["desc"].format(title=p["title"][lang], year=self.year_label(p, lang),
                                     medium=p["medium"][lang], size=p["size"],
                                     artist=artist["name"][lang], price=price), 200)

    @staticmethod
    def price_text(p, lang):
        """Цена для страницы: у проданной — ничего (статус «Продано» и так виден)."""
        if p.get("status") == "sold":
            return ""
        if isinstance(p.get("price"), int):
            return format_price(p["price"], lang)
        return LABELS[lang]["price_val"]

    @staticmethod
    def year_label(p, lang="en"):
        if p.get("yearNote"):
            return p["yearNote"][lang]
        return str(p["year"]) if p.get("year") is not None else ""

    def build_paintings(self):
        template = read(os.path.join(self.root, "painting.html"))
        pdict = self.page_dict(template)
        ids = set()
        for p in self.paintings:
            pid = p["id"]
            ids.add(pid)
            artist = self.artist_by_id.get(p["artistId"])
            if not artist:
                self.warn(f"{pid}: нет художника {p['artistId']}")
                continue
            photos = p.get("photos") or {}
            front = photos.get("front")
            if self.check_images:
                for k, v in photos.items():
                    if v and not os.path.exists(os.path.join(self.root, v)):
                        self.warn(f"{pid}: нет файла {v}")
            path = f"painting/{pid}.html"
            apath = f"artist/{artist['id']}.html"
            self.sitemap.append((path, [photos[k] for k in ("front", "framed") if photos.get(k)]))
            for lang in LANGS:
                L = LABELS[lang]
                title_txt = p["title"][lang]
                aname = artist["name"][lang]
                year = self.year_label(p, lang)
                page_title = f"{title_txt} — {aname} — {SITE_NAME}"
                desc = self.painting_desc(p, artist, lang)
                alt = ", ".join(x for x in (title_txt, aname, year, p["medium"][lang]) if x and x != "—")
                imgs = [self.url(photos[k]) for k in ("front", "framed") if photos.get(k)]
                art = {"@type": "VisualArtwork", "@id": self.url(lang_path(path, lang)) + "#artwork",
                       "name": title_txt, "artform": "Painting", "artMedium": p["medium"][lang],
                       "creator": {"@type": "Person", "name": aname, "url": self.url(lang_path(apath, lang))},
                       "description": desc, "url": self.url(lang_path(path, lang)), "inLanguage": HREFLANG[lang]}
                if p.get("year") is not None:
                    art["dateCreated"] = str(p["year"])
                hw = parse_size(p.get("size"))
                if hw:
                    art["height"] = {"@type": "QuantitativeValue", "value": hw[0], "unitCode": "CMT"}
                    art["width"] = {"@type": "QuantitativeValue", "value": hw[1], "unitCode": "CMT"}
                if imgs:
                    art["image"] = imgs
                # Предложение о продаже для Google: цена и наличие (у проданных — не указываем)
                if isinstance(p.get("price"), int) and p.get("status") != "sold":
                    art["offers"] = {"@type": "Offer", "price": p["price"], "priceCurrency": PRICE_CURRENCY,
                                     "availability": "https://schema.org/" +
                                     ("LimitedAvailability" if p.get("status") == "reserved" else "InStock"),
                                     "itemCondition": "https://schema.org/UsedCondition",
                                     "url": self.url(lang_path(path, lang))}
                crumbs = self.breadcrumbs(lang, (self.t(lang, "nav_catalog"), "catalog.html"),
                                          (aname, apath), (title_txt, path))
                ld = {"@context": "https://schema.org", "@graph": [art, crumbs]}
                block = self.head_block(page_title, desc, path, image=front, jsonld=ld, lang=lang)
                rows = [(L["medium"], p["medium"][lang]), (L["size"], p["size"]), (L["year"], year),
                        (L["signature"], (p.get("signature") or {}).get(lang)),
                        (L["inscription"], (p.get("inscription") or {}).get(lang)),
                        (L["condition"], (p.get("condition") or {}).get(lang)),
                        (L["status"], self.t(lang, "status_" + p.get("status", "available"))),
                        (L["price"], self.price_text(p, lang))]
                rows_html = "\n".join(f"    <li><b>{esc(k)}:</b> {esc(v)}</li>" for k, v in rows if v)
                full_desc = (p.get("description") or {}).get(lang) or ""
                prov = [x.get(lang) for x in (p.get("provenance") or []) if x.get(lang)]
                img_html = (f'\n  <img src="{esc(front)}" alt="{esc(alt)}" style="max-width:100%;height:auto;">'
                            if front else "")
                static_html = (
                    f'<main id="seo-static" class="bordered">\n'
                    f'  <h2>{esc(title_txt)}, {esc(year)}</h2>\n'
                    f'  <p><a href="{esc(apath)}">{esc(aname)}</a>'
                    f' {esc(artist.get("years") or "")}</p>{img_html}\n'
                    f'  <ul>\n{rows_html}\n  </ul>\n'
                    + (f'  <p>{html.escape(re.sub(r"<[^>]+>", "", full_desc))}</p>\n' if full_desc else "")
                    + (f"  <h3>{L['provenance']}</h3>\n  <ul>\n" +
                       "\n".join(f"    <li>{html.escape(re.sub(r'<[^>]+>', '', x))}</li>" for x in prov) +
                       "\n  </ul>\n" if prov else "")
                    + f'  <p><a href="catalog.html">{esc(L["back"])}</a> · '
                      f'<a href="mailto:{esc(CONTACT_EMAIL)}?subject={quote("Enquiry: " + p["title"]["en"])}">'
                      f'{esc(L["enquire"])}</a></p>\n'
                      '</main>'
                )
                page = self.make_page(template, page_title, block, "PAINTING_ID", pid, static_html)
                write(os.path.join(self.root, lang_path(path, lang)), self.localize(page, lang, pdict))
        for lang in LANGS:
            self.stale_warning(os.path.join(self.root, lang_path("painting", lang)), ids)

    def build_artists(self):
        template = read(os.path.join(self.root, "artist.html"))
        pdict = self.page_dict(template)
        ids = set()
        for a in self.artists:
            aid = a["id"]
            ids.add(aid)
            path = f"artist/{aid}.html"
            works = [p for p in self.paintings if p["artistId"] == aid]
            first_front = next(((p.get("photos") or {}).get("front") for p in works
                                if (p.get("photos") or {}).get("front")), None)
            self.sitemap.append((path, [a["photo"]] if a.get("photo") else []))
            for lang in LANGS:
                L = LABELS[lang]
                name = a["name"][lang]
                bio = [b.get(lang) for b in (a.get("bio") or []) if b.get(lang)]
                desc = trim(bio[0], 155) if bio else trim(
                    L["artist_desc"].format(name=name, years=a.get("years") or "", site=SITE_NAME), 200)
                page_title = f"{name} — {SITE_NAME}"
                person = {"@type": "Person", "@id": self.url(lang_path(path, lang)) + "#person", "name": name,
                          "jobTitle": "Painter" if lang == "en" else "Художник",
                          "description": desc, "url": self.url(lang_path(path, lang))}
                if a.get("name", {}).get("en") and lang != "en":
                    person["alternateName"] = a["name"]["en"]
                elif a.get("name", {}).get("ua") and lang == "en":
                    person["alternateName"] = a["name"]["ua"]
                m = re.match(r"\s*(\d{4})\s*\D+\s*(\d{4})\s*$", a.get("years") or "")
                if m:
                    person["birthDate"], person["deathDate"] = m.group(1), m.group(2)
                if a.get("photo"):
                    person["image"] = self.url(a["photo"])
                crumbs = self.breadcrumbs(lang, (self.t(lang, "nav_artists"), "artists.html"), (name, path))
                ld = {"@context": "https://schema.org", "@graph": [person, crumbs]}
                block = self.head_block(page_title, desc, path, image=a.get("photo") or first_front,
                                        jsonld=ld, lang=lang)
                bio_html = "\n".join(f"  <p>{esc(b)}</p>" for b in bio)
                works_html = "\n".join(
                    f'    <li><a href="painting/{esc(p["id"])}.html">{esc(p["title"][lang])}, '
                    f'{esc(self.year_label(p, lang))}</a></li>' for p in works)
                photo_html = (f'\n  <img src="{esc(a["photo"])}" alt="{esc(name)}, {esc(a.get("years") or "")}" '
                              f'style="max-width:240px;height:auto;">' if a.get("photo") else "")
                static_html = (
                    f'<main id="seo-static" class="bordered">\n'
                    f'  <h2>{esc(name)}</h2>{photo_html}\n'
                    f'  <p>{esc(a.get("years") or "")} {esc((a.get("title") or {}).get(lang) or "")}</p>\n'
                    f'{bio_html}\n  <h3>{esc(L["works"])}</h3>\n  <ul>\n{works_html}\n  </ul>\n'
                    f'  <p><a href="catalog.html">{esc(L["back"])}</a></p>\n</main>'
                )
                page = self.make_page(template, page_title, block, "ARTIST_ID", aid, static_html)
                write(os.path.join(self.root, lang_path(path, lang)), self.localize(page, lang, pdict))
        for lang in LANGS:
            self.stale_warning(os.path.join(self.root, lang_path("artist", lang)), ids)

    def stale_warning(self, out_dir, ids):
        if os.path.isdir(out_dir):
            for f in os.listdir(out_dir):
                if f.endswith(".html") and f[:-5] not in ids:
                    self.warn(f"лишний файл {os.path.basename(out_dir)}/{f}: такой записи больше нет в JSON, удалите вручную")

    # ---------- sitemap / robots / llms.txt ----------
    def build_sitemap(self):
        """Карта сайта: обе языковые версии каждой страницы, связи между ними и фото картин."""
        entries = []
        for path, images in self.sitemap:
            alts = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{HREFLANG[l]}" href="{esc(self.url(lang_path(path, l)))}"/>'
                           for l in LANGS)
            alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{esc(self.url(path))}"/>'
            imgs = "".join(f"\n    <image:image><image:loc>{esc(self.url(i))}</image:loc></image:image>" for i in images)
            for lang in LANGS:
                entries.append(f"  <url>\n    <loc>{esc(self.url(lang_path(path, lang)))}</loc>{alts}{imgs}\n  </url>")
        write(os.path.join(self.root, "sitemap.xml"),
              '<?xml version="1.0" encoding="UTF-8"?>\n'
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
              '        xmlns:xhtml="http://www.w3.org/1999/xhtml"\n'
              '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
              + "\n".join(entries) + "\n</urlset>\n")
        write(os.path.join(self.root, "robots.txt"),
              f"User-agent: *\nAllow: /\n\nSitemap: {self.site}/sitemap.xml\n")
        return len(entries)

    def build_llms(self):
        """llms.txt — краткая справка о сайте для ИИ-ассистентов (формат llmstxt.org), с ценами в USD."""
        index_dict = self.page_dict(read(os.path.join(self.root, "index.html")))
        about = re.sub(r"\s+", " ", self.t("en", "about_text", index_dict)).strip()
        lines = [f"# {SITE_NAME}", "", f"> {INDEX_DESC} Prices are listed in US dollars on each painting page.", "",
                 about, "",
                 f"All pages exist in English ({self.url('')}) and Ukrainian ({self.url('ua/')}): "
                 "the Ukrainian version of any page is the same address with /ua/ after the domain.", "",
                 "## Main pages", ""]
        n, a = len(self.paintings), len(self.artists)
        names = {"catalog.html": "Catalog", "artists.html": "Artists", "how-to-buy.html": "How to Buy",
                 "about.html": "About the Collection", "contact.html": "Contact"}
        for fname, (path, desc) in STATIC_PAGES.items():
            if fname in names:
                lines.append(f"- [{names[fname]}]({self.url(path)}): {desc.format(n=n, a=a, site=SITE_NAME)}")
        lines += ["", "## Artists", ""]
        for ar in self.artists:
            bio = [b.get("en") for b in (ar.get("bio") or []) if b.get("en")]
            count = sum(1 for p in self.paintings if p["artistId"] == ar["id"])
            lines.append(f"- [{ar['name']['en']}]({self.url('artist/' + ar['id'] + '.html')}) "
                         f"({ar.get('years') or ''}), {count} {'work' if count == 1 else 'works'} in the collection: {trim(bio[0], 220) if bio else ''}")
        lines += ["", "## Paintings", ""]
        for p in self.paintings:
            ar = self.artist_by_id.get(p["artistId"])
            if not ar:
                continue
            status = self.t("en", "status_" + p.get("status", "available"))
            price = self.price_text(p, "en")
            lines.append(f"- [{p['title']['en']}]({self.url('painting/' + p['id'] + '.html')}): "
                         f"{ar['name']['en']}, {self.year_label(p)}. {p['medium']['en']}, {p['size']}. {status}"
                         + (f", {price}." if price else "."))
        lines += ["", "## Contact", "",
                  f"- Email: {CONTACT_EMAIL} (enquiries about any painting)",
                  f"- Instagram: {INSTAGRAM}", ""]
        write(os.path.join(self.root, "llms.txt"), "\n".join(lines))


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
    b.build_llms()
    print(f"Готово: {len(b.paintings)} страниц картин, {len(b.artists)} страниц художников (каждая на 2 языках), "
          f"{n} адресов в sitemap.xml, llms.txt. Адрес сайта: {site}, название: {SITE_NAME}")
    if site.rstrip("/") == PLACEHOLDER:
        print("ВНИМАНИЕ: в tools/seo.config.json указан адрес-заглушка. Впишите реальный домен и запустите скрипт снова.")
    for w in b.warnings:
        print("ПРЕДУПРЕЖДЕНИЕ:", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
