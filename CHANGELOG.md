# Changelog — AI Платформа AIналитик (AInalyst)

Все значимые изменения в проекте документируются здесь.  
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/).  
Проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

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
