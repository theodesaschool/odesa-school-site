#!/usr/bin/env python3
"""Собирает чистую папку для публикации сайта (без CLAUDE.md, .claude, .git, бэкапов, tools и т.д.).

Запуск из корня сайта:  python3 tools/make_publish.py
Результат: папка ../my-site-publish рядом с сайтом (её содержимое загружается на хостинг).
Исходную папку скрипт не меняет. Папку публикации он пересоздаёт при каждом запуске
(только папку с именем my-site-publish).
"""
import argparse
import json
import os
import re
import shutil
import sys

TOP_FILES = ["index.html", "catalog.html", "artists.html", "artist.html", "painting.html",
             "about.html", "contact.html", "how-to-buy.html",
             "artists.json", "paintings.json", "places.json",
             "favicon.svg", "robots.txt", "sitemap.xml"]
TOP_DIRS = ["css", "js", "images", "painting", "artist"]
SKIP_NAMES = {".DS_Store"}
PRIVATE_NAME_RX = re.compile(r"invoice|инвойс|цен[ыа]|price|\.pdf$|\.pages$|копия|backup", re.I)
PRICE_RX = re.compile(r"[$€₴£]\s?\d|\d\s?(грн|USD|EUR|UAH|GBP)\b", re.I)
MAX_FILE = 25 * 1024 * 1024  # лимит Cloudflare Pages на один файл


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ap.add_argument("--root", default=root)
    ap.add_argument("--dest", default=os.path.join(os.path.dirname(root), "my-site-publish"))
    args = ap.parse_args()
    root, dest = args.root, args.dest
    problems, warnings = [], []

    # 1. Проверки до копирования
    cfg = json.load(open(os.path.join(root, "tools", "seo.config.json"), encoding="utf-8"))
    if "YOUR-DOMAIN" in cfg.get("site_url", "") or "YOUR-DOMAIN" in open(os.path.join(root, "sitemap.xml"), encoding="utf-8").read():
        problems.append("в sitemap.xml или seo.config.json остался адрес-заглушка: впишите домен и запустите tools/build_seo.py")
    paintings = json.load(open(os.path.join(root, "paintings.json"), encoding="utf-8"))
    for p in paintings:
        if not os.path.exists(os.path.join(root, "painting", p["id"] + ".html")):
            problems.append(f"нет страницы painting/{p['id']}.html: запустите tools/build_seo.py")
        for k, v in (p.get("photos") or {}).items():
            if v and not os.path.exists(os.path.join(root, v)):
                problems.append(f"{p['id']}: нет файла {v}")
    for name in ("paintings.json", "artists.json", "places.json"):
        for m in PRICE_RX.finditer(open(os.path.join(root, name), encoding="utf-8").read()):
            warnings.append(f"{name}: похоже на цену: {m.group(0)!r}")
    if problems:
        print("ОСТАНОВЛЕНО, сначала исправьте:")
        for x in problems:
            print(" -", x)
        return 1

    # 2. Подготовка папки назначения (пересоздаём только нашу папку my-site-publish)
    if os.path.exists(dest):
        if os.path.basename(os.path.normpath(dest)) != "my-site-publish" and os.listdir(dest):
            print(f"ОСТАНОВЛЕНО: {dest} уже существует и не называется my-site-publish. Укажите другую папку через --dest.")
            return 1
        shutil.rmtree(dest)
    os.makedirs(dest)

    # 3. Копирование по белому списку
    count, total, biggest = 0, 0, (0, "")

    def copy(src, rel):
        nonlocal count, total, biggest
        size = os.path.getsize(src)
        if size > MAX_FILE:
            problems.append(f"{rel}: {size // 1024 // 1024} МБ, больше лимита хостинга 25 МБ")
        if PRIVATE_NAME_RX.search(os.path.basename(rel)):
            warnings.append(f"{rel}: подозрительное имя файла (цена/инвойс/копия/бэкап), проверьте вручную")
        out = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copy2(src, out)
        count += 1
        total += size
        if size > biggest[0]:
            biggest = (size, rel)

    for f in TOP_FILES:
        src = os.path.join(root, f)
        if os.path.exists(src):
            copy(src, f)
        else:
            warnings.append(f"нет файла {f}")
    for d in TOP_DIRS:
        base = os.path.join(root, d)
        if not os.path.isdir(base):
            warnings.append(f"нет папки {d}/")
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if not x.startswith(".")]
            for fn in filenames:
                if fn in SKIP_NAMES or fn.startswith("."):
                    continue
                src = os.path.join(dirpath, fn)
                copy(src, os.path.relpath(src, root))

    print(f"Готово: {count} файлов, {total / 1024 / 1024:.1f} МБ → {dest}")
    print(f"Самый большой файл: {biggest[1]} ({biggest[0] / 1024 / 1024:.1f} МБ)")
    for w in warnings:
        print("ПРЕДУПРЕЖДЕНИЕ:", w)
    for x in problems:
        print("ОШИБКА:", x)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
