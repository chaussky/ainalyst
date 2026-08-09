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

Читай этот скилл когда:
- Требования верифицированы (прошли 7.2 `mark_req_verified`) и готовы к формальному
  согласованию. Это сообщается, а не навязывается: `prepare_approval_package`
  предупреждает о неверифицированных требованиях, а `create_requirements_baseline`
  записывает их в Approval Record, но ни один из них не блокирует — решение остаётся за BA
- Нужно согласование стейкхолдеров перед передачей в разработку
- Нужно создать официальный Requirements Baseline
- Стейкхолдер дал условное согласование, и условие нужно закрыть
- Нужно проверить готовность пакета требований к baseline

---

## Входная информация

| Источник | Что берём |
|----------|-----------|
| 7.2 (Verify Requirements) | Свидетельства верификации (`req_verified` в истории репозитория) |
| 4.3 (Confirm Elicitation) | Подтверждённые результаты выявления (контекст) |
| 5.1 (Trace Requirements) | Матрица трассировки, статусы требований |
| 5.2 (Maintain Requirements) | Версии, история изменений, стабильность |
| 5.3 (Prioritize Requirements) | Приоритеты: Must/Should/Could/Won't, WSJF |
| 5.4 (Assess Changes) | CR Decision Records, требования в статусе under_change |
| 3.2 / 4.2 | Реестр стейкхолдеров: роли, полномочия, влияние |

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
**Когда:** перед началом сессии согласования. Собирает пакет требований для стейкхолдеров.

**Что делает:**
- Достаёт требования из репозитория 5.1 по req_ids или по пакету
- Читает формулировку и критерии приёмки каждого требования из его spec-файла 7.1
  (в узле графа лежат только метаданные) — стейкхолдер подписывает читаемый текст
- Добавляет матрицу трассировки, приоритеты (5.3), CR Decision Records (5.4)
- Формирует Markdown-документ под конкретную аудиторию

**Parameters:**
- `project_name` — название проекта
- `package_id` — уникальный ID пакета (APKG-001)
- `req_ids_json` — JSON-список ID требований для пакета
- `approach` — `predictive` или `agile`. Здесь параметр выбирает **церемонию**
  согласования: формальное меню решений по каждому требованию со сроком ответа либо
  формулировки Sprint Planning. **Можно не указывать**: тогда значение выводится из
  плана BA (3.1) в таком порядке — (1) регулируемый гибрид (`Hybrid (Agile + compliance
  gates)` или `Hybrid (with strengthened governance)`, оба возникают только при
  `regulatory_need=True`) означает формальное подписание для аудита, поэтому выводится
  `predictive` независимо от каденции; (2) планируемая форма тайминга из
  `plan_ba_activities`; (3) метка рекомендованного подхода. Простой `Hybrid` не выводится
  ни в одно из значений, поэтому там `approach` нужно указать явно либо объявить
  `timing_form` в `plan_ba_activities`.
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
- `project_name`, `package_id` — название проекта и ID пакета
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
- `project_name`, `package_id` — название проекта и ID пакета
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
- `project_name`, `package_id` — название проекта и ID пакета

---

### 5. `create_requirements_baseline`
**Когда:** После того как пакет готов к baseline (check_approval_status = ✅).

**Что делает:**
- Создаёт snapshot пакета в `{project}_approval_history.json`
- Обновляет статус approved требований в репозитории 5.1
- Генерирует Approval Record (Markdown) через save_artifact
- Этот артефакт → 4.4 (коммуникация) и Глава 6 (вход для разработки)

**Параметры:**
- `project_name`, `package_id` — название проекта и ID пакета
- `baseline_version` — версия baseline (например: `v1.0`, `v1.1`, `sprint-5`)
- `decided_by` — кто подтверждает создание baseline (спонсор / PO)
- `force` — `true` чтобы создать baseline даже при наличии предупреждений
  (rejected от Consulted, открытые условия). По умолчанию `false`.

---

## Алгоритм работы BA

### Сценарий 1: Predictive — baseline в конце фазы

1. Получи список требований, верифицированных в 7.2 (`get_verification_report`)
2. **`prepare_approval_package`** — собери пакет, `approach=predictive`, `audience=all`
3. Отправь пакет стейкхолдерам (через 4.4 `prepare_communication_package`)
4. После каждого ответа: **`record_approval_decision`**
5. Если Conditional: согласуй правки, затем **`close_approval_condition`**
6. **`check_approval_status`** — проверь готовность
7. **`create_requirements_baseline`** — зафиксируй baseline v1.0

### Сценарий 2: Agile — Sprint Backlog Baseline

1. Отобрать требования для следующего спринта
2. **`prepare_approval_package`** — `approach=agile`, `sprint_number=N`
3. Sprint Planning: Product Owner рассматривает пакет
4. **`record_approval_decision`** — фиксируем решение PO
5. **`create_requirements_baseline`** — baseline `sprint-N` (базовая версия спринта)

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
| `verified` | Прошло проверки качества (7.2), готово к согласованию |
| `pending_approval` | Отправлено на согласование, ждём ответа |
| `approved` | Официально согласовано, готово к разработке |
| `conditional_approved` | Согласовано с условием (условие открыто) |
| `rejected` | Отклонено, требует доработки или оценки рисков |
| `under_change` | Затронуто CR из 5.4, идёт оценка изменения |

---

## Связь с другими задачами

**Depends on:**
- 3.1 → методология: читается автоматически из формы тайминга `plan_ba_activities`
  (или из рекомендованного подхода), когда `approach` оставлен пустым
- 7.2 → свидетельства верификации (`req_verified` в истории репозитория) — сообщается, не обязательно
- 4.3 → подтверждённые результаты выявления (контекст)
- 5.1 → репозиторий трассировки
- 5.2 → статусы и версии требований
- 5.3 → приоритеты (контекст для анализа конфликтов)
- 5.4 → CR Decision Records (контекст по изменениям)

**Даёт:**
- 4.4 → Approval Record для коммуникации
- Глава 6 → approved требования как вход для разработки решения

---

## Справочные материалы

При необходимости читай:
- `references/approval_guide.md` — полный справочник: роли, статусы, baseline,
  Predictive vs Agile, типичные ошибки
