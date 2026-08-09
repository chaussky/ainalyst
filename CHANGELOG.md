# Changelog — AI Платформа AIналитик (AInalyst)

All notable changes to the project are documented here.  
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
The project follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **A stored artifact survives an interrupted write.** Every project JSON file is now replaced in a single step (written beside the target, then moved into place), so an interruption — Ctrl+C, a full disk, a dead battery, an antivirus holding the handle — leaves the previous version whole instead of a truncated one. Previously 32 places wrote straight over the file, truncating it before the replacement existed.
- **Previous versions are kept.** Before a file is replaced, the version being replaced is copied to `governance_plans/.history/`; the last five generations of each artifact are retained. This covers what atomicity cannot: content written perfectly and *wrong*, and hand edits. The message for a damaged artifact now names that folder — and states that the newest copy is the project as it stood before the most recent change.
- **A malformed structure is refused on write.** The requirements graph accepts only `requirements` and `links` as lists; the refusal happens before the file is touched and reaches the analyst as the usual `❌` line. Validation previously existed only on read, which meant a wrong-shaped write was detected after the good version was already gone.

### Changed
- The flagship version of the project is now in English. The Russian version is kept on the `ru` branch.

### Removed
- PDF export (`export_pdf.py`) and the `reportlab` dependency. Artifacts are produced as Markdown; convert them to PDF with a tool of your choice (for example `pandoc` or a Markdown editor's "Print to PDF").

---

## [1.0.0-beta] — 2026-04-07

> [!IMPORTANT]
> **Статус: Public Beta.** Первый публичный релиз для открытого тестирования. 
> Мы активно проверяем логику инструментов в реальных боевых условиях. 

### Добавлено

**Архитектура платформы**
- Система фаз BABOK: `planning`, `elicitation`, `lifecycle`, `analysis`, `design`, `full`
- Переключатель фаз `phase.py` с отображением экономии токенов
- SessionStart и PostToolUse хуки для автоматического контекста и уведомлений об артефактах
- Rules для Claude Code: `artifacts.md`, `babok_process.md`
- Утилита экспорта в PDF `export_pdf.py`
- Интеграция с Confluence Cloud и Server/Data Center

**21 скилл и 22 MCP-сервера (111 инструментов)**

| Глава | Скилл / MCP-сервер |
|-------|-------------------|
| 3 | Планирование бизнес-анализа (`planning_mcp.py`) |
| 4.1 | Подготовка к выявлению (`elicitation_mcp.py`) |
| 4.2 | Проведение выявления (`elicitation_conduct_mcp.py`) |
| 4.3 | Подтверждение результатов (`elicitation_confirm_mcp.py`) |
| 4.4 | Коммуникация результатов (`elicitation_communicate_mcp.py`) |
| 4.5 | Управление сотрудничеством (`elicitation_collaborate_mcp.py`) |
| 5.1 | Трассировка требований (`requirements_traceability_mcp.py`) |
| 5.2 | Поддержка требований (`requirements_maintain_mcp.py`) |
| 5.3 | Приоритизация требований (`requirements_prioritize_mcp.py`) |
| 5.4 | Оценка изменений — CR (`requirements_assess_changes_mcp.py`) |
| 5.5 | Утверждение требований (`requirements_approve_mcp.py`) |
| 6.1 | Анализ текущего состояния (`current_state_mcp.py`) |
| 6.2 | Определение будущего состояния (`future_state_mcp.py`) |
| 6.3 | Оценка рисков (`risk_assessment_mcp.py`) |
| 6.4 | Стратегия изменения (`change_strategy_mcp.py`) |
| 7.1 | Спецификация требований (`requirements_spec_mcp.py`) |
| 7.2 | Верификация требований (`requirements_verify_mcp.py`) |
| 7.3 | Валидация требований (`requirements_validate_mcp.py`) |
| 7.4 | Архитектура требований (`requirements_architecture_mcp.py`) |
| 7.5 | Варианты дизайна (`design_options_mcp.py`) |
| 7.6 | Оценка ценности и рекомендация (`value_recommend_mcp.py`) |

**Документация**
- Пользовательское руководство по всем главам BABOK (`docs/user-guide/`)
- Сценарии использования платформы (`docs/use-cases/use-cases.md`)
- Руководство разработчика (`docs/developer-guide/developer-guide.md`)

**Тестовое покрытие**
- 1 556 тестов по 24 файлам — 100% зелёных
- Полное покрытие всех 21 MCP-сервера
- Интеграционные pipeline-тесты для каждой главы BABOK

**Лицензирование**
- GNU AGPL v3 для открытого использования
- Коммерческая лицензия для SaaS и проприетарных интеграций (`COMMERCIAL_LICENSE.md`)
- Contributor License Agreement (`CLA.md`)

---

## Как читать этот файл

Каждый релиз содержит секции:

- **Добавлено** — новые возможности
- **Изменено** — изменения в существующей функциональности
- **Исправлено** — исправления ошибок
- **Удалено** — удалённые возможности
- **Устарело** — возможности, которые будут удалены в следующих версиях
- **Безопасность** — исправления уязвимостей

---

[1.0.0]: https://github.com/chaussky/ainalyst/releases/tag/v1.0.0
