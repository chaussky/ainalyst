# Правила работы с артефактами

## Folder structure
- `governance_plans/data/` — JSON files. The BA doesn't go here. This is internal data for the MCP.
- `governance_plans/reports/` — Markdown files. Point the BA here for results, and only here.
- `governance_plans/.history/` — the last 5 versions of every `data/` file, kept automatically
  on each write. Never point the BA here for results; it exists only for recovery.

## Что показывать BA
После сохранения артефакта всегда сообщай:
- Имя файла в reports/ (если это .md)
- Коротко: что в нём содержится и кому его можно отправить

## Формат сообщения об артефакте
✅ Артефакт сохранён: `reports/ИМЯ_ФАЙЛА.md`
Это: [что содержит — 1 строка]
Можно передать: [кому — стейкхолдер, разработчик, спонсор]

## Артефакты — официальные документы
Всё что сохраняется через MCP — это официальные артефакты проекта,
не черновики. Они используются в последующих задачах BABOK.
Напоминай BA об этом если он относится к ним легкомысленно.

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
