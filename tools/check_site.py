#!/usr/bin/env python3
"""Быстрая проверка сайта перед публикацией. Только читает файлы: ничего не копирует и не удаляет.

Запуск из корня сайта:  python3 tools/check_site.py
Порядок перед публикацией:  python3 tools/build_seo.py  →  python3 tools/check_site.py  →  тесты (tests/README.md)

Проверяет:
  - задан домен и название сайта (tools/seo.config.json);
  - у каждой картины и художника есть страница (английская и украинская в ua/), лишних страниц нет;
  - есть llms.txt, sitemap.xml, robots.txt;
  - все фото из paintings.json / artists.json / places.json существуют;
  - places.json ссылается только на существующие картины;
  - у каждой непроданной картины есть цена (целое число долларов в поле price), и она показана на её странице;
  - в текстах данных (описания, провенанс и т. п.) нет цен — цена хранится только в поле price;
  - в шапке, подвале и заголовках нет старых названий сайта;
  - нет файлов с подозрительными именами (инвойсы, копии, бэкапы), пробелами в имени или больше 25 МБ.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIRS = ["css", "js", "images", "painting", "artist", "ua"]
DATA_FILES = ["paintings.json", "artists.json", "places.json"]
TEMPLATES = ["index.html", "catalog.html", "artists.html", "artist.html", "painting.html",
             "about.html", "contact.html", "how-to-buy.html", "404.html"]
# Украинские версии страниц (создаёт build_seo.py в папке ua/)
UA_PAGES = ["index.html", "catalog.html", "artists.html", "about.html", "contact.html", "how-to-buy.html"]
OLD_SITE_NAMES = ["Odesa Art Gallery", "Odesa Art School"]  # «Odesa Art School» в биографиях — училище, это нормально
PRIVATE_NAME_RX = re.compile(r"invoice|инвойс|цен[ыа]|price|\.pdf$|\.pages$|копия|backup", re.I)
PRICE_RX = re.compile(r"[$€₴£]\s?\d|\d\s?(грн|USD|EUR|UAH|GBP)\b", re.I)
MAX_FILE = 25 * 1024 * 1024


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def main():
    problems, warnings = [], []
    exists = lambda rel: os.path.exists(os.path.join(ROOT, rel))

    cfg = json.loads(read("tools/seo.config.json"))
    if "YOUR-DOMAIN" in cfg.get("site_url", ""):
        problems.append("в tools/seo.config.json адрес-заглушка вместо домена")
    if not cfg.get("site_name"):
        problems.append("в tools/seo.config.json не задано название сайта (site_name)")

    paintings = json.loads(read("paintings.json"))
    artists = json.loads(read("artists.json"))
    places = json.loads(read("places.json"))
    painting_ids = {p["id"] for p in paintings}

    for prefix in ("", "ua/"):
        for kind, items in (("painting", paintings), ("artist", artists)):
            ids = {x["id"] for x in items}
            folder = prefix + kind
            for i in ids:
                if not exists(f"{folder}/{i}.html"):
                    problems.append(f"нет страницы {folder}/{i}.html: запустите tools/build_seo.py")
            if os.path.isdir(os.path.join(ROOT, folder)):
                for f in os.listdir(os.path.join(ROOT, folder)):
                    if f.endswith(".html") and f[:-5] not in ids:
                        warnings.append(f"лишняя страница {folder}/{f}: такой записи нет в JSON")
    for name in UA_PAGES:
        if not exists("ua/" + name):
            problems.append(f"нет украинской страницы ua/{name}: запустите tools/build_seo.py")
    for name in ("llms.txt", "sitemap.xml", "robots.txt"):
        if not exists(name):
            problems.append(f"нет файла {name}: запустите tools/build_seo.py")

    for p in paintings:
        for k, v in (p.get("photos") or {}).items():
            if v and not exists(v):
                problems.append(f"{p['id']}: нет файла {v}")
    for a in artists:
        if a.get("photo") and not exists(a["photo"]):
            problems.append(f"{a['id']}: нет файла {a['photo']}")
    for pl in places:
        if pl.get("photo") and not exists(pl["photo"]):
            problems.append(f"places.json {pl['id']}: нет файла {pl['photo']}")
        for pid in pl.get("paintingIds") or []:
            if pid not in painting_ids:
                problems.append(f"places.json {pl['id']}: нет картины {pid}")

    # Цена хранится только числом в поле price; в текстах данных цен быть не должно
    for name in DATA_FILES:
        for m in PRICE_RX.finditer(read(name)):
            problems.append(f"{name}: цена в тексте: {m.group(0)!r} (цена — только в поле price)")
    for p in paintings:
        price = p.get("price")
        if price is None:
            if p.get("status") != "sold":
                warnings.append(f"{p['id']}: нет цены (на сайте будет «по запросу»)")
            continue
        if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
            problems.append(f"{p['id']}: цена должна быть целым числом долларов больше нуля, сейчас {price!r}")
            continue
        if p.get("status") != "sold" and exists(f"painting/{p['id']}.html"):
            shown = f"${price:,}"
            if shown not in read(f"painting/{p['id']}.html"):
                problems.append(f"painting/{p['id']}.html: не показана цена {shown}: запустите tools/build_seo.py")

    pages = TEMPLATES + ["ua/" + n for n in UA_PAGES if exists("ua/" + n)] + [
        f"{d}/{f}" for d in ("painting", "artist", "ua/painting", "ua/artist") if os.path.isdir(os.path.join(ROOT, d))
        for f in sorted(os.listdir(os.path.join(ROOT, d))) if f.endswith(".html")]
    for rel in pages:
        text = read(rel)
        branded = " ".join(re.findall(r"<header.*?</header>|<footer.*?</footer>|<title>.*?</title>"
                                      r"|og:site_name\" content=\"[^\"]*", text, flags=re.S))
        for old in OLD_SITE_NAMES:
            if old in branded:
                problems.append(f"{rel}: старое название {old!r} в шапке/подвале/заголовке: запустите tools/build_seo.py")

    count, total = 0, 0
    for d in SITE_DIRS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, d)):
            dirnames[:] = [x for x in dirnames if not x.startswith(".")]
            for fn in filenames:
                if fn.startswith("."):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
                size = os.path.getsize(os.path.join(dirpath, fn))
                count, total = count + 1, total + size
                if size > MAX_FILE:
                    problems.append(f"{rel}: {size // 1024 // 1024} МБ — слишком большой файл")
                if PRIVATE_NAME_RX.search(fn):
                    warnings.append(f"{rel}: подозрительное имя (цена/инвойс/копия/бэкап), проверьте вручную")
                if " " in fn:
                    warnings.append(f"{rel}: пробел в имени файла — лучше заменить на дефис")

    print(f"Проверено: {len(paintings)} картин, {len(artists)} художников, {len(pages)} страниц, "
          f"{count} файлов ({total / 1024 / 1024:.1f} МБ).")
    for w in warnings:
        print("ПРЕДУПРЕЖДЕНИЕ:", w)
    for x in problems:
        print("ОШИБКА:", x)
    if not problems:
        print("Ошибок нет.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
