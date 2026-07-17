#!/bin/bash
# PostToolUse hook: notifies the BA when an artifact is saved to reports/
# Reads JSON from stdin, checks whether an .md file was created in reports/

INPUT=$(cat)

# Check whether this was a file-writing tool call
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

if [ -z "$TOOL_NAME" ]; then
    exit 0
fi

# Check whether a file was created in governance_plans/reports/
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
inp = d.get('tool_input', {})
# Look for the file path in different fields
path = inp.get('file_path') or inp.get('path') or ''
print(path)
" 2>/dev/null)

if echo "$FILE_PATH" | grep -q "governance_plans/reports/.*\.md"; then
    FILENAME=$(basename "$FILE_PATH")
    echo ""
    echo "✅ Artifact saved to reports/: $FILENAME"
    echo "   Open it: cat governance_plans/reports/$FILENAME"
fi

exit 0
