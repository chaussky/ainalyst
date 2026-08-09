---
name: requirements_prioritize
description: >
  BABOK 5.3 skill — Prioritize Requirements. Use this skill when the BA wants to
  rank requirements using MoSCoW, WSJF, Impact/Effort or Time Boxing/Budgeting,
  resolve conflicts between stakeholders, or justify the implementation order.
  Triggers: "prioritization", "prioritize requirements", "MoSCoW", "WSJF",
  "what to do first", "priority conflict", "requirement importance", "backlog",
  "time boxing", "fixed budget", "what fits in the sprint".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: BABOK 5.3 — Prioritize Requirements
**Задача:** приоритизация требований и дизайнов — определение их относительной важности для стейкхолдеров.
**MCP-сервер:** `requirements_prioritize_mcp.py`
**References:** `references/methods_guide.md`, `references/conflict_resolution.md`

---

## Суть задачи

5.3 — не разовое мероприятие, а **непрерывный процесс**. Приоритеты живут вместе с проектом.

**Что делает BA в 5.3:**
- Выбирает метод приоритизации под контекст проекта
- Собирает оценки стейкхолдеров (у каждого свой взгляд на ценность)
- Агрегирует оценки, выявляет конфликты и dependency violations
- Фасилитирует разрешение конфликтов
- Фиксирует итоговые приоритеты в репозитории

**Что 5.3 НЕ делает:**
- Не создаёт новые требования (это 4.2/4.3)
- Не формально согласовывает требования со стейкхолдерами (это 5.5)
- Не оценивает изменения/CR (это 5.4)
- Не принимает решения за стейкхолдеров — только помогает BA структурировать процесс

**Выход 5.3:** приоритизированные требования → уходят в **6.3 (Оценка рисков)**.

---

## Входы из других задач

| Задача | Что даёт |
|--------|----------|
| **5.1** | Граф зависимостей → автоматическая проверка dependency violations |
| **5.2** | Стабильность требований → нестабильные флагируются как рискованные для высокого приоритета |
| **4.2** | Реестр стейкхолдеров → influence-веса для агрегации, список участников сессии |
| **4.3** | Подтверждённые требования → список для приоритизации |
| **3.2** | Governance rules → кто принимает финальное решение по конфликтам |

---

## Когда активируется этот скилл

- Перед планированием спринта/релиза — нужно определить что войдёт
- После завершения выявления (4.3) — первичная приоритизация
- После получения оценок от разработчиков — пересмотр с учётом стоимости
- После Change Request (5.4) — пересмотр затронутых требований
- При изменении бизнес-контекста — полная переоценка
- Регулярно (раз в спринт/этап) — поддержание актуальности приоритетов

---

## Four methods — quick cheat sheet

### MoSCoW
`Must` / `Should` / `Could` / `Won't` — категориальная расстановка.
Быстро, понятно стейкхолдерам. Не учитывает стоимость и time criticality.
Подробнее: `references/methods_guide.md` → «Метод 1»

### WSJF (Weighted Shortest Job First)
`WSJF = (BV + TC + RR) ÷ Job Size` — числовое ранжирование.
Объективно, учитывает время и риски. Требует оценок от разработчиков.
Подробнее: `references/methods_guide.md` → «Метод 2»

### Impact/Effort Matrix
Два критерия: ценность vs усилия → 4 квадранта → настраиваемый маппинг в приоритет.
Визуально, хорошо для воркшопов. Маппинг настраивает BA под проект.
Подробнее: `references/methods_guide.md` → «Метод 3»

### Time Boxing / Budgeting
A fixed resource — team throughput for the period, or a fixed budget — decides the
scope. Requirements are filled into the box by value until the capacity runs out;
what does not fit becomes `Won't` (MoSCoW's "won't have **this time**").
Needs a capacity and a cost estimate per requirement. Value is taken from this
session if stakeholders score it, otherwise from the requirement's current priority.
Details: `references/methods_guide.md` → "Method 4"

---

## Пять режимов работы

### Режим A — Открыть сессию приоритизации

**Когда:** начало новой сессии (первичная или повторная приоритизация).

Algorithm:
1. Determine the context: which iteration? which requirement scope?
2. Choose a method (if not already chosen):
   - No cost estimates → MoSCoW or Impact/Effort
   - Estimates available + Agile project → WSJF
   - Fixed deadline or fixed budget, scope must be cut to fit → TimeBoxing
   - Already prioritized and hit Must Inflation → TimeBoxing as a second pass
3. For WSJF: choose a scale (Fibonacci or 1–10) and set a reference requirement
4. For Impact/Effort: configure the quadrant mapping
5. For TimeBoxing: set `capacity` (what the team delivers in the period, or the budget)
   and `capacity_unit` ("story points" / "person-days" / "USD")
5. Call `start_prioritization_session`

Результат: список требований готовых к оценке.
⚠️ Нестабильные требования (stability = Volatile) — помечаются автоматически.
⚠️ Требования из Must-кандидатов с зависимостями — помечаются для проверки.

### Режим B — Собрать оценки стейкхолдеров

**Когда:** после открытия сессии, для каждого стейкхолдера отдельно.

Algorithm:
1. Score with each stakeholder (from the 4.2 registry) individually
2. For MoSCoW: each requirement → Must/Should/Could/Won't
3. For WSJF: score BV, TC, RR for each requirement (JS — from developers)
4. For Impact/Effort: score Impact and Effort for each requirement
5. For TimeBoxing: `cost` for each requirement (from the team, in the capacity unit);
   `value` is optional — omit it and the requirement's current priority is used
6. Call `add_stakeholder_scores` for each stakeholder

> 📌 Важно: BA вызывает `add_stakeholder_scores` по одному разу на стейкхолдера.
> Оценки накапливаются в снапшоте сессии, агрегация — только в Режиме C.

### Режим C — Агрегировать и выявить конфликты

**Когда:** все оценки собраны, готовы к расчёту.

Алгоритм:
1. Вызвать `run_aggregation`
2. Изучить результат:
   - Итоговые приоритеты по каждому требованию
   - 🔴 Конфликты стейкхолдеров — требуют разрешения
   - ⚠️ Dependency violations — логические противоречия
   - 🟡 Нестабильные в высоком приоритете — риск переделок
3. Для каждого конфликта — выбрать тактику (Режим D)
4. Если конфликтов нет — переходить к Режиму E

Справка по тактикам конфликтов: `references/conflict_resolution.md`

> 📌 If >60% of requirements are Must, that's a sign of Must Inflation.
> Recommendation: run a follow-up session with `method="TimeBoxing"` — set the capacity
> the team can actually deliver, and let the box decide what fits.
> (A TimeBoxing session does not raise this warning itself: there the Must share
> follows the capacity, not stakeholder discipline.)

### Режим D — Разрешить конфликт

**Когда:** после агрегации выявлен конфликт.

Алгоритм:
1. Определить тип конфликта:
   - Межстейкхолдерский (расхождение оценок)
   - Dependency violation (Must зависит от Won't)
   - Priority inflation (>60% Must)
2. Применить тактику (см. `references/conflict_resolution.md`)
3. Вызвать `resolve_conflict` — зафиксировать решение и rationale
4. Критические конфликты (Must vs Won't, High/High influence) → связать с Decision Log (4.5)

### Режим E — Зафиксировать результат

**Когда:** все конфликты разрешены, приоритеты согласованы.

Algorithm:
1. Verify that all conflicts are marked resolved
2. Call `save_prioritization_result`
3. The tool:
   - Writes the `priority` field into the 5.1 repository
   - WSJF sessions also write `wsjf_score` onto the node — 5.5 reads it to warn
     when a stakeholder rejects a high-value requirement
   - Saves a snapshot to `{project}_prioritization.json`
   - Generates a Markdown report for stakeholders

---

## MCP-инструменты

| Инструмент | Режим | Что делает |
|------------|-------|-----------|
| `start_prioritization_session` | A | Открыть сессию, выбрать метод, получить список требований |
| `add_stakeholder_scores` | B | Добавить оценки одного стейкхолдера |
| `run_aggregation` | C | Агрегировать оценки, найти конфликты и violations |
| `resolve_conflict` | D | Зафиксировать решение по конфликту |
| `save_prioritization_result` | E | Финализировать, обновить репозиторий 5.1 |

---

## Mapping из 5.2 — стабильность как фактор

Перед сессией инструмент `start_prioritization_session` автоматически проверяет стабильность требований:

| Stability (из 5.2) | Версия | Поведение в 5.3 |
|--------------------|--------|-----------------|
| `Stable` | < 1.3 | Без ограничений |
| `Volatile` | 1.3–1.3 | 🟡 Предупреждение при Must |
| `Volatile` (критично) | ≥ 1.4 | 🔴 Флаг: «высокий риск переделок при Must» |
| `Unknown` | — | 🟡 Рекомендация: уточнить стабильность перед финализацией |

---

## Mapping из 5.1 — зависимости

`run_aggregation` автоматически проверяет dependency violations:

1. Для каждого требования с итоговым приоритетом Must/Should
2. Ищет в репозитории 5.1 все связи типа `depends`
3. Проверяет: все upstream-зависимости имеют приоритет ≥ текущего?
4. Если нет — флагирует как dependency violation

Типы связей, которые проверяются: только `depends`.
Связи `derives`, `satisfies`, `verifies` — не являются dependency violations.

---

## Типичные вопросы BA

**«Стейкхолдер поменял мнение после первой оценки — как обновить?»**
Вызвать `add_stakeholder_scores` повторно для того же стейкхолдера.
Новые оценки заменяют предыдущие в текущей сессии.

**"Do I need to run prioritization for designs too (not just requirements)?"**
Yes — BABOK includes Designs as input information for 5.3. In this platform the design and
model artifacts from 7.1 (use cases, business processes, data dictionaries, ERDs) are already
registered in the 5.1 repository under their own types and are prioritized with the same
scheme. There is no separate `design` node type.

**«Как часто проводить повторную приоритизацию?»**
Правило: при любом из триггеров выше (получены оценки, CR принят, контекст изменился).
Каждая сессия — отдельный снапшот с историей.
