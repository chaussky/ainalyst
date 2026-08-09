#!/bin/bash
# PostToolUse hook — уведомляет BA когда артефакт сохранён в reports/
# Читает JSON из stdin, проверяет был ли создан .md файл в reports/

INPUT=$(cat)

# Проверяем был ли это вызов инструмента записи файла
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

if [ -z "$TOOL_NAME" ]; then
    exit 0
fi

# Проверяем был ли создан файл в governance_plans/reports/
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
inp = d.get('tool_input', {})
# Ищем путь к файлу в разных полях
path = inp.get('file_path') or inp.get('path') or ''
print(path)
" 2>/dev/null)

if echo "$FILE_PATH" | grep -q "governance_plans/reports/.*\.md"; then
    FILENAME=$(basename "$FILE_PATH")
    echo ""
    echo "✅ Артефакт сохранён в reports/: $FILENAME"
    echo "   Открыть: cat governance_plans/reports/$FILENAME"
fi

exit 0
