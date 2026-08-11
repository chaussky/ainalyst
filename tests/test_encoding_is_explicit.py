# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""Текстовые файлы открываются в ЯВНО НАЗВАННОЙ кодировке, а не в умолчании платформы.

Без `encoding=` Python берёт кодировку локали, и один и тот же код ведёт себя
по-разному на трёх машинах: UTF-8 на Linux и macOS, cp1252 или cp1251 на Windows
в зависимости от языка системы. Артефакты платформы несут слова самого аналитика,
поэтому умолчание здесь — не теоретическая придирка.

Сторож нужен из-за характера отказа. Локаль, у которой для байта нет клетки,
поднимает UnicodeDecodeError — это громко и это чинят. Локаль, отображающая любой
байт хоть куда-нибудь, декодирует русский UTF-8 в беззвучную кашу и идёт дальше:
JSON по-прежнему разбирается, потому что его скобки и кавычки — ASCII, и тест,
который проверяет структуру, а не слова, проходит. Дефект остаётся в артефакте,
а не в прогоне.

Ровно так двенадцать таких вызовов дожили в тестовой оснастке до дня, когда
Windows-раннер с cp1252 встретил русский артефакт. Локальный прогон не возражал
никогда.

Тест читает отслеживаемый Python платформы и падает на любом текстовом
`open()`, `.open()`, `read_text()` или `write_text()`, оставившем кодировку на
волю случая. Формы через атрибут — `Path.open`, `io.open`, `codecs.open` — в
этом коде не встречаются ни разу; они покрыты, чтобы первая же написанная не
проскочила в ту единственную дыру, которая у такого сторожа есть по природе.
"""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Отслеживаемый Python платформы: пакеты плюс модули верхнего уровня.
# Внутренних рабочих каталогов здесь нет намеренно — они не поставляются.
PACKAGES = ("skills", "tests")

PATH_TEXT_METHODS = ("read_text", "write_text")


def _tracked_sources():
    """Все .py, которые поставляются вместе с платформой."""
    found = sorted(PROJECT_ROOT.glob("*.py"))
    for package in PACKAGES:
        found.extend(sorted((PROJECT_ROOT / package).rglob("*.py")))
    return [p for p in found if "__pycache__" not in p.parts]


def _looks_like_a_mode(value):
    """Истина для "r", "wb", "a+" — и ложь для имени файла, просто короткого.

    Режим стоит в разной позиции в зависимости от вызова: встроенный open берёт
    первым файл, а Path.open() — первым режим. Вместо угадывания, на что
    ссылается атрибут, осматриваются обе позиции и принимается только то, что
    действительно является литералом режима.
    """
    return (
        isinstance(value, str)
        and 0 < len(value) <= 3
        and set(value) <= set("rwxabt+")
    )


def _mode_of(call):
    """Режим вызова, либо "r", когда он оставлен по умолчанию."""
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    for argument in call.args[:2]:
        if isinstance(argument, ast.Constant) and _looks_like_a_mode(argument.value):
            return str(argument.value)
    return "r"


def _offenders_in(path):
    """Вызовы в одном файле, читающие или пишущие текст без названной кодировки."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if any(k.arg == "encoding" for k in node.keywords):
            continue

        func = node.func

        # Голый open(...) — не помощник, у которого имя лишь кончается на _open
        if isinstance(func, ast.Name) and func.id == "open":
            # Двоичный режим несёт байты и справедливо отвергает кодировку.
            if "b" in _mode_of(node):
                continue
            found.append((node.lineno, "open()"))

        # Path.open(), io.open(), codecs.open() умолчание берут так же. Сегодня
        # здесь нет ни одного такого вызова; правило и держит это состояние.
        elif isinstance(func, ast.Attribute) and func.attr == "open":
            if "b" in _mode_of(node):
                continue
            found.append((node.lineno, ".open()"))

        # У Path.read_text() / Path.write_text() двоичного написания нет.
        elif isinstance(func, ast.Attribute) and func.attr in PATH_TEXT_METHODS:
            found.append((node.lineno, f"{func.attr}()"))

    return found


def test_every_text_file_access_names_its_encoding():
    sources = _tracked_sources()
    assert sources, "исходники не найдены — неверен путь обхода, а не код"

    offenders = []
    for path in sources:
        for lineno, what in _offenders_in(path):
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            offenders.append(f"{rel}:{lineno}: {what} без encoding=")

    assert not offenders, (
        "Текст читается или пишется в кодировке платформы по умолчанию, поэтому "
        "эти строки ведут себя по-разному на Windows и Linux:\n  "
        + "\n  ".join(offenders)
        + '\n\nПередайте encoding="utf-8" явно. Для байтов открывайте в двоичном режиме.'
    )
