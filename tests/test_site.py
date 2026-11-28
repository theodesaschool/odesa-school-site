"""Проверки сайта глазами посетителя (Playwright открывает настоящий браузер Chromium).

Запуск:  .venv/bin/pytest tests
"""
import re
import sys
from pathlib import Path

import pytest

STATIC_PAGES = {
    # файл: значение data-nav, которое должно подсвечиваться в меню
    "index.html": "home",
    "catalog.html": "catalog",
    "artists.html": "artists",
    "how-to-buy.html": "howtobuy",
    "about.html": "about",
    "contact.html": "contact",
}
NAV_ITEMS = ["home", "catalog", "artists", "howtobuy", "about", "contact"]
OLD_NAMES = ["Odesa Art Gallery", "Odesa Art School"]
# формат цены общий для всего проекта и хранится в tools/build_seo.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from build_seo import format_price  # noqa: E402
EMAIL = "nataliiavas.uk@gmail.com"
HTML_LANG = {"en": "en", "ua": "uk"}  # код украинского языка в HTML — uk


class Watcher:
    """Собирает ошибки страницы: ошибки JS, ошибки консоли и файлы, которые не загрузились."""

    def __init__(self, page):
        self.problems = []
        page.on("pageerror", lambda e: self.problems.append(f"JS error: {e}"))
        page.on("console", lambda m: m.type == "error" and self.problems.append(f"console: {m.text}"))
        page.on("response", lambda r: r.status >= 400 and self.problems.append(f"{r.status} {r.url}"))
        page.on("requestfailed", lambda r: self.problems.append(f"failed {r.url}"))

    def take(self):
        out, self.problems = self.problems, []
        return out


def open_page(page, path, lang="en"):
    # язык хранится в localStorage; ставим его один раз до первой загрузки,
    # дальше сайт сам помнит выбор (как у настоящего посетителя)
    page.add_init_script(
        f"if (!sessionStorage.getItem('__test_lang')) {{"
        f" localStorage.setItem('lang', '{lang}'); sessionStorage.setItem('__test_lang', '1'); }}"
    )
    page.goto(path, wait_until="networkidle")


def visible_text(page):
    return page.evaluate(
        "() => [...document.querySelectorAll('body *')]"
        ".filter(e => e.offsetParent !== null && e.children.length === 0)"
        ".map(e => e.textContent).join('\\n')"
    )


def broken_images(page):
    return page.evaluate(
        "() => [...document.images].filter(i => i.offsetParent !== null && i.complete && i.naturalWidth === 0)"
        ".map(i => i.getAttribute('src'))"
    )


# ---------- Обычные страницы ----------

@pytest.mark.parametrize("lang", ["en", "ua"])
@pytest.mark.parametrize("path", list(STATIC_PAGES))
def test_static_page_loads_cleanly(page, path, lang):
    w = Watcher(page)
    open_page(page, "/" + path, lang)
    assert w.take() == [], "ошибки на странице"
    assert broken_images(page) == []
    # язык выбран раньше кнопкой -> сайт сам открывает версию на этом языке (украинские — в папке ua/)
    assert page.evaluate("document.documentElement.lang") == HTML_LANG[lang]
    assert ("/ua/" in page.url) == (lang == "ua")


@pytest.mark.parametrize("path,active", list(STATIC_PAGES.items()))
def test_menu_and_active_item(page, path, active):
    open_page(page, "/" + path)
    nav = [a.get_attribute("data-nav") for a in page.locator("nav.main-nav a").all()]
    assert nav == NAV_ITEMS
    assert page.locator("nav.main-nav a.active").get_attribute("data-nav") == active
    for a in page.locator("nav.main-nav a").all():
        href = a.get_attribute("href")
        assert page.request.get(href).ok, f"ссылка меню не открывается: {href}"


def test_language_switch_is_remembered(page):
    open_page(page, "/catalog.html", "en")
    assert page.locator("nav.main-nav a[data-nav=catalog]").inner_text().strip().lower() == "catalog"
    page.click("#btn-ua")
    page.wait_for_url("**/ua/catalog.html")
    page.wait_for_load_state("networkidle")
    assert page.evaluate("document.documentElement.lang") == "uk"
    ua_text = page.locator("nav.main-nav a[data-nav=catalog]").inner_text().strip()
    assert ua_text.lower() != "catalog"
    page.click("nav.main-nav a[data-nav=home]")
    page.wait_for_url("**/ua/")
    page.wait_for_load_state("networkidle")
    assert page.evaluate("document.documentElement.lang") == "uk"
    assert page.locator("#btn-ua").get_attribute("class") == "active"
    # назад на английский — та же страница без /ua/
    page.click("#btn-en")
    page.wait_for_url(lambda u: "/ua/" not in u)
    page.wait_for_load_state("networkidle")
    assert page.evaluate("document.documentElement.lang") == "en"


# ---------- Украинская версия (папка ua/) ----------

UA_STATIC = [p for p in STATIC_PAGES]


def ua_path(path):
    return "/ua/" if path == "index.html" else "/ua/" + path


@pytest.mark.parametrize("path", UA_STATIC)
def test_ua_html_has_ukrainian_without_js(page, path):
    """Поисковики и ИИ часто не запускают JavaScript: украинский текст должен быть в самом файле."""
    raw = page.request.get(ua_path(path)).text()
    assert '<html lang="uk">' in raw
    assert ">Каталог</a>" in raw, "меню не переведено заранее"
    assert 'hreflang="uk"' in raw and 'hreflang="en"' in raw and 'hreflang="x-default"' in raw
    canonical = re.search(r'<link rel="canonical" href="([^"]+)"', raw).group(1)
    assert "/ua/" in canonical
    assert not re.search(r'<a [^>]*href="(?!ua/|https?:|mailto:|#)[\w\-/]+\.html"', raw), \
        "ссылка с украинской страницы ведёт на английскую"


def test_en_html_points_to_ua_version(page):
    raw = page.request.get("/painting/lomykin-winter-morning.html").text()
    assert 'hreflang="uk" href="https://theodesaschool.com/ua/painting/lomykin-winter-morning.html"' in raw


def test_every_ua_painting_and_artist_page(page, paintings, artists):
    w = Watcher(page)
    page.add_init_script("localStorage.removeItem('lang')")
    failures = []
    for p in paintings:
        page.goto(f"/ua/painting/{p['id']}.html", wait_until="networkidle")
        errs = w.take()
        title = page.locator("#pg-title").inner_text().strip()
        if errs:
            failures.append(f"ua {p['id']}: {errs}")
        if p["title"]["ua"] not in title:
            failures.append(f"ua {p['id']}: нет украинского названия (видно {title!r})")
        bad = page.evaluate("() => [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))"
                            ".filter(h => /^(painting|artist|catalog|how-to-buy)[\\w\\-\\/]*\\.html/.test(h))")
        if bad:
            failures.append(f"ua {p['id']}: ссылки на английские страницы {bad[:3]}")
    for a in artists:
        page.goto(f"/ua/artist/{a['id']}.html", wait_until="networkidle")
        errs = w.take()
        if errs:
            failures.append(f"ua {a['id']}: {errs}")
        if a["name"]["ua"] not in page.locator("#artist-hero").inner_text():
            failures.append(f"ua {a['id']}: нет украинского имени")
        hrefs = page.evaluate("() => [...document.querySelectorAll('#thumb-grid a')].map(a => a.getAttribute('href'))")
        if any(not h.startswith("ua/painting/") for h in hrefs):
            failures.append(f"ua {a['id']}: ссылки на работы не ведут в ua/: {hrefs[:2]}")
    assert failures == []


def test_ua_catalog_renders(page, paintings):
    page.add_init_script("localStorage.removeItem('lang')")
    page.goto("/ua/catalog.html", wait_until="networkidle")
    assert page.locator("#catalog-grid .painting-card").count() == len(paintings)
    assert not page.locator("#seo-static").is_visible()
    href = page.locator("#catalog-grid .painting-card a.canvas").first.get_attribute("href")
    assert href.startswith("ua/painting/")


def test_llms_txt(page, paintings):
    r = page.request.get("/llms.txt")
    assert r.ok
    text = r.text()
    assert text.startswith("# ") and "/painting/" in text and "/artist/" in text
    for p in paintings:
        if p["status"] != "sold":
            assert format_price(p["price"], "en") in text, p["id"]


# ---------- Каталог ----------

def test_catalog_shows_all_paintings(page, paintings):
    open_page(page, "/catalog.html")
    assert page.locator("#catalog-grid .painting-card").count() == len(paintings)


def test_catalog_filter_by_artist(page, paintings):
    open_page(page, "/catalog.html")
    page.select_option("#filter-artist", "lomykin")
    expected = sum(1 for p in paintings if p["artistId"] == "lomykin")
    assert page.locator("#catalog-grid .painting-card").count() == expected
    page.click("#filter-reset")
    assert page.locator("#catalog-grid .painting-card").count() == len(paintings)


# ---------- Каждая картина и каждый художник ----------

def test_every_painting_page(page, paintings):
    w = Watcher(page)
    page.add_init_script("localStorage.setItem('lang', 'en')")
    failures = []
    for p in paintings:
        page.goto(f"/painting/{p['id']}.html", wait_until="networkidle")
        errs = w.take()
        title = page.locator("#pg-title").inner_text().strip()
        main_ok = page.evaluate("() => { const i = document.getElementById('pg-main-img'); return !!i && i.naturalWidth > 0; }")
        inquire = page.locator("#pg-inquire").get_attribute("href") or ""
        if errs:
            failures.append(f"{p['id']}: {errs}")
        if p["title"]["en"] not in title:
            failures.append(f"{p['id']}: нет названия (видно {title!r})")
        if not main_ok:
            failures.append(f"{p['id']}: главное фото не показалось")
        if not inquire.startswith(f"mailto:{EMAIL}"):
            failures.append(f"{p['id']}: кнопка Enquire ведёт на {inquire!r}")
    assert failures == []


def test_every_artist_page(page, artists, paintings):
    w = Watcher(page)
    page.add_init_script("localStorage.setItem('lang', 'en')")
    failures = []
    for a in artists:
        page.goto(f"/artist/{a['id']}.html", wait_until="networkidle")
        errs = w.take()
        if errs:
            failures.append(f"{a['id']}: {errs}")
        if a["name"]["en"] not in page.locator("#artist-hero").inner_text():
            failures.append(f"{a['id']}: нет имени художника")
        works = sum(1 for p in paintings if p["artistId"] == a["id"])
        shown = page.locator("#thumb-grid a").count()
        if shown != works:
            failures.append(f"{a['id']}: показано {shown} работ из {works}")
    assert failures == []


def test_enquire_button_in_catalog(page):
    open_page(page, "/catalog.html")
    href = page.locator("#catalog-grid .inquire-btn").first.get_attribute("href")
    assert href.startswith(f"mailto:{EMAIL}")


# ---------- Телефон ----------

MOBILE_PAGES = list(STATIC_PAGES) + ["painting/lomykin-winter-morning.html", "artist/shelyuto.html"]


@pytest.mark.parametrize("path", MOBILE_PAGES)
def test_mobile_no_horizontal_scroll(browser, base_url, path):
    ctx = browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True, base_url=base_url)
    page = ctx.new_page()
    open_page(page, "/" + path)
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    ctx.close()
    assert overflow <= 1, f"страница шире экрана телефона на {overflow}px"


# ---------- Правила бизнеса ----------

ALL_CHECK_PAGES = list(STATIC_PAGES) + ["painting/lomykin-winter-morning.html", "artist/shelyuto.html"]


PRICE_CELLS = ".meta-row--price span:last-child"


@pytest.mark.parametrize("lang", ["en", "ua"])
def test_catalog_shows_prices(page, paintings, lang):
    # у каждой непроданной картины на карточке — её цена; у проданных цены нет
    open_page(page, "/catalog.html", lang)
    shown = sorted(page.locator("#catalog-grid " + PRICE_CELLS).all_text_contents())
    expected = sorted(format_price(p["price"], lang) for p in paintings if p["status"] != "sold")
    assert shown == expected
    assert page.locator("#catalog-grid .painting-card.is-sold .meta-row--price").count() == 0


@pytest.mark.parametrize("lang", ["en", "ua"])
def test_painting_page_shows_price(page, paintings, lang):
    available = next(p for p in paintings if p["status"] != "sold")
    open_page(page, f"/painting/{available['id']}.html", lang)
    assert page.locator("#pg-meta " + PRICE_CELLS).inner_text() == format_price(available["price"], lang)
    sold = next((p for p in paintings if p["status"] == "sold"), None)
    if sold:
        open_page(page, f"/painting/{sold['id']}.html", lang)
        assert page.locator("#pg-meta .meta-row--price").count() == 0


@pytest.mark.parametrize("lang", ["en", "ua"])
@pytest.mark.parametrize("path", ALL_CHECK_PAGES)
def test_no_other_currencies(page, path, lang):
    # все цены — в долларах; гривны, евро и фунты на сайте не должны появиться
    open_page(page, "/" + path, lang)
    found = re.findall(r"[€₴£]\s?\d|\d\s?(?:грн|EUR|UAH|GBP)\b", visible_text(page))
    assert not found, f"другая валюта: {found}"


@pytest.mark.parametrize("lang", ["en", "ua"])
@pytest.mark.parametrize("path", ALL_CHECK_PAGES)
def test_site_name_is_consistent(page, path, lang, seo_config):
    name = seo_config.get("site_name")
    if not name:
        pytest.skip("название сайта ещё не задано в tools/seo.config.json")
    open_page(page, "/" + path, lang)
    # «Odesa Art School» — ещё и настоящее училище из биографий художников,
    # поэтому проверяем только места, где пишется название сайта
    og = page.locator('meta[property="og:site_name"]')
    places = {
        "шапка": page.locator("header.site-header").inner_text(),
        "подвал": page.locator("footer.site-footer").inner_text(),
        "заголовок вкладки": page.title(),
        "og:site_name": og.get_attribute("content") if og.count() else name,
    }
    for where, text in places.items():
        for old in OLD_NAMES:
            assert old not in text, f"{where}: осталось старое название {old!r}"
    assert name in places["шапка"]
    assert name in places["подвал"]
    assert name in places["заголовок вкладки"]
    assert places["og:site_name"] == name


def test_images_have_alt_text(page):
    failures = []
    for path in ALL_CHECK_PAGES:
        open_page(page, "/" + path)
        missing = page.evaluate("() => [...document.images].filter(i => !i.hasAttribute('alt')).map(i => i.src)")
        failures += [f"{path}: {m}" for m in missing]
    assert failures == []


# ---------- Доступность (axe) ----------
# Падает только на критичных ошибках. Известные некритичные проблемы
# (контраст светлого текста, разметка областей страницы) печатаются в отчёт:
#   .venv/bin/pytest tests -k accessibility -s

@pytest.mark.parametrize("path", ALL_CHECK_PAGES)
def test_accessibility(page, path):
    from axe_playwright_python.sync_playwright import Axe
    open_page(page, "/" + path)
    violations = Axe().run(page).response["violations"]
    print(f"\n{path}: " + ", ".join(f"{v['id']} ({v['impact']}, {len(v['nodes'])})" for v in violations))
    critical = [v["id"] for v in violations if v["impact"] == "critical"]
    assert critical == [], f"критичные проблемы доступности: {critical}"
