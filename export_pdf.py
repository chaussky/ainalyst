#!/usr/bin/env python3
"""
export_pdf.py — Экспорт отчётов AInalyst из Markdown в PDF.

Использование:
    python export_pdf.py                    # все .md в reports/, спрашивает про существующие
    python export_pdf.py report_name.md     # один конкретный файл
    python export_pdf.py --all              # все .md без вопросов (не перезаписывает)
    python export_pdf.py --all --force      # все .md, перезаписать существующие

Библиотека: reportlab (ADR-092)
"""

import argparse
import re
import sys
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent / "governance_plans" / "reports"

# ── Цвета для консоли ─────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def check_reportlab() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        print(f"{RED}❌ Библиотека reportlab не установлена.{RESET}")
        print(f"   Установите: {BOLD}pip install reportlab{RESET}")
        return False


# ── Markdown → PDF через reportlab ────────────────────────────────────────────

def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    """Конвертирует один .md файл в .pdf через reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        Preformatted, ListFlowable, ListItem,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    text = md_path.read_text(encoding="utf-8")

    # ── Стили ─────────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    base_font = "Helvetica"

    def style(name, parent="Normal", **kwargs):
        return ParagraphStyle(name, parent=styles[parent], fontName=base_font, **kwargs)

    s_h1 = style("H1", fontSize=18, leading=24, spaceAfter=10, spaceBefore=18,
                 textColor=colors.HexColor("#1a1a2e"), fontName="Helvetica-Bold")
    s_h2 = style("H2", fontSize=14, leading=20, spaceAfter=8, spaceBefore=14,
                 textColor=colors.HexColor("#16213e"), fontName="Helvetica-Bold")
    s_h3 = style("H3", fontSize=12, leading=16, spaceAfter=6, spaceBefore=10,
                 textColor=colors.HexColor("#0f3460"), fontName="Helvetica-Bold")
    s_h4 = style("H4", fontSize=11, leading=15, spaceAfter=4, spaceBefore=8,
                 textColor=colors.HexColor("#333333"), fontName="Helvetica-Bold")
    s_body = style("Body", fontSize=10, leading=15, spaceAfter=6)
    s_code = ParagraphStyle("Code", fontName="Courier", fontSize=9, leading=13,
                             backColor=colors.HexColor("#f4f4f4"),
                             leftIndent=12, rightIndent=12,
                             spaceBefore=4, spaceAfter=4,
                             borderPad=6)
    s_bullet = style("Bullet", fontSize=10, leading=15, leftIndent=16,
                     spaceAfter=3, bulletIndent=6)
    s_quote = style("Quote", fontSize=10, leading=15, leftIndent=16,
                    textColor=colors.HexColor("#555555"),
                    borderColor=colors.HexColor("#cccccc"),
                    borderWidth=0, spaceAfter=6)

    # ── Парсинг Markdown → flowables ──────────────────────────────────────────
    story = []
    lines = text.splitlines()
    i = 0

    def escape(s: str) -> str:
        """Экранируем HTML-спецсимволы для reportlab Paragraph."""
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return s

    def inline(s: str) -> str:
        """Обработка inline-разметки: **bold**, *italic*, `code`."""
        s = escape(s)
        # **bold** и __bold__
        s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        s = re.sub(r'__(.+?)__',     r'<b>\1</b>', s)
        # *italic* и _italic_
        s = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', s)
        s = re.sub(r'_(.+?)_',       r'<i>\1</i>', s)
        # `code`
        s = re.sub(r'`(.+?)`', r'<font name="Courier">\1</font>', s)
        return s

    while i < len(lines):
        line = lines[i]

        # Пустая строка
        if not line.strip():
            story.append(Spacer(1, 6))
            i += 1
            continue

        # Горизонтальная линия
        if re.match(r'^---+$', line.strip()) or re.match(r'^===+$', line.strip()):
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=colors.HexColor("#cccccc"),
                                    spaceAfter=8, spaceBefore=8))
            i += 1
            continue

        # Заголовки
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            content = inline(m.group(2))
            st = [s_h1, s_h2, s_h3, s_h4][min(level - 1, 3)]
            story.append(Paragraph(content, st))
            i += 1
            continue

        # Блок кода (``` ... ```)
        if line.strip().startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # пропускаем закрывающий ```
            code_text = "\n".join(code_lines)
            story.append(Preformatted(code_text, s_code))
            story.append(Spacer(1, 4))
            continue

        # Таблица (| ... |)
        if line.strip().startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            story.extend(_render_table(table_lines, s_body))
            continue

        # Цитата (> ...)
        if line.startswith(">"):
            content = inline(line.lstrip(">").strip())
            story.append(Paragraph(f"<i>{content}</i>", s_quote))
            i += 1
            continue

        # Маркированный список
        m = re.match(r'^(\s*)[-*+]\s+(.*)', line)
        if m:
            items = []
            indent = len(m.group(1))
            while i < len(lines):
                ml = re.match(r'^(\s*)[-*+]\s+(.*)', lines[i])
                if ml:
                    items.append(ListItem(
                        Paragraph(inline(ml.group(2)), s_bullet),
                        bulletColor=colors.HexColor("#333333"),
                        leftIndent=16 + len(ml.group(1)) * 8,
                    ))
                    i += 1
                elif lines[i].strip() == "":
                    break
                else:
                    break
            story.append(ListFlowable(items, bulletType="bullet",
                                      bulletFontSize=8, leftIndent=8))
            story.append(Spacer(1, 4))
            continue

        # Нумерованный список
        m = re.match(r'^(\s*)\d+\.\s+(.*)', line)
        if m:
            items = []
            num = 1
            while i < len(lines):
                ml = re.match(r'^(\s*)\d+\.\s+(.*)', lines[i])
                if ml:
                    items.append(ListItem(
                        Paragraph(inline(ml.group(2)), s_bullet),
                        leftIndent=20,
                    ))
                    i += 1
                    num += 1
                elif lines[i].strip() == "":
                    break
                else:
                    break
            story.append(ListFlowable(items, bulletType="1",
                                      bulletFontSize=9, leftIndent=8))
            story.append(Spacer(1, 4))
            continue

        # Обычный абзац
        story.append(Paragraph(inline(line), s_body))
        i += 1

    # ── Генерация PDF ──────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=md_path.stem,
    )
    doc.build(story)


def _render_table(table_lines: list[str], body_style) -> list:
    """Рендерит Markdown-таблицу в reportlab Table."""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors

    rows = []
    is_header = True

    for line in table_lines:
        # Пропускаем разделительную строку (|---|---|)
        if re.match(r'^\|[-| :]+\|$', line.strip()):
            is_header = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append((cells, is_header))
        is_header = False

    if not rows:
        return []

    from reportlab.lib.styles import ParagraphStyle
    cell_style = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=13)
    header_style = ParagraphStyle("cellH", fontName="Helvetica-Bold", fontSize=9, leading=13)

    data = []
    for cells, is_hdr in rows:
        st = header_style if is_hdr else cell_style
        data.append([Paragraph(c, st) for c in cells])

    if not data:
        return []

    col_count = max(len(r) for r in data)
    from reportlab.lib.units import cm
    from reportlab.lib.pagesizes import A4
    available = A4[0] - 5 * cm
    col_width = available / col_count

    t = Table(data, colWidths=[col_width] * col_count, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#e8eaf6")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.HexColor("#1a1a2e")),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))

    from reportlab.platypus import Spacer
    return [t, Spacer(1, 8)]


# ── CLI ───────────────────────────────────────────────────────────────────────

def find_md_files() -> list[Path]:
    return sorted(REPORTS_DIR.glob("*.md"))


def pdf_path_for(md: Path) -> Path:
    return md.with_suffix(".pdf")


def convert_one(md: Path, force: bool, ask: bool) -> bool:
    """
    Конвертирует один файл. Возвращает True если конвертация выполнена.
    """
    pdf = pdf_path_for(md)

    if pdf.exists():
        if force:
            pass  # перезаписываем без вопросов
        elif ask:
            answer = input(f"  {YELLOW}⚠️  {pdf.name} уже существует. Перезаписать? [y/N]{RESET} ").strip().lower()
            if answer not in ("y", "да"):
                print(f"  Пропущен: {md.name}")
                return False
        else:
            print(f"  {YELLOW}Пропущен (уже существует):{RESET} {md.name}")
            return False

    print(f"  Конвертирую: {md.name} → {pdf.name} ...", end=" ", flush=True)
    try:
        md_to_pdf(md, pdf)
        print(f"{GREEN}✅{RESET}")
        return True
    except Exception as e:
        print(f"{RED}❌ Ошибка: {e}{RESET}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Экспорт отчётов AInalyst из Markdown в PDF.",
        epilog=(
            "Примеры:\n"
            "  python export_pdf.py                     # все .md, интерактивный режим\n"
            "  python export_pdf.py report.md           # один файл\n"
            "  python export_pdf.py --all               # все .md, не перезаписывать\n"
            "  python export_pdf.py --all --force       # все .md, перезаписать"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", nargs="?", help="Конкретный .md файл для конвертации")
    parser.add_argument("--all",   action="store_true", help="Конвертировать все .md в reports/")
    parser.add_argument("--force", action="store_true", help="Перезаписать существующие PDF без вопросов")
    args = parser.parse_args()

    if not check_reportlab():
        sys.exit(1)

    if not REPORTS_DIR.exists():
        print(f"{RED}❌ Папка не найдена: {REPORTS_DIR}{RESET}")
        sys.exit(1)

    print(f"\n{BOLD}AInalyst PDF Export{RESET}")
    print(f"Папка: {REPORTS_DIR}\n")

    # Один файл
    if args.file:
        md = REPORTS_DIR / args.file if not Path(args.file).is_absolute() else Path(args.file)
        if not md.exists():
            print(f"{RED}❌ Файл не найден: {md}{RESET}")
            sys.exit(1)
        convert_one(md, force=args.force, ask=True)
        return

    # Все файлы
    md_files = find_md_files()
    if not md_files:
        print(f"{YELLOW}В папке reports/ нет .md файлов.{RESET}")
        return

    print(f"Найдено .md файлов: {len(md_files)}\n")

    converted = 0
    for md in md_files:
        # Без --all: спрашиваем про каждый существующий PDF
        ok = convert_one(md, force=args.force, ask=not args.all)
        if ok:
            converted += 1

    print(f"\n{BOLD}Готово:{RESET} сконвертировано {converted} из {len(md_files)} файлов.")
    if converted > 0:
        print(f"PDF сохранены в: {REPORTS_DIR}")


if __name__ == "__main__":
    main()
