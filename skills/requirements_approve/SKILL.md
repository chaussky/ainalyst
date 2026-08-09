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

Use this skill when:
- Requirements have been verified (passed 7.2 `mark_req_verified`) and are ready for formal
  sign-off. This is reported, not enforced: `prepare_approval_package` warns about unverified
  requirements and `create_requirements_baseline` records them in the Approval Record, but
  neither blocks — the decision stays with the BA
- Stakeholder approval is needed before handoff to development
- An official Requirements Baseline needs to be created
- A stakeholder issued a conditional approval and the condition needs to be closed
- The readiness of a requirements package for baseline needs to be checked

---

## Входная информация

| Источник | Что берём |
|----------|-----------|
| 7.2 (Verify Requirements) | Verification evidence (`req_verified` in the repository history) |
| 4.3 (Confirm Elicitation) | Confirmed elicitation results (context) |
| 5.1 (Trace Requirements) | Traceability matrix, requirement statuses |
| 5.2 (Maintain Requirements) | Versions, change history, stability |
| 5.3 (Prioritize Requirements) | Priorities: Must/Should/Could/Won't, WSJF |
| 5.4 (Assess Changes) | CR Decision Records, under_change requirements |
| 3.2 / 4.2 | Stakeholder registry: roles, authority, influence |

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
**When:** Before starting an approval session. Assembles a requirements package for stakeholders.

**What it does:**
- Pulls requirements from the 5.1 repository by req_ids or package
- Reads each requirement's statement and acceptance criteria from its 7.1 spec
  file (the graph node holds only metadata) — the stakeholder signs readable text
- Adds the traceability matrix, priorities (5.3), CR Decision Records (5.4)
- Generates a Markdown document tailored to the audience

**Parameters:**
- `project_name` — project name
- `package_id` — unique package ID (APKG-001)
- `req_ids_json` — JSON list of requirement IDs for the package
- `approach` — `predictive` or `agile`. Here it selects the approval **ceremony**: the
  formal per-requirement decision menu with a response deadline, or the Sprint Planning
  wording. **May be omitted**: it then resolves from the 3.1 BA plan in this order —
  (1) a regulated hybrid (`Hybrid (Agile + compliance gates)` or `Hybrid (with
  strengthened governance)`, both produced only when `regulatory_need=True`) means
  formal sign-off for audit, so it resolves to `predictive` whatever its cadence;
  (2) the planned timing form from `plan_ba_activities`; (3) the recommended approach
  label. A plain `Hybrid` resolves to neither value, so there `approach` must be stated
  explicitly, or `plan_ba_activities` must declare a `timing_form`.
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

1. Get the list of requirements verified in 7.2 (`get_verification_report`)
2. **`prepare_approval_package`** — assemble the package, `approach=predictive`, `audience=all`
3. Send the package to stakeholders (via 4.4 `prepare_communication_package`)
4. After each response: **`record_approval_decision`**
5. If Conditional: agree on the changes, then **`close_approval_condition`**
6. **`check_approval_status`** — check readiness
7. **`create_requirements_baseline`** — record baseline v1.0

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
| `verified` | Passed quality checks (7.2), ready for approval |
| `pending_approval` | Sent for approval, awaiting response |
| `approved` | Officially approved, ready for development |
| `conditional_approved` | Approved with a condition (condition open) |
| `rejected` | Rejected, requires rework or risk assessment |
| `under_change` | Affected by a CR from 5.4, change assessment in progress |

---

## Связь с другими задачами

**Depends on:**
- 3.1 → the methodology, read automatically from `plan_ba_activities`' timing form (or the
  recommended approach) when `approach` is left empty
- 7.2 → verification evidence (`req_verified` in the repository history) — reported, not mandatory
- 4.3 → confirmed elicitation results (context)
- 5.1 → traceability repository
- 5.2 → requirement statuses and versions
- 5.3 → priorities (context for conflict analysis)
- 5.4 → CR Decision Records (context on changes)

**Даёт:**
- 4.4 → Approval Record для коммуникации
- Глава 6 → approved требования как вход для разработки решения

---

## Справочные материалы

При необходимости читай:
- `references/approval_guide.md` — полный справочник: роли, статусы, baseline,
  Predictive vs Agile, типичные ошибки
