# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""The .docx promise is backed by a WORKING recipe in CLAUDE.md.

The docs promise .docx among supported input formats, but the agent's Read
tool cannot open binary files, and no platform code parses docx. The agreed
product answer: CLAUDE.md carries a stdlib-only extraction snippet the agent
runs verbatim. This test executes the snippet AS PUBLISHED in CLAUDE.md
against a real minimal docx, so the documented promise cannot rot silently.
"""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DOCUMENT_XML = (
    '<?xml version="1.0"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body>"
    "<w:p><w:r><w:t>Interview with CFO: payment terms are 45 days.</w:t></w:r></w:p>"
    "<w:p><w:r><w:t>Risk: penalties &amp; interest accrue after day 60.</w:t></w:r></w:p>"
    "</w:body></w:document>"
)

CONTENT_TYPES_XML = (
    '<?xml version="1.0"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/></Types>'
)


def _snippet_from_claude_md() -> str:
    text = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    docx_sections = text.split(".docx")
    assert len(docx_sections) > 1, "CLAUDE.md no longer mentions .docx"
    for chunk in docx_sections[1:]:
        fence = re.search(r"```python\n(.*?)```", chunk, flags=re.DOTALL)
        if fence:
            return fence.group(1)
    raise AssertionError(
        "CLAUDE.md mentions .docx but carries no ```python extraction snippet"
    )


def test_claude_md_docx_snippet_extracts_text(tmp_path):
    docx = tmp_path / "sample.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", DOCUMENT_XML)
        z.writestr("[Content_Types].xml", CONTENT_TYPES_XML)

    script = tmp_path / "snippet.py"
    script.write_text(_snippet_from_claude_md(), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(script), str(docx)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "Interview with CFO: payment terms are 45 days." in out
    assert "Risk: penalties & interest accrue after day 60." in out, (
        "XML entities must be unescaped"
    )
    first = out.index("Interview with CFO")
    second = out.index("Risk: penalties")
    assert "\n" in out[first:second], "paragraphs must stay on separate lines"
