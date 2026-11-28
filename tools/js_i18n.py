"""Чтение словарей переводов прямо из JavaScript-файлов сайта.

Переводы живут в одном месте — там, где их использует сайт:
  - общие: `const I18N_COMMON = { en: {...}, ua: {...} };` в js/data.js;
  - страничные: `window.PAGE_I18N = { en: {...}, ua: {...} };` во встроенном <script> страницы.
build_seo.py берёт их отсюда, чтобы заранее записать украинский текст в страницы ua/.

Понимает только то, что реально встречается в словарях: ключи (с кавычками или без),
строки в "…", '…' или `…` (без ${…}), склейку через + и имя SITE_NAME.
Если встретит что-то другое — остановится с понятной ошибкой, а не угадает.
"""
import json
import re

_TOKEN = re.compile(r"""
    (?P<ws>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)
  | (?P<name>[A-Za-z_$][\w$]*)
  | (?P<num>\d+(?:\.\d+)?)
  | (?P<punct>[{}:,+])
""", re.S | re.X)


def _unquote(s):
    q, body = s[0], s[1:-1]
    if q == "`":
        if "${" in body:
            raise ValueError("шаблонные строки с ${…} в словаре не поддерживаются")
    # \' и \` в JSON не допустимы — снимаем экранирование перед разбором
    body = body.replace("\\'", "'").replace("\\`", "`")
    if q != '"':
        body = body.replace('"', '\\"')
    return json.loads('"' + body.replace("\n", "\\n") + '"')


class _Parser:
    def __init__(self, text, pos, names):
        self.text, self.pos, self.names = text, pos, names

    def next(self):
        while True:
            m = _TOKEN.match(self.text, self.pos)
            if not m:
                raise ValueError(f"не понял текст словаря: {self.text[self.pos:self.pos + 40]!r}")
            self.pos = m.end()
            if m.lastgroup != "ws":
                return m.lastgroup, m.group()

    def peek(self):
        save = self.pos
        tok = self.next()
        self.pos = save
        return tok

    def obj(self):
        kind, v = self.next()
        assert v == "{", f"ожидалась {{, а встретилось {v!r}"
        out = {}
        while True:
            kind, v = self.next()
            if v == "}":
                return out
            if kind == "str":
                key = _unquote(v)
            elif kind == "name":
                key = v
            else:
                raise ValueError(f"ожидался ключ, а встретилось {v!r}")
            kind, colon = self.next()
            assert colon == ":", f"после ключа {key!r} ожидалось двоеточие"
            out[key] = self.value()
            kind, v = self.next()
            if v == "}":
                return out
            assert v == ",", f"после значения {key!r} ожидалась запятая, а встретилось {v!r}"

    def value(self):
        if self.peek()[1] == "{":
            return self.obj()
        parts = [self.atom()]
        while self.peek()[1] == "+":
            self.next()
            parts.append(self.atom())
        return "".join(parts)

    def atom(self):
        kind, v = self.next()
        if kind == "str":
            return _unquote(v)
        if kind == "num":
            return v
        if kind == "name" and v in self.names:
            return self.names[v]
        raise ValueError(f"в словаре встретилось {v!r} — такое значение скрипт не умеет читать")


def read_dict(text, marker, names=None):
    """Находит `marker = {…}` в тексте и возвращает словарь. None — если маркера нет."""
    m = re.search(re.escape(marker) + r"\s*=\s*", text)
    if not m:
        return None
    return _Parser(text, m.end(), names or {}).obj()
