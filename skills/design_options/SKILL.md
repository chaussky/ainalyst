---
name: design_options
description: >
  Скилл BABOK 7.5 — Определение вариантов дизайна. Используй этот скилл когда
  BA переходит от требований к вариантам реализации: выбирает build/buy/hybrid подход,
  оценивает технические альтернативы, описывает компромиссы и готовит рекомендацию.
  Триггеры: «варианты дизайна», «design options», «build vs buy», «варианты реализации»,
  «как реализовать», «технические альтернативы», «solution options».
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL.md — BABOK 7.5 Define Design Options

## Суть задачи

7.5 — момент, когда BA перестаёт быть «регистратором потребностей» и становится
**архитектором решения**. Задача синтезирует всё накопленное в проекте
и переводит требования в конкретные варианты реализации.

По BABOK v3 задача объединила три задачи из v2:
- Determine Solution Approach (BA выбирает Build/Buy/Hybrid)
- Assess Proposed Solution (BA оценивает варианты)
- Allocation Requirements (BA распределяет req по версиям)

**Результат задачи → 7.6 Analyze Value and Recommend Solution**

---

## Входы (все опциональны — graceful degradation)

| Файл | Источник | Что берём |
|------|----------|-----------|
| `{project}_traceability_repo.json` | 5.1 | Граф `depends`-связей для allocation |
| `{project}_prioritization.json` | 5.3 | Приоритеты (Must/Should/Could/Won't) для auto_suggest |
| `{project}_business_context.json` | 7.3 | Бизнес-цели, Future State, ограничения |
| `{project}_architecture.json` | 7.4 | Viewpoints, gaps, coverage matrix |
| `{project}_change_strategy.json` | 6.4 | Тип изменения, скоуп, ограничения |

---

## Pipeline

```
1. set_change_strategy          ← [опционально] зафиксировать стратегию изменения
2. create_design_option × N     ← создать 2-3 варианта (Build / Buy / Hybrid)
3. allocate_requirements        ← распределить req по версиям для каждого варианта
4. compare_design_options       ← сравнить варианты по критериям
5. save_design_options_report   ← финальный документ → 7.6
```

---

## MCP-инструменты

### 1. `set_change_strategy`
**Когда:** в начале работы над 7.5, если Change Strategy ещё не зафиксирована.
**Поля:** `change_type` (technology/process/organizational/hybrid), `scope`, `constraints`, `timeline`
**Результат:** `{project}_change_strategy.json`

---

### 2. `create_design_option`
**Когда:** для каждого варианта решения (обычно 2–3 варианта).
**Идемпотентен:** повторный вызов с тем же `option_id` обновляет вариант.

**Подходы:**
- `build` — разработка с нуля
- `buy` — готовое решение / SaaS
- `hybrid` — комбинация

**Ключевые поля:**
- `components_json` — список компонентов решения: `'["Backend API", "Web UI", "БД"]'`
- `improvement_opportunities_json` — массив возможностей улучшения:
  `'[{"type": "efficiency", "description": "Автоматическое формирование отчётов"}]'`
  Типы: `efficiency` / `information_access` / `new_capability`
- `effectiveness_measures_json` — метрики успеха: `'["Снижение времени обработки на 40%"]'`
- `vendor_notes` — для подходов buy/hybrid: оценка вендора, стоимость, ограничения

**Справочник:** `references/design_options_guide.md` — подробнее о подходах и типах возможностей

---

### 3. `allocate_requirements`
**Когда:** после создания вариантов дизайна, для каждого варианта.
**Что делает:** распределяет req по версиям v1 / v2 / out_of_scope.

**Режим auto_suggest=True (рекомендуется):**
- Читает приоритеты из репозитория 5.1 (поле `priority` в req)
- Must → v1, Should → v1/v2, Could → v2, Won't → out_of_scope
- Выдаёт предложение — BA подтверждает или переопределяет

**Ручное переопределение через assignments_json:**
```json
[
  {"req_id": "FR-001", "version": "v1", "rationale": "Критично для MVP"},
  {"req_id": "FR-010", "version": "out_of_scope", "rationale": "Не входит в проект"}
]
```

**Проверка depends-конфликтов:**
После утверждения — автоматически проверяет граф 5.1.
Если req A (v1) зависит от req B (v2) → предупреждение с предложением исправить.

---

### 4. `compare_design_options`
**Когда:** после создания и allocation всех вариантов.
**Что делает:** строит сравнительную матрицу по критериям.

Дефолтные критерии: стоимость, скорость, риски, покрытие требований, гибкость.
Кастомные критерии передаются через `criteria_json`.

**Результат:** Comparison Document для стейкхолдеров → 4.4

---

### 5. `save_design_options_report`
**Когда:** финальный шаг — все варианты описаны и сравнены.
**Что включает:** все варианты + allocation map + improvement opportunities + рекомендация BA.

Параметр `recommended_option_id` — опциональный: BA может дать предварительный вывод,
но финальная рекомендация решения — в задаче 7.6.

**Результат:** Design Options Report сохраняется через `save_artifact` (префикс `7_5_design_options`) → 7.6

---

## Типичный сценарий работы

**Контекст:** проект «CRM-система», 45 требований в репозитории 5.1, приоритизация выполнена в 5.3.

1. Зафиксируй стратегию изменения:
   - `set_change_strategy(project_id="crm", change_type="technology", scope="Замена legacy CRM", constraints="Бюджет $200k, срок 12 месяцев")`

2. Создай 3 варианта:
   - OPT-001 Build: собственная разработка
   - OPT-002 Buy: Salesforce
   - OPT-003 Hybrid: open-source CRM + кастомные модули

3. Для каждого варианта запусти allocation:
   - `allocate_requirements(project_id="crm", option_id="OPT-001", auto_suggest=True)`
   - Проверь предложение, передай переопределения если нужно

4. Сравни варианты:
   - `compare_design_options(project_id="crm")`

5. Сохрани финальный отчёт:
   - `save_design_options_report(project_id="crm", recommended_option_id="OPT-003", notes="Hybrid оптимален по соотношению цена/покрытие")`

---

## Артефакты задачи

| Файл | Формат | Назначение |
|------|--------|-----------|
| `{project}_design_options.json` | JSON | Варианты + allocation (основной файл) |
| `{project}_change_strategy.json` | JSON | Суррогат 6.4 |
| `7_5_design_options_*.md` | Markdown | Design Options Report → 7.6 |

---

## Справочные материалы

> Читай `references/design_options_guide.md` если нужно:
> - Подробнее о подходах Build/Buy/Hybrid
> - Типы Improvement Opportunities по BABOK
> - Критерии сравнения и их веса
> - Паттерны allocation
> - Vendor Assessment
