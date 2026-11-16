# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## О проекте

Статический двуязычный (EN/UA) сайт галереи «Odesa Art School» — одесская живопись XX века. Без сборки, без npm, без фреймворков: HTML + CSS + чистый JS. Тестов и линтера нет.

## Запуск локально

```bash
python3 -m http.server 8400 --bind 127.0.0.1
# http://localhost:8400
```

Открывать HTML двойным кликом (`file://`) нельзя: данные грузятся через `fetch`, и без сервера страница покажет баннер об ошибке (`showFetchErrorBanner` в `js/main.js`). После правок JSON проверять консоль и вкладку Network на 404 и «Could not load …».

## Архитектура

- Каждая страница подключает по порядку `js/data.js` → `js/main.js` → свой встроенный `<script>`.
- `js/data.js` — только общие переводы интерфейса `I18N_COMMON` (`en`/`ua`). Тексты, нужные одной странице, лежат в её `window.PAGE_I18N`.
- `js/main.js` — общие функции: `loadAll()` загружает `artists.json` и `paintings.json` в глобальные `ARTISTS`/`PAINTINGS`; `getArtist`, `getPaintingById`, `getPaintingsByArtist`; шаблоны `paintingCardHtml` / `paintingThumbHtml`; переключение языка.
- Язык: элементы с `data-i18n="ключ"` заменяются через `innerHTML` из словаря; выбор хранится в `localStorage("lang")`. `initLangSwitch(onChange)` перерисовывает динамический контент через колбэк — новые страницы должны рендерить данные внутри этого колбэка.
- Страницы деталей: `painting/<painting.id>.html` и `artist/<artist.id>.html`. Их **генерирует** `python3 tools/build_seo.py` из шаблонов `painting.html` / `artist.html` (шаблоны сами закрыты от индексации через `noindex`; ID берётся из `window.PAINTING_ID` / `window.ARTIST_ID`, запасной вариант — `?id=` / `?artist=`). Не править сгенерированные файлы вручную.
- `about.html` дополнительно грузит `places.json` (места Одессы ↔ картины через `paintingIds`).
- `contact.html` и `how-to-buy.html` — только текст и переводы, без данных.
- Шапка и навигация продублированы в каждом HTML вручную — при изменении меню править все 8 страниц. Активный пункт определяется по `<body data-page>` ↔ `data-nav`.
- Кнопка «Inquire» ведёт в Instagram `theodesaschool`; цены на сайте не показываются («Price on request»).

## Данные

Новая картина или художник добавляются правкой JSON — HTML/JS менять не нужно, **но после правки JSON обязательно запустить `python3 tools/build_seo.py`**: он создаёт страницы `painting/<id>.html` / `artist/<id>.html`, `sitemap.xml`, `robots.txt` и мета-теги. Без этого ссылки на новую картину дадут 404.

Связи: `painting.artistId` → `artist.id`; `places.json → paintingIds[]` → `painting.id`. ID — латинский slug `<фамилия>-<название>`, он же имя папки с фото.

### Запись в `paintings.json`

```json
{
  "id": "lomykin-winter-morning",
  "artistId": "lomykin",
  "title": { "en": "Winter Morning", "ua": "Зимовий ранок" },
  "year": 1969,
  "yearNote": { "en": "circa 1960s", "ua": "орієнтовно 1960-і" },
  "medium": { "en": "Oil on board", "ua": "Картон, олія" },
  "size": "50 × 80 cm (19.7 × 31.5 in)",
  "status": "available",
  "description": { "en": "", "ua": "" },
  "photos": {
    "front": "images/paintings/lomykin-winter-morning/front.jpg",
    "framed": "images/paintings/lomykin-winter-morning/framed.jpg",
    "back": "images/paintings/lomykin-winter-morning/back.jpg",
    "documents": null,
    "signature": null
  },
  "hue": ["#8fb3c9", "#dbe6df", "#c9a86b"],
  "signature": { "en": "", "ua": "" },
  "inscription": { "en": "", "ua": "" },
  "condition": { "en": "", "ua": "" },
  "provenance": [{ "en": "...", "ua": "..." }],
  "documents": [{ "en": "...", "ua": "..." }],
  "details": [{ "src": "images/paintings/<id>/detail-1.jpg", "caption": { "en": "...", "ua": "..." } }]
}
```

- Все текстовые поля — объекты `{ en, ua }`; `size` — строка, общая для обоих языков.
- `yearNote` необязателен; если есть, показывается вместо `year` (`year` может быть `null`).
- `status`: `available` | `sold` | `reserved` (подписи — `status_*` в `I18N_COMMON`).
- `photos.*` — путь или `null`. Галерея на `painting.html` показывает их в порядке front → framed → back → documents → signature, пропуская `null`. Указанный путь обязан существовать.
- `hue` — 3 цвета для градиента-заглушки, пока фото не загрузилось или отсутствует.
- `provenance`, `documents`, `details` — массивы, могут быть пустыми; пустые блоки на странице не выводятся.

Фото: `images/paintings/<id>/{front,framed,back}.jpg`. Новые `documents.jpg` не добавлять без явного разрешения пользователя (см. «Приватные данные»).

### Обработка новых фото

Перед добавлением в `images/` каждое новое фото:

1. Оригинал сохранить в `~/Desktop/my-site-materials/originals-images/` с тем же относительным путём (`originals-images/images/paintings/<id>/front.jpg`) и сверить копию побайтно (`cmp`). Только после этого менять файл в `images/`.
2. Если длинная сторона больше 2400 px — уменьшить до 2400 px, пропорции не менять. Меньшие фото не увеличивать.
3. Сохранить JPEG с качеством около 85 через Pillow (`quality=85, optimize=True, progressive=True`), сохранив `icc_profile` и `exif`. Не через `sips`: на этих фото он даёт файл больше оригинала.
4. Имя файла не менять. Если результат не меньше оригинала — оставить оригинал.

## SEO

- Адрес сайта лежит в `tools/seo.config.json` (`site_url`): `https://theodesaschool.com`. При смене домена — поправить здесь и перезапустить скрипт.
- Скрипт также вставляет блок `<!-- seo:start --> … <!-- seo:end -->` в `<head>` статических страниц (description, Open Graph, canonical, favicon). Текст описаний задан в `tools/build_seo.py` (`STATIC_PAGES`); не править блок руками.
- Сгенерированные страницы используют `<base href="/">`, поэтому сайт должен лежать в корне домена (не в подпапке вроде `user.github.io/repo/`).
- Описание картины для поисковиков берётся из `description.en`; если пусто — собирается из названия, техники и размера. Цены в эти тексты не попадают (скрипт предупреждает, если видит валюту).
- Хостинг — **GitHub Pages** (репозиторий `theodesaschool/odesa-school-site`, ветка `main`, папка `/root`). Домен `theodesaschool.com` подключён через файл `CNAME` в корне репозитория + DNS-записи в Cloudflare (4 A-записи на IP GitHub Pages для `@`, CNAME `www` → `theodesaschool.github.io`, обе без прокси — «DNS only»).
- Публикация = обычный git push в `main`: GitHub Pages сам пересобирает и выкладывает сайт за одну-две минуты. Перед пушем: `build_seo.py`, затем можно прогнать `tools/make_publish.py` как дополнительную проверку на цены/заглушки/пропавшие фото (он просто сканирует файлы, без выгрузки; саму копию в `~/Desktop/my-site-publish` для публикации использовать не нужно).
- Сгенерированные файлы (`painting/`, `artist/`, `sitemap.xml`, `robots.txt`) коммитятся в git, это часть статического сайта.

## Приватные данные и рабочие материалы

- **Репозиторий будет публичным.** Всё, что попадает в git, считать опубликованным — включая историю коммитов.
- **Новые фото документов (`documents.jpg`) не добавлять без явного разрешения пользователя.** По умолчанию `photos.documents` — `null`. На опубликованном документе не должно быть имён частных лиц (владельцев, покупателей, адресатов), людей и цен. Сейчас на сайте 8 разрешённых сертификатов (экспертиза Одесского худ. музея и сертификаты галереи NT-Art).
- **Никакие цены на сайт не попадают** — ни в JSON (включая `description`), ни в HTML. На сайте только «Price on request».
- **Инвойсы, цены клиентов и приватные документы не публикуются и не добавляются в репозиторий** — ни как файлы, ни как текст. Сюда же относится каталог «с ценами» (`.pages`/PDF).
- В `details` — только фрагменты самой картины, без документов и людей.
- Рабочие материалы (исходные фото `Back/`, `Картины без рамы/`, папка документов, PDF/.pages-каталоги, бэкапы JSON/JS) лежат вне репозитория в `~/Desktop/my-site-materials/`. Новые исходники класть туда, а в `images/` — только обработанные файлы для сайта.
- `.gitignore` дополнительно отсекает `*.pdf`, `*.pages`, `*копия*`, `*.backup*`, `.DS_Store`, `.claude/`.

## Git

- **Ничего не коммитить и не пушить без прямой просьбы пользователя.** Изменения оставлять в рабочей папке и показывать `git status` / `git diff --stat`.
- Удалённый репозиторий: `https://github.com/theodesaschool/odesa-school-site` (публичный). `git push` в `main` = публикация сайта (см. SEO) — делать только по явной просьбе.
