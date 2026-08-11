# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""Text files are opened in a NAMED encoding, never the platform default.

Without an explicit `encoding=`, Python falls back to the locale encoding, and
the same code then behaves differently on three machines: UTF-8 on Linux and
macOS, cp1252 or cp1251 on Windows depending on the system language. Artifacts
this platform writes carry the analyst's own words, so the fallback is not a
theoretical concern.

The failure mode is what makes this worth a guard. A locale that has no slot
for a byte raises UnicodeDecodeError, which is loud and gets fixed. A locale
that maps every byte to SOMETHING decodes UTF-8 Russian into silent mojibake
and keeps going: the JSON still parses, because its braces and quotes are
ASCII, so a test that checks structure rather than words passes. The defect
then lives in the artifact, not in the run.

That is exactly how twelve such calls survived in the test harness until a
Windows CI runner with cp1252 met a Russian artifact. Nothing in a local run
had ever objected.

This test reads the tracked Python of the platform and fails on any text-mode
`open()`, `.open()`, `read_text()` or `write_text()` that leaves the encoding
to chance. The attribute forms — `Path.open`, `io.open`, `codecs.open` — appear
nowhere in this codebase; they are covered so that the first one written does
not slip through the one hole a guard like this naturally has.
"""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Tracked Python of the platform: the packages plus the top-level modules.
# Internal working directories are deliberately absent — they are not shipped.
PACKAGES = ("skills", "tests")

PATH_TEXT_METHODS = ("read_text", "write_text")


def _tracked_sources():
    """Every .py file that ships with the platform."""
    found = sorted(PROJECT_ROOT.glob("*.py"))
    for package in PACKAGES:
        found.extend(sorted((PROJECT_ROOT / package).rglob("*.py")))
    return [p for p in found if "__pycache__" not in p.parts]


def _looks_like_a_mode(value):
    """True for "r", "wb", "a+" — and false for a file name that merely is short.

    The mode sits in a different position depending on the call: the builtin
    takes the file first, Path.open() takes the mode first. Rather than guess
    which callable an attribute refers to, both positions are examined and only
    a genuine mode literal is accepted.
    """
    return (
        isinstance(value, str)
        and 0 < len(value) <= 3
        and set(value) <= set("rwxabt+")
    )


def _mode_of(call):
    """The mode of a call, or "r" when it is left to default."""
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    for argument in call.args[:2]:
        if isinstance(argument, ast.Constant) and _looks_like_a_mode(argument.value):
            return str(argument.value)
    return "r"


def _offenders_in(path):
    """Calls in one file that read or write text without naming an encoding."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if any(k.arg == "encoding" for k in node.keywords):
            continue

        func = node.func

        # Bare open(...) — not a helper whose name merely ends in _open
        if isinstance(func, ast.Name) and func.id == "open":
            # Binary mode carries bytes and rightly refuses an encoding.
            if "b" in _mode_of(node):
                continue
            found.append((node.lineno, "open()"))

        # Path.open(), io.open(), codecs.open() default the same way. None of
        # these are used here today; the rule is what keeps that true.
        elif isinstance(func, ast.Attribute) and func.attr == "open":
            if "b" in _mode_of(node):
                continue
            found.append((node.lineno, ".open()"))

        # Path.read_text() / Path.write_text() have no binary spelling.
        elif isinstance(func, ast.Attribute) and func.attr in PATH_TEXT_METHODS:
            found.append((node.lineno, f"{func.attr}()"))

    return found


def test_every_text_file_access_names_its_encoding():
    sources = _tracked_sources()
    assert sources, "no sources found — the scan path is wrong, not the code"

    offenders = []
    for path in sources:
        for lineno, what in _offenders_in(path):
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            offenders.append(f"{rel}:{lineno}: {what} without encoding=")

    assert not offenders, (
        "Text is read or written in the platform's default encoding, so these "
        "lines behave differently on Windows and Linux:\n  "
        + "\n  ".join(offenders)
        + '\n\nPass encoding="utf-8" explicitly. For bytes, open in binary mode.'
    )
