#!/bin/bash
# SessionStart hook — загружает контекст проекта AInalyst для BA
# Вывод в stdout добавляется как контекст который Claude видит в начале сессии

REPORTS_DIR="$CLAUDE_PROJECT_DIR/governance_plans/reports"
DATA_DIR="$CLAUDE_PROJECT_DIR/governance_plans/data"

echo "=== AInalyst — Контекст проекта ==="
echo ""

# Показываем какие проекты уже есть (по JSON файлам в data/)
if [ -d "$DATA_DIR" ] && [ "$(ls -A $DATA_DIR 2>/dev/null)" ]; then
    echo "📁 Активные проекты:"
    ls "$DATA_DIR"/*.json 2>/dev/null | \
        sed 's/.*\///' | \
        sed 's/_traceability_repo\.json//' | \
        sed 's/_prioritization\.json//' | \
        sed 's/_approval_history\.json//' | \
        sed 's/_design_options\.json//' | \
        sed 's/_recommendation\.json//' | \
        sed 's/_business_context\.json//' | \
        sed 's/_assumptions\.json//' | \
        sed 's/_architecture\.json//' | \
        sed 's/_change_strategy\.json//' | \
        sort -u | \
        while read proj; do echo "   • $proj"; done
    echo ""
else
    echo "📁 Проектов пока нет. Начните с нового проекта."
    echo "   Пример: «Начинаю новый проект — автоматизация HR в банке»"
    echo ""
fi

# Показываем последние сохранённые отчёты
if [ -d "$REPORTS_DIR" ] && [ "$(ls -A $REPORTS_DIR 2>/dev/null)" ]; then
    echo "📄 Последние артефакты в reports/:"
    ls -t "$REPORTS_DIR"/*.md 2>/dev/null | head -5 | \
        while read f; do
            echo "   • $(basename $f)"
        done
    echo ""
fi

echo "💡 Просто опишите задачу на русском — я подберу нужный скилл и инструмент."
echo "   Голосовой режим: /voice (держи пробел — говори, отпусти — отправь)"
echo "   Плановый режим: Shift+Tab дважды (обсудить подход перед действием)"
echo "   Экспорт в PDF:  python export_pdf.py [файл.md | --all] [--force]"
echo "   Канал проекта:  https://t.me/platform_ainalyst"
echo ""

# Показываем файлы готовые к обработке в inputs/
INPUTS_DIR="$CLAUDE_PROJECT_DIR/inputs"
INPUT_FILES=$(find "$INPUTS_DIR" -maxdepth 1 \( -name "*.txt" -o -name "*.md" -o -name "*.pdf" -o -name "*.docx" \) ! -name "README*" 2>/dev/null)
if [ -d "$INPUTS_DIR" ] && [ -n "$INPUT_FILES" ]; then
    echo "📂 Файлы готовые к обработке (inputs/):"
    echo "$INPUT_FILES" | while read f; do echo "   • $(basename $f)"; done
    echo "   Скажите: «Обработай материал: inputs/ИМЯ_ФАЙЛА»"
    echo ""
fi
