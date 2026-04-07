---
name: requirements_approve
description: >
  Скилл BABOK 5.5 — Утверждение требований. Используй этот скилл когда требования
  верифицированы и готовы к официальному согласованию стейкхолдерами, нужно создать
  Requirements Baseline, получить подпись/одобрение или закрыть условное одобрение.
  Триггеры: «утверждение требований», «approve requirements», «baseline», «согласование»,
  «одобрение стейкхолдеров», «подписать требования», «requirements sign-off».
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: BABOK 5.5 — Approve Requirements

## Когда использовать этот скилл

Используй этот скилл когда:
- Требования верифицированы (прошли 4.3) и готовы к официальному согласованию
- Нужно получить одобрение стейкхолдеров перед передачей в разработку
- Нужно создать official Requirements Baseline
- Стейкхолдер выставил условное одобрение и нужно закрыть условие
- Нужно проверить готовность пакета требований к baseline

---

## Входная информация

| Источник | Что берём |
|----------|-----------|
| 4.3 (Confirm Elicitation) | Верифицированные требования |
| 5.1 (Trace Requirements) | Матрица трассировки, статусы требований |
| 5.2 (Maintain Requirements) | Версии, история изменений, stability |
| 5.3 (Prioritize Requirements) | Приоритеты: Must/Should/Could/Won't, WSJF |
| 5.4 (Assess Changes) | CR Decision Records, under_change требования |
| 3.2 / 4.2 | Реестр стейкхолдеров: роли, authority, influence |

---

## Pipeline задачи

```
prepare_approval_package → record_approval_decision (×N стейкхолдеров)
  → [close_approval_condition (при Conditional)]
  → check_approval_status
  → create_requirements_baseline
```

---

## Инструменты MCP

### 1. `prepare_approval_package`
**Когда:** Перед началом сессии согласования. Собирает пакет требований для стейкхолдеров.

**Что делает:**
- Берёт требования из репозитория 5.1 по req_ids или пакету
- Добавляет матрицу трассировки, приоритеты (5.3), CR Decision Records (5.4)
- Формирует Markdown-документ, адаптированный под аудиторию

**Параметры:**
- `project_name` — название проекта
- `package_id` — уникальный ID пакета (APKG-001)
- `req_ids_json` — JSON-список ID требований для пакета
- `approach` — `predictive` или `agile`
- `audience` — `business` / `developer` / `regulator` / `all`
- `package_title` — название пакета (например: «Фича: Онбординг пользователей»)
- `sprint_number` — номер спринта (только для agile)

---

### 2. `record_approval_decision`
**Когда:** После получения ответа от каждого стейкхолдера.
Вызывается по одному разу на каждого стейкхолдера (аналог add_stakeholder_scores в 5.3).

**Что делает:**
- Фиксирует решение: `approved` / `conditional` / `rejected` / `abstained`
- При `conditional` — записывает условие, дедлайн, ответственного
- При `rejected` — анализирует контекст из 5.3/5.4 и флагует конфликты
- Обновляет статус требований в репозитории 5.1

**Параметры:**
- `project_name`, `package_id`
- `stakeholder_name` — имя стейкхолдера
- `stakeholder_raci` — `accountable` / `responsible` / `consulted`
- `decision` — `approved` / `conditional` / `rejected` / `abstained`
- `req_decisions_json` — JSON: решения по отдельным требованиям пакета.
  Формат: `[{"req_id": "FR-001", "decision": "approved"}, {"req_id": "FR-002", "decision": "conditional", "condition_text": "...", "condition_deadline": "2026-04-01", "condition_owner": "Иванов"}]`
  Если пусто (`[]`) — решение применяется ко всем требованиям пакета целиком.
- `rejection_reason` — обязательно при decision=rejected
- `comment` — любой комментарий стейкхолдера

---

### 3. `close_approval_condition`
**Когда:** После выполнения условия по Conditional-одобрению.

**Что делает:**
- Находит открытое условие по пакету, требованию и стейкхолдеру
- Фиксирует что условие выполнено (с датой и описанием)
- Обновляет статус требования на `approved`

**Параметры:**
- `project_name`, `package_id`
- `req_id` — требование с условием
- `stakeholder_name` — кто выставил условие
- `resolution_notes` — как условие было закрыто

---

### 4. `check_approval_status`
**Когда:** В любой момент для проверки готовности пакета к baseline.

**Что делает:**
- Считает статистику: approved / conditional / rejected / pending / abstained
- Выявляет просроченные conditional и стейкхолдеров без ответа
- Флагует rejected от Accountable-стейкхолдеров (блокеры)
- Даёт вердикт: готов / не готов к baseline, с причинами

**Параметры:**
- `project_name`, `package_id`

---

### 5. `create_requirements_baseline`
**Когда:** После того как пакет готов к baseline (check_approval_status = ✅).

**Что делает:**
- Создаёт snapshot пакета в `{project}_approval_history.json`
- Обновляет статус approved требований в репозитории 5.1
- Генерирует Approval Record (Markdown) через save_artifact
- Этот артефакт → 4.4 (коммуникация) и Глава 6 (вход для разработки)

**Параметры:**
- `project_name`, `package_id`
- `baseline_version` — версия baseline (например: `v1.0`, `v1.1`, `sprint-5`)
- `decided_by` — кто подтверждает создание baseline (спонсор / PO)
- `force` — `true` чтобы создать baseline даже при наличии предупреждений
  (rejected от Consulted, открытые условия). По умолчанию `false`.

---

## Алгоритм работы BA

### Сценарий 1: Predictive — baseline в конце фазы

1. Получить список verified требований из 4.3
2. **`prepare_approval_package`** — собрать пакет, `approach=predictive`, `audience=all`
3. Разослать пакет стейкхолдерам (через 4.4 `prepare_communication_package`)
4. После ответа каждого: **`record_approval_decision`**
5. Если Conditional: согласовать изменения, затем **`close_approval_condition`**
6. **`check_approval_status`** — проверить готовность
7. **`create_requirements_baseline`** — зафиксировать baseline v1.0

### Сценарий 2: Agile — Sprint Backlog Baseline

1. Отобрать требования для следующего спринта
2. **`prepare_approval_package`** — `approach=agile`, `sprint_number=N`
3. Sprint Planning: Product Owner рассматривает пакет
4. **`record_approval_decision`** — фиксируем решение PO
5. **`create_requirements_baseline`** — baseline `sprint-N`

### Сценарий 3: Конфликт на этапе согласования

1. **`record_approval_decision`** — стейкхолдер отклонил требование
2. Система автоматически показывает конфликт с 5.3 / 5.4
3. BA анализирует: это Accountable или Consulted стейкхолдер?
   - Consulted: документируем риск, baseline возможен
   - Accountable: нужно разрешить конфликт перед baseline
4. Если нужно изменить требование → 5.2 `update_requirement`, потом повтор с шага 2
5. Если нужен новый CR → 5.4 `open_cr`, затем повтор согласования

---

## Статусы требований в репозитории 5.1

| Статус | Значение |
|--------|----------|
| `verified` | Прошло проверку качества (4.3), готово к согласованию |
| `pending_approval` | Отправлено на согласование, ожидает ответа |
| `approved` | Официально одобрено, готово к разработке |
| `conditional_approved` | Одобрено с условием (условие открыто) |
| `rejected` | Отклонено, требует доработки или risk assessment |
| `under_change` | Затронуто CR из 5.4, идёт оценка изменения |

---

## Связь с другими задачами

**Зависит от:**
- 4.3 → verified требования (обязательный вход)
- 5.1 → репозиторий с трассировкой
- 5.2 → статусы и версии требований
- 5.3 → приоритеты (контекст для анализа конфликтов)
- 5.4 → CR Decision Records (контекст изменений)

**Даёт:**
- 4.4 → Approval Record для коммуникации
- Глава 6 → approved требования как вход для разработки решения

---

## Справочные материалы

При необходимости читай:
- `references/approval_guide.md` — полный справочник: роли, статусы, baseline,
  Predictive vs Agile, типичные ошибки
