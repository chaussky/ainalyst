---
name: requirements_verify
description: >
  Скилл BABOK 7.2 — Верификация требований. Используй этот скилл когда BA хочет
  проверить качество написанных требований: атомарность, однозначность, тестируемость,
  полноту, консистентность. Отличие от валидации: верификация — про качество формулировок,
  не про ценность для бизнеса. Триггеры: «верификация требований», «verify requirements»,
  «качество требований», «requirements quality», «проверить требования», «чеклист».
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL.md — BABOK 7.2 Verify Requirements

## Суть задачи

Верификация требований отвечает на вопрос: **«Правильно ли написаны требования?»**

Отличие от задачи 7.3 (Validate):
- 7.2 Verify: правильно ли *написано* требование? (качество формулировки)
- 7.3 Validate: правильное ли *это* требование? (соответствие бизнес-потребности)

Входные данные: требования из репозитория 5.1 (созданные в 7.1).  
Выходные данные: статус `verified` в 5.1, Verification Report → 5.5 (Approve) и 7.3 (Validate).

---

## 9 характеристик качества BABOK

| Характеристика | Группа | Как проверяем |
|---------------|--------|---------------|
| Атомарность | A | MCP: стоп-слова |
| Однозначность | A | MCP: слова-сигналы |
| Тестируемость | A | MCP: структура + AC |
| Приоритизированность | A | MCP: поле priority в 5.1 |
| Краткость | A | MCP: длина + сигналы |
| Согласованность | B | MCP: статусы + граф 5.1 |
| Полнота | B | MCP: source_artifact + links |
| Выполнимость | C | Чеклист BA (см. references/) |
| Понятность | C | Чеклист BA (см. references/) |

Детали правил — в `references/quality_rules.md`.  
Чеклисты по типам — в `references/checklist_templates.md`.

---

## Pipeline задачи 7.2

```
check_req_quality           → автоматические проверки Группы A+B
  ↓ (если есть проблемы)
open_verification_issue     → фиксируем каждую проблему
  ↓ (BA исправляет требования)
check_model_consistency     → cross-model проверка файлов из 7.1
  ↓ (если есть рассинхрон)
open_verification_issue     → фиксируем model inconsistency
  ↓ (BA исправил)
resolve_verification_issue  → закрываем issue
  ↓
mark_req_verified           → статус draft → verified в 5.1
  ↓
get_verification_report     → сводный отчёт → 5.5 + 7.3
```

---

## Инструменты MCP

### check_req_quality(project_id, req_ids?, req_type?)

Проверяет одно требование, список или все req проекта по 9 характеристикам.

**Умный батч:** если `req_ids` не задан — берёт все `draft` req из репозитория 5.1.  
Если задан `req_type` — фильтрует по типу (user_story / functional / non_functional и т.д.).

**Возвращает:**
- Результаты проверок по каждому req (Группы A+B)
- Список blockers и majors для каждого
- Подсказки для Claude Code: что именно нарушено и как исправить
- Напоминание пройти чеклисты Группы C (Выполнимость + Понятность)

**Паттерн использования:**
```
# Проверить всё
check_req_quality(project_id="my_project")

# Проверить конкретные req
check_req_quality(project_id="my_project", req_ids='["US-001", "FR-001"]')

# Проверить только User Stories
check_req_quality(project_id="my_project", req_type="user_story")
```

---

### check_model_consistency(project_id)

Сравнивает артефакты из 7.1: .md и .puml файлы в `governance_plans/{project}_specs/`.

**Что проверяет:**
- Сущности в DD vs ERD (рассинхрон имён)
- Use Cases vs UC Diagram (UC без актора в диаграмме)
- Участники бизнес-процесса vs акторы в UC Diagram

**Важно:** Парсинг регулярками по шаблонам из 7.1. Работает для стандартного форматирования. Нестандартные форматы — Claude Code интерпретирует предупреждения вручную.

---

### open_verification_issue(project_id, req_id, issue_type, description, severity, assigned_to?)

Фиксирует проблему, найденную при верификации.

**issue_type:** ambiguity / not_testable / not_atomic / missing_ac / model_inconsistency / other  
**severity:** blocker / major / minor

**Когда открывать:**
- После `check_req_quality` — для каждой автоматически найденной проблемы
- После ручной проверки чеклистов Группы C
- После `check_model_consistency` — для рассинхронов моделей

**Присвоение assigned_to:** как правило — тот BA кто создавал требование (владелец).

---

### resolve_verification_issue(project_id, issue_id, resolution_note)

Закрывает issue после того как BA исправил требование.

**resolution_note** — что именно было исправлено (для аудита).

**Важно:** После закрытия всех blocker-issues по req — можно вызывать `mark_req_verified`.

---

### mark_req_verified(project_id, req_ids)

Меняет статус `draft → verified` в репозитории 5.1.

**Предусловие:** MCP проверит наличие открытых blocker-issues по каждому req.  
Если blocker есть — предупреждение, но не блокировка (BA принимает решение).

```
# Верифицировать список
mark_req_verified(project_id="my_project", req_ids='["US-001", "US-002", "FR-001"]')
```

---

### get_verification_report(project_id)

Сводный отчёт по верификации проекта.

**Содержит:**
- % verified из всех req (показатель готовности к 5.5)
- Топ-проблемы по типам характеристик
- Список req с открытыми blocker-issues
- Открытые issues с деталями
- Вердикт: готово ли к Approve (5.5)

Сохраняет Markdown через `save_artifact` — передать в 5.5 и 7.3.

---

## Типичный сценарий работы

**Шаг 1.** Запускаешь проверку всех требований:
```
check_req_quality(project_id="crm_2024")
```
Claude Code читает результат и объясняет каждую проблему понятным языком.

**Шаг 2.** Для критичных проблем открываешь issues:
```
open_verification_issue(
  project_id="crm_2024",
  req_id="US-003",
  issue_type="missing_ac",
  description="User Story не содержит Acceptance Criteria — нет критериев приёмки",
  severity="blocker"
)
```

**Шаг 3.** Исправляешь требование (в файле или через инструмент 7.1). Затем закрываешь issue:
```
resolve_verification_issue(
  project_id="crm_2024",
  issue_id="VI-001",
  resolution_note="Добавлено 3 Acceptance Criteria: успешная авторизация, неверный пароль, блокировка"
)
```

**Шаг 4.** Проверяешь согласованность моделей:
```
check_model_consistency(project_id="crm_2024")
```

**Шаг 5.** Проходишь чеклисты Группы C из `references/checklist_templates.md` — Выполнимость и Понятность для каждого типа требований.

**Шаг 6.** Верифицируешь требования без блокеров:
```
mark_req_verified(project_id="crm_2024", req_ids='["US-001", "US-002", "FR-001"]')
```

**Шаг 7.** Генерируешь отчёт для передачи в 5.5:
```
get_verification_report(project_id="crm_2024")
```

---

## Связь с другими задачами BABOK

**Входящие связи:**
- Репозиторий 5.1 — список req со статусами
- Файлы из 7.1 — спецификации в `governance_plans/{project}_specs/`

**Исходящие связи:**
- → 5.5 (Approve Requirements): Verification Report как входной артефакт
- → 7.3 (Validate Requirements): верифицированные req как входные данные

**Важно:** 7.2 и 7.3 можно запускать итеративно и параллельно. Если в процессе валидации (7.3) выясняется что требование сформулировано плохо — возвращайся в 7.2.

---

## Хранение данных

| Что | Где | Формат |
|-----|-----|--------|
| Verification issues | `governance_plans/{project}_verification_issues.json` | JSON |
| Статусы req | Репозиторий 5.1 (`{project}_traceability_repo.json`) | JSON (поле status) |
| Verification Report | `governance_plans/` через save_artifact | Markdown |

---

## Подсказки для Claude Code при интерпретации результатов

**При `ambiguity` (слово-сигнал):**
Объясни BA что конкретно размыто и предложи переформулировку с метрикой.  
Пример: «быстро» → «в течение 2 секунд при нагрузке до 1000 пользователей».

**При `missing_ac`:**
Предложи 2-3 примера AC в формате Given/When/Then или просто нумерованных условий.

**При `not_atomic`:**
Укажи где именно союз делит требование на два. Предложи разбить на req_id_a и req_id_b.

**При `not_testable` (FR без метрики):**
Уточни у BA что является измеримым результатом. Пример: «система сохраняет» → «система сохраняет в течение X секунд с вероятностью Y%».

**При `model_inconsistency`:**
Покажи конкретно: в каком файле что написано и что расходится. BA исправляет в нужном файле.
