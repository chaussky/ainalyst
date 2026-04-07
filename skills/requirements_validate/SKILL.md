---
name: requirements_validate
description: >
  Скилл BABOK 7.3 — Валидация требований. Используй этот скилл когда BA хочет
  проверить что требования действительно нужны бизнесу: соответствуют бизнес-целям,
  создают ценность, не противоречат стратегии и приняты стейкхолдерами.
  Триггеры: «валидация требований», «validate requirements», «нужно ли это бизнесу»,
  «соответствие целям», «business value», «правильные ли требования», «acceptance».
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL.md — BABOK 7.3 Validate Requirements

## Суть задачи

**Валидация** отвечает на вопрос: **«Правильные ли требования мы написали?»**

Отличие от верификации (7.2):
- **7.2 Verify** → «Правильно ли написаны требования?» (качество формулировок)
- **7.3 Validate** → «Нужны ли нам эти требования?» (ценность для бизнеса)

Требование может быть идеально сформулировано — атомарным, однозначным, тестируемым — но бесполезным для бизнеса. Валидация ловит именно это.

**Ключевой принцип:** 7.3 — итерационная задача. Она может вызываться несколько раз на разных стадиях проекта, в отличие от 7.2 (разовый прогон).

---

## Три оси валидации (BABOK)

### Ось 1: Ценность
Приносит ли требование выгоду стейкхолдерам?
- Каждое req должно трассироваться к бизнес-цели (BG)
- Orphan req без трассировки — кандидат на удаление или декомпозицию

### Ось 2: Соответствие будущему состоянию
Помогает ли req достичь Future State, описанного в бизнес-контексте?
- `check_business_alignment` проверяет это автоматически (BFS + title-matching)
- Coverage matrix показывает какие BG не покрыты ни одним req

### Ось 3: Предположения и риски
Выявлены ли assumptions, управляются ли связанные риски?
- Каждое спорное допущение должно быть зафиксировано через `log_assumption`
- High-risk assumptions блокируют валидацию (предупреждение в `mark_req_validated`)

---

## Pipeline (шаги по порядку)

```
1. set_business_context        ← один раз в начале валидации
2. check_business_alignment    ← проверить все verified req
3. set_success_criteria        ← [необязательно] для критичных req
4. log_assumption              ← [по мере работы] при выявлении допущений
5. resolve_assumption          ← [по мере работы] после подтверждения/опровержения
6. mark_req_validated          ← перевести verified → validated
7. get_validation_report       ← сводный отчёт
```

---

## Инструменты MCP

### 1. `set_business_context`

**Когда:** один раз в начале работы над валидацией проекта.

```
set_business_context(
  project_id = "crm_upgrade",
  business_goals_json = '[
    {"id":"BG-001","title":"Снизить время обработки заявок","kpi":"с 24ч до 4ч"},
    {"id":"BG-002","title":"Увеличить NPS","kpi":"с 45 до 65"}
  ]',
  future_state = "Операторы обрабатывают заявки в едином окне, автоматизирована приоритизация",
  solution_scope = "Входит: модуль CRM, интеграция с 1С. Не входит: мобильное приложение"
)
```

Данные хранятся в `{project}_business_context.json`. Бизнес-контекст синхронизирован с задачами 6.1/6.2.

---

### 2. `check_business_alignment`

**Когда:** после создания бизнес-контекста, перед `mark_req_validated`.

```
check_business_alignment(project_id = "crm_upgrade")
# Проверяет все verified req

check_business_alignment(
  project_id = "crm_upgrade",
  req_ids = '["US-001", "FR-005", "UC-002"]'
)
# Проверяет конкретные req
```

**Что проверяет:**
- BFS-обход графа 5.1: достижим ли узел типа `business` из req?
- Title-matching с BG из business_context
- Возвращает: aligned / orphan по каждому req
- Coverage matrix: какие BG не покрыты

**Интерпретация:**
- `aligned` (bfs) → трассировка через граф 5.1 — наилучший результат
- `aligned` (title-match) → совпадение по ключевым словам — стоит добавить явную связь в 5.1
- `orphan` → нет ни BFS, ни title-match → требование без бизнес-обоснования

---

### 3. `set_success_criteria`

**Когда:** необязательно — для критичных req где важно измерить результат.

```
set_success_criteria(
  project_id = "crm_upgrade",
  req_id = "FR-001",
  criteria_json = '{
    "baseline": "Время распределения: 45 мин вручную",
    "target": "Время распределения: ≤ 30 сек автоматически",
    "measurement_method": "Среднее время в системе мониторинга за 1 неделю",
    "kpi_ref": "BG-001"
  }'
)
```

**Подсказка:** инструмент автоматически покажет KPI из связанной бизнес-цели как ориентир.

**Связь с 8.1:** данные success_criteria из 7.3 станут входными для Measure Solution Performance.

---

### 4. `log_assumption`

**Когда:** при обнаружении спорного допущения в любой момент работы над валидацией.

```
log_assumption(
  project_id = "crm_upgrade",
  description = "Предполагаем, что операторы готовы перейти на новый интерфейс без длительного обучения",
  req_ids = '["US-005", "US-006"]',
  risk_level = "high",
  assigned_to = "Петрова А."
)
```

**Risk levels:**
- `high` → предупреждение при `mark_req_validated` пока не закрыто
- `medium` → фиксируется, не блокирует
- `low` → низкий риск, информационная запись

---

### 5. `resolve_assumption`

**Когда:** после подтверждения или опровержения допущения (интервью, тест, исследование).

```
resolve_assumption(
  project_id = "crm_upgrade",
  assumption_id = "AS-001",
  resolution = "confirmed",
  resolution_note = "Проведён пилот с 3 операторами — переход прошёл без проблем за 2 часа"
)

resolve_assumption(
  project_id = "crm_upgrade",
  assumption_id = "AS-002",
  resolution = "refuted",
  resolution_note = "Интеграция с legacy-системой невозможна без миграции данных"
)
```

**При `refuted`:** инструмент выдаёт список связанных req для пересмотра. Возможно нужен новый раунд выявления (4.1–4.3).

---

### 6. `mark_req_validated`

**Когда:** req готов — verified, нет high-risk assumptions, есть трассировка к BG.

```
mark_req_validated(
  project_id = "crm_upgrade",
  req_ids = '["US-001", "FR-001", "FR-002"]'
)

# Override при наличии предупреждений:
mark_req_validated(
  project_id = "crm_upgrade",
  req_ids = '["US-007"]',
  force = True
)
```

**Три предусловия (ADR-033) — предупреждения, не блокировки:**
1. Статус req = `verified` (из 7.2)
2. Нет open high-risk assumptions по этому req
3. Есть трассировка к бизнес-цели

**Lifecycle:** `draft → verified (7.2) → validated (7.3)`

---

### 7. `get_validation_report`

**Когда:** в конце работы над валидацией, для передачи в 7.5.

```
get_validation_report(project_id = "crm_upgrade")
```

**Что содержит:**
- % validated из общего числа req
- Coverage matrix (BG → req)
- Список orphan req без трассировки
- Открытые assumptions по risk_level
- % req с success_criteria
- Вердикт готовности к 7.5

---

## Типичный рабочий сценарий

### Начало проекта
1. Верифицируй требования (7.2)
2. Вызови `set_business_context` — введи бизнес-цели от заказчика

### Основная работа
3. `check_business_alignment` — найди orphan req и пробелы в BG
4. Для orphan req: добавь трассировку через 5.1 (`add_trace_link`) или исключи req
5. `log_assumption` — зафиксируй спорные допущения при обнаружении
6. Проверяй допущения в работе: интервью, пилот, анализ → `resolve_assumption`

### Финализация
7. `mark_req_validated` для готовых req
8. `get_validation_report` → отчёт для передачи в 7.5

---

## Файлы, которые создаёт задача 7.3

| Файл | Содержит |
|------|----------|
| `{project}_business_context.json` | Бизнес-цели, Future State, скоуп |
| `{project}_assumptions.json` | Реестр предположений AS-001/AS-002/... |
| `{project}_traceability_repo.json` | Обновлённые статусы validated в 5.1 |
| `7_3_business_alignment_*.md` | Отчёт по выравниванию |
| `7_3_validation_report_*.md` | Финальный отчёт → 7.5 |

---

## Связи с другими задачами

| Откуда | Что приходит |
|--------|-------------|
| 5.1 | Граф трассировки — BFS-обход для check_business_alignment |
| 7.2 | Статус `verified` — предусловие для mark_req_validated |

| Куда | Что передаём |
|------|-------------|
| 7.5 | Validation Report — основа для Design Options |
| 8.1 | success_criteria из 7.3 — для измерения результата |

---

## Детальная методология и техники

- Три оси валидации, техники BABOK, паттерны ошибок →
  `references/validation_guide.md`

- Работа с предположениями, классификация рисков, паттерны assumptions в IT →
  `references/assumptions_guide.md`
