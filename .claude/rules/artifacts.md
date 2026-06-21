# Rules for working with artifacts

## Folder structure
- `governance_plans/data/` — JSON files. The BA doesn't go here. This is internal data for the MCP.
- `governance_plans/reports/` — Markdown files. Point the BA here for results, and only here.

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
