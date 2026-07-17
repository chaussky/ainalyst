#!/bin/bash
# SessionStart hook: loads the AInalyst project context for the BA
# Whatever is printed to stdout is added as context that Claude sees at the start of the session

REPORTS_DIR="$CLAUDE_PROJECT_DIR/governance_plans/reports"
DATA_DIR="$CLAUDE_PROJECT_DIR/governance_plans/data"

echo "=== AInalyst project context ==="
echo ""

# Show which projects already exist (from the JSON files in data/)
if [ -d "$DATA_DIR" ] && [ "$(ls -A $DATA_DIR 2>/dev/null)" ]; then
    echo "📁 Active projects:"
    find "$DATA_DIR" -name '*.json' 2>/dev/null | \
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
    echo "📁 No projects yet. Start with a new project."
    echo "   Example: \"Starting a new project: HR automation at a bank\""
    echo ""
fi

# Show the most recently saved reports
if [ -d "$REPORTS_DIR" ] && [ "$(ls -A $REPORTS_DIR 2>/dev/null)" ]; then
    echo "📄 Latest artifacts in reports/:"
    find "$REPORTS_DIR" -name '*.md' 2>/dev/null | xargs -r ls -t 2>/dev/null | head -5 | \
        while read f; do
            echo "   • $(basename $f)"
        done
    echo ""
fi

echo "💡 Just describe your task in plain language, and I'll pick the right skill and tool."
echo "   Voice mode: /voice (hold space to talk, release to send)"
echo "   Plan mode: Shift+Tab twice (discuss the approach before acting)"
echo ""

# Show files ready for processing in inputs/
INPUTS_DIR="$CLAUDE_PROJECT_DIR/inputs"
INPUT_FILES=$(find "$INPUTS_DIR" -maxdepth 1 \( -name "*.txt" -o -name "*.md" -o -name "*.pdf" -o -name "*.docx" \) ! -name "README*" 2>/dev/null)
if [ -d "$INPUTS_DIR" ] && [ -n "$INPUT_FILES" ]; then
    echo "📂 Files ready for processing (inputs/):"
    echo "$INPUT_FILES" | while read f; do echo "   • $(basename $f)"; done
    echo "   Say: \"Process this material: inputs/FILENAME\""
    echo ""
fi
