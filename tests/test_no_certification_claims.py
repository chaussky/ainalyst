# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""Поставляемый текст не заявляет ни сертификаций IIBA, ни её благословения.

BABOK и IIBA — зарегистрированные товарные знаки International Institute of
Business Analysis, а CBAP, CCBA и ECBA — сертификационные программы института.
Этот проект следует методологии; отношения к институту он не имеет, и README
это заявляет.

Опасность, от которой стоит сторож, — не вандализм, а энтузиазм. «Готовит к
CBAP», «официальный инструмент по BABOK», «одобрено IIBA» — это первое, что
просится написать про инструмент, который учит стандарту, и каждая такая фраза
утверждает нечто о чужой сертификационной программе, а не об этой программе.
Правку вносят в абзац README, рецензент читает абзац по смыслу, а не по
юридическому весу, — и утверждение уезжает в поставку.

Правило записано прозой в CONTRIBUTING.md. Проза — это совет: её читают один
раз и те, кто и так собирался ей следовать. Этот тест — та часть, которая
остаётся верной после того, как разговор забыт.

ЧТО НАМЕРЕННО НЕ ПОКРЫТО
------------------------
Сам `CONTRIBUTING.md` пропущен: файл, запрещающий эти утверждения, обязан их
процитировать, а отличить цитату от утверждения одним шаблоном нельзя. Это
настоящая дыра, оставленная осознанно, — и это ровно тот файл, где правило
скорее прочтут, чем нарушат.

Оговорка о знаках освобождена построчно, а не пофайльно, поэтому остальной
README остаётся под охраной: строка, которая заявляет непричастность, вправе
назвать то, от чего открещивается («не аффилирован с IIBA, не одобрен и не
сертифицирован ею»), а маркетинговый абзац тремя строками выше — не вправе.
"""

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Поставляемый текст: то, что читает пользователь — в репозитории и в выводе самих
# инструментов. Внутренние рабочие каталоги отсутствуют по той же причине, что и в
# стороже кодировок, а `tests/` — потому что он ни к кому не обращён.
MARKDOWN_ROOTS = ("docs", "skills", ".claude/rules")
CODE_ROOTS = ("skills",)

# Файл, формулирующий запрет, обязан его процитировать. См. докстринг.
EXEMPT_FILES = ("CONTRIBUTING.md",)

# Строка с оговоркой о знаках вправе назвать то, от чего открещивается.
DISCLAIMER_MARKERS = ("registered trademark", "товарные знаки")

# Сертификационные программы института плюс его единица непрерывного развития.
# Ни у одной нет невинного применения в этом репозитории: платформа их не выдаёт
# и ни к одной не готовит.
CERTIFICATION_PROGRAMMES = ("CBAP", "CCBA", "ECBA", "CDU", "CDUs")

# Слова, превращающие упоминание института в заявление о его благословении.
# Оба языка перечислены в обеих ветках: сторож обязан поймать русскую фразу,
# приехавшую в английскую ветку слиянием, ровно так же охотно.
ENDORSEMENT_WORDS = (
    "approv", "endors", "certif", "accredit", "official", "partner",
    "sponsor", "compliant", "authoris", "authoriz",
    "одобр", "сертифиц", "аккредит", "официальн", "партн", "спонсор",
    "уполномоч", "соответству",
)

PROGRAMME_RE = re.compile(r"\b(" + "|".join(CERTIFICATION_PROGRAMMES) + r")\b")
_WORDS = "|".join(ENDORSEMENT_WORDS)
ENDORSEMENT_RE = re.compile(
    r"IIBA.{0,60}?(" + _WORDS + r")|(" + _WORDS + r").{0,60}?IIBA",
    re.IGNORECASE,
)


def _shipped_text():
    """Каждый файл, чьи слова доходят до читателя, как (путь, номер строки, строка)."""
    paths = sorted(PROJECT_ROOT.glob("*.md")) + sorted(PROJECT_ROOT.glob("*.py"))
    for root in MARKDOWN_ROOTS:
        paths.extend(sorted((PROJECT_ROOT / root).rglob("*.md")))
    for root in CODE_ROOTS:
        paths.extend(sorted((PROJECT_ROOT / root).rglob("*.py")))

    for path in paths:
        if "__pycache__" in path.parts or "superpowers" in path.parts:
            continue
        if path.name in EXEMPT_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if any(marker in lowered for marker in DISCLAIMER_MARKERS):
                continue
            yield path.relative_to(PROJECT_ROOT), number, line


class TestTheShippedTextClaimsNoCertification(unittest.TestCase):

    def test_no_certification_programme_is_named(self):
        offenders = [
            f"{path}:{number}: {line.strip()[:100]}"
            for path, number, line in _shipped_text()
            if PROGRAMME_RE.search(line)
        ]
        self.assertFalse(offenders, (
            "В поставляемом тексте названы сертификационные программы института. "
            "Платформа их не выдаёт и ни к одной не готовит, поэтому упоминание "
            "заявляет нечто о чужой программе:\n  "
            + "\n  ".join(offenders)
        ))

    def test_no_claim_of_iiba_endorsement(self):
        offenders = [
            f"{path}:{number}: {line.strip()[:100]}"
            for path, number, line in _shipped_text()
            if ENDORSEMENT_RE.search(line)
        ]
        self.assertFalse(offenders, (
            "В поставляемом тексте имя института стоит рядом со словом одобрения. "
            "Проект не аффилирован с IIBA, не одобрен, не спонсирован и не "
            "сертифицирован ею; сказать это вправе только оговорка о знаках — и "
            "только чтобы это отрицать:\n  "
            + "\n  ".join(offenders)
        ))

    def test_the_scan_actually_reaches_the_shipped_text(self):
        """Сторож, который ничего не обходит, проходит всегда. Это нижняя граница."""
        scanned = {path for path, _number, _line in _shipped_text()}
        self.assertIn(Path("README.md"), scanned)
        self.assertGreater(len(scanned), 30, "неверен путь обхода, а не текст")


if __name__ == "__main__":
    unittest.main()
