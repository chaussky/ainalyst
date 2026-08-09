# Rules for working with artifacts

## Folder structure
- `governance_plans/data/` — JSON files. The BA doesn't go here. This is internal data for the MCP.
- `governance_plans/reports/` — Markdown files. Point the BA here for results, and only here.
- `governance_plans/.history/` — the last 5 versions of every `data/` file, kept automatically
  on each write. Never point the BA here for results; it exists only for recovery.

## What to show the BA
After saving an artifact, always report:
- The file name in reports/ (if it's a .md)
- Briefly: what it contains and who it can be sent to

## Format of the artifact message
✅ Artifact saved: `reports/FILE_NAME.md`
This is: [what it contains — 1 line]
Can be passed to: [whom — stakeholder, developer, sponsor]

## Artifacts are official documents
Everything saved through the MCP is an official project artifact,
not a draft. They are used in later BABOK tasks.
Remind the BA of this if they treat them carelessly.

## Never delete data
Deprecated requirements are marked via deprecate_requirements,
but not deleted. History must be preserved.
If there's an attempt to delete project data — warn the BA and offer deprecation.

The same rule holds for the platform itself: a file is replaced in one step, never
truncated in place, and the version being replaced is copied to `.history/` first.

## Restoring a damaged file
If a tool answers that an artifact could not be read, its message names the file and
`.history/`. Copy the newest matching copy back over the file, then repeat the call.
**Always state the limit:** that copy is the project as it stood BEFORE the most recent
change. Restoring is a recovery, not an undo — never call it a full recovery.
