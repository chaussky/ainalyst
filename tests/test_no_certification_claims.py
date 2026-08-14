# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""The shipped text never claims IIBA's certifications or IIBA's blessing.

BABOK and IIBA are registered trademarks of the International Institute of
Business Analysis, and CBAP, CCBA and ECBA are the Institute's certification
programmes. This project follows the methodology; it has no relationship with
the Institute, and the README says so.

The risk this guards is not vandalism, it is enthusiasm. "Prepares you for
CBAP", "the official BABOK toolkit", "IIBA-approved" are the natural things to
write when you are proud of a tool that teaches a standard, and each of them is
a claim about someone else's certification programme rather than about this
software. A contributor writes one in a README paragraph, a reviewer reads the
paragraph for its meaning rather than its legal weight, and the claim ships.

CONTRIBUTING.md carries the rule in prose. Prose is advice: it is read once, by
people who already intend to follow it. This test is the part that keeps being
true after everyone has forgotten the conversation.

WHAT IS DELIBERATELY NOT COVERED
--------------------------------
`CONTRIBUTING.md` itself is skipped: the file that forbids these claims has to
quote them to forbid them, and there is no way to tell a quotation from a claim
by pattern alone. That is a real hole, accepted knowingly, and it is the one
file where the rule is most likely to be read before it is broken.

The trademark notice is exempt line by line rather than file by file, so the
rest of README.md stays covered: a line that states the disclaimer is allowed
to name what it disclaims ("not affiliated with, endorsed, sponsored, or
certified by IIBA"), while the marketing paragraph three lines above it is not.
"""

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Shipped text: what a user reads, in the repository and in the tools' own output.
# Internal working directories are absent for the same reason as in the encoding
# guard, and `tests/` is absent because it is not addressed to anyone.
MARKDOWN_ROOTS = ("docs", "skills", ".claude/rules")
CODE_ROOTS = ("skills",)

# The file that states the prohibition has to quote it. See the docstring.
EXEMPT_FILES = ("CONTRIBUTING.md",)

# A line that carries the trademark disclaimer may name the claims it disclaims.
DISCLAIMER_MARKERS = ("registered trademark", "товарные знаки")

# The Institute's certification programmes, plus its continuing-education unit.
# None of these has an innocent use in this repository: the platform neither
# grants them nor prepares anyone for them.
CERTIFICATION_PROGRAMMES = ("CBAP", "CCBA", "ECBA", "CDU", "CDUs")

# Words that turn a mention of the Institute into a claim of its blessing.
# Both languages are listed in both branches: the guard should catch a Russian
# phrase that reaches the English branch by way of a merge just as readily.
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
    """Every file whose words reach a reader, as (path, line number, line)."""
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
            "The Institute's certification programmes are named in shipped text. "
            "The platform neither grants them nor prepares anyone for them, so "
            "naming them makes a claim about someone else's programme:\n  "
            + "\n  ".join(offenders)
        ))

    def test_no_claim_of_iiba_endorsement(self):
        offenders = [
            f"{path}:{number}: {line.strip()[:100]}"
            for path, number, line in _shipped_text()
            if ENDORSEMENT_RE.search(line)
        ]
        self.assertFalse(offenders, (
            "Shipped text puts the Institute next to a word of approval. The "
            "project is not affiliated with, endorsed, sponsored or certified by "
            "IIBA; only the trademark notice may say so, and only to deny it:\n  "
            + "\n  ".join(offenders)
        ))

    def test_the_scan_actually_reaches_the_shipped_text(self):
        """A guard that scans nothing passes forever. This is the floor."""
        scanned = {path for path, _number, _line in _shipped_text()}
        self.assertIn(Path("README.md"), scanned)
        self.assertGreater(len(scanned), 30, "the scan path is wrong, not the text")


if __name__ == "__main__":
    unittest.main()
