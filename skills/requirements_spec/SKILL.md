---
name: requirements_spec
description: >
  Скилл BABOK 7.1 — Спецификация и моделирование требований. Используй этот скилл
  когда BA переводит результаты выявления в формальные спецификации: user stories,
  use cases, бизнес-правила, data definitions, процессные модели (BPMN).
  Триггеры: «спецификация требований», «user story», «use case», «бизнес-правила»,
  «specify requirements», «написать требования», «оформить требования», «BPMN», «модели».
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL.md — BABOK 7.1: Specify and Model Requirements

## Что делает эта задача

Задача 7.1 превращает подтверждённые результаты выявления (4.2/4.3) в формальные
спецификации требований. Вход — «что сказали стейкхолдеры», выход — «требования
в стандартных нотациях с моделями».

Это мост между выявлением (Глава 4) и верификацией/валидацией (7.2, 7.3).

---

## Когда вызывать эти инструменты

Вызывай инструменты 7.1, когда:
- Есть подтверждённые результаты выявления (артефакты 4.3)
- Нужно передать требования разработчикам, архитекторам, тестировщикам
- Нужны трассируемые формальные спецификации
- Надо проверить, что все бизнес-цели из выявления покрыты требованиями

---

## Рекомендуемый порядок работы

### Шаг 1 — Анализ контекста
Начни с `analyze_elicitation_context`. Инструмент прочитает артефакты 4.3
и предложит список требований-кандидатов с классификацией.

```
analyze_elicitation_context(
    project_id="crm_2024",
    context_text=""   # оставить пустым — инструмент найдёт файл сам
)
```

Если файл 4.3 не найден, инструмент попросит передать текст вручную:
```
analyze_elicitation_context(
    project_id="crm_2024",
    context_text="[скопируй сюда содержимое артефакта 4.3]"
)
```

### Шаг 2 — Создание артефактов
Создавай требования по одному или группами, используя нужный инструмент.
**Каждый созданный артефакт автоматически регистрируется в репозитории 5.1**
со статусом `draft`. Тебе не нужно вручную вызывать инструменты 5.1.

**Link each requirement to the business objective it serves.** Every creating tool takes
`business_goal_ids_json` — the IDs of the 6.2 objectives (`["BG-001", "BG-002"]`). This
writes a `satisfies` link into the 5.1 graph, and it is what makes the coverage matrix in
Step 4 precise instead of a checklist. Ask the BA which objective the requirement serves;
never guess it from the wording. If the ID is unknown the tool warns and creates the
requirement anyway — you can link it later with `add_trace_link` (5.1).

Supporting models (data dictionary, ERD) are usually left unlinked — they describe the
solution rather than serve an objective directly.

How to choose the artifact type → see `references/modeling_guide.md`.
Templates for each artifact → see `references/templates.md`.

### Шаг 3 — Диаграммы (по необходимости)
- После создания Use Cases → вызови `generate_use_case_diagram` для сводной диаграммы
- Business Process создаёт `.puml` файл Activity Diagram автоматически
- ERD создаёт `.puml` файл автоматически

### Step 4 — Coverage check
At the end, call `build_coverage_matrix`. It reads the business objectives from 6.2
(Define Future State: the `business_goal` nodes registered in the 5.1 graph, or
`future_state_goals.json`) and reports, per objective, which requirements serve it.

**Precise coverage requires two things:**
1. objectives defined in 6.2 `define_goals_and_objectives` — that is what puts them in the
   graph as `business_goal` nodes with IDs;
2. requirements linked to them — pass `business_goal_ids_json=["BG-001"]` when creating the
   requirement (see Step 2), or link later with `add_trace_link` (5.1).

Then the report shows:
- 🔴 an objective no requirement serves
- 🟢 normal coverage (1–9 requirements)
- 🟡 10+ requirements on one objective — possible over-engineering, check for duplicates
- requirements not linked to any objective, grouped by type

**If the objectives have no IDs** (they came from `future_state_goals.json`, a legacy
"Business objectives" section in the 4.3 artifact, or grouping by source), no per-objective
claim is made at all: the objectives are shown as a checklist and the report says so. The
tool never guesses which requirement serves which objective from their wording.

For full per-requirement traceability (sources, implementation, tests) run `check_coverage` (5.1).

---

## Инструменты

### `analyze_elicitation_context`
Анализирует подтверждённые результаты выявления и предлагает список требований.

```
analyze_elicitation_context(
    project_id="crm_2024",       # обязательно
    context_text=""              # опционально: текст если файл не найден
)
```

Возвращает:
- Список бизнес-целей из 4.3
- Требования-кандидаты с рекомендуемым типом и ID-префиксом
- Пробелы: темы выявления без конкретных требований

---

### `create_user_story`

```
create_user_story(
    project_id="crm_2024",
    story_id="US-001",
    title="Подать заявку на кредит",
    role="Менеджер по заявкам",
    action="создать новую заявку на кредит с заполнением всех полей",
    benefit="заявка была зарегистрирована и передана на рассмотрение",
    acceptance_criteria_json='["Система сохраняет заявку с уникальным ID", "Система отправляет подтверждение на email менеджера"]',
    priority="High",
    source_artifact="governance_plans/4_3_crm_confirmed.md",
    notes=""
)
```

---

### `create_functional_requirement`

```
create_functional_requirement(
    project_id="crm_2024",
    req_id="FR-001",
    req_type="functional",           # functional | non_functional | business_rule
    title="Автоматическое распределение заявок",
    description="Система ДОЛЖНА автоматически распределять входящие заявки между менеджерами по алгоритму round-robin с учётом текущей загрузки.",
    rationale="Снижает время ожидания клиента, исключает ручной контроль.",
    priority="High",
    owner="Руководитель отдела продаж",
    source_artifact="governance_plans/4_3_crm_confirmed.md",
    constraints="",
    related_ids_json='["BR-001", "UC-001"]'
)
```

**Формулировки по типу:**
- `functional`: «Система ДОЛЖНА [действие]...»
- `non_functional`: «Система ДОЛЖНА обрабатывать не менее [N] запросов в секунду при [условии]»
- `business_rule`: «[Субъект] [ограничение/правило]» — без привязки к системе

---

### `create_use_case`

```
create_use_case(
    project_id="crm_2024",
    uc_id="UC-001",
    title="Рассмотреть заявку на кредит",
    primary_actor="Кредитный аналитик",
    secondary_actors="Служба безопасности, Система скоринга",
    precondition="Заявка имеет статус 'На рассмотрении'",
    postcondition="Заявка получает статус 'Одобрена' или 'Отклонена'",
    trigger="Аналитик открывает заявку в системе",
    main_scenario="1. Аналитик открывает заявку.\n2. Система отображает данные клиента и документы.\n3. Аналитик проверяет скоринговый балл.\n4. Система запрашивает проверку в Службе безопасности.\n5. Аналитик принимает решение.\n6. Система фиксирует решение и меняет статус.",
    alt_scenarios="3а. Скоринговый балл недоступен: Аналитик запрашивает повторный расчёт.",
    exc_scenarios="4а. Служба безопасности не отвечает более 24ч: Система уведомляет руководителя.",
    business_rules="Решение должно быть принято в течение 3 рабочих дней.",
    priority="High",
    source_artifact="governance_plans/4_3_crm_confirmed.md"
)
```

---

### `generate_use_case_diagram`

Генерирует сводную PlantUML Use Case Diagram по **всем** UC проекта из репозитория 5.1.

```
generate_use_case_diagram(
    project_id="crm_2024",
    system_boundary="CRM-система",
    diagram_name="crm_use_cases"
)
```

Результат: файл `{project}_specs/uc_diagram_{diagram_name}.puml`

---

### `create_business_process`

Создаёт **два файла**: текстовое описание `.md` + Activity Diagram `.puml`.

```
create_business_process(
    project_id="crm_2024",
    bp_id="BP-001",
    title="Жизненный цикл заявки",
    process_owner="Руководитель отдела продаж",
    trigger="Клиент обращается за кредитом",
    outcome="Кредит выдан или заявка закрыта с отказом",
    participants="Менеджер, Кредитный аналитик, Служба безопасности",
    steps="1. Менеджер: принять обращение клиента.\n2. Менеджер: создать заявку в CRM.\n3. Система: назначить аналитика.\n4. Аналитик: проверить документы.\n5. ...",
    business_rules="Срок рассмотрения — 3 рабочих дня.",
    metrics="Среднее время: 2 дня. Конверсия в одобрение: 65%.",
    exceptions="Если клиент не предоставил документы в течение 5 дней — автозакрытие.",
    priority="Medium",
    source_artifact="governance_plans/4_3_crm_confirmed.md"
)
```

---

### `create_data_dictionary`

```
create_data_dictionary(
    project_id="crm_2024",
    dd_id="DD-001",
    title="Сущность Заявка (Application)",
    entities_json='[{"name": "Application", "description": "Заявка на кредит", "attributes": [{"name": "id", "type": "Integer", "required": true, "constraints": "PK, AUTO_INCREMENT", "description": "Уникальный идентификатор"}, {"name": "status", "type": "Enum", "required": true, "constraints": "draft|submitted|approved|rejected", "description": "Статус заявки"}], "business_rules": ["Статус меняется только по бизнес-правилам перехода"]}]',
    source_artifact="governance_plans/4_3_crm_confirmed.md"
)
```

---

### `create_erd`

Создаёт **два файла**: описание связей `.md` + ER Diagram `.puml`.

```
create_erd(
    project_id="crm_2024",
    erd_id="ERD-001",
    title="Основные сущности CRM",
    entities_json='[{"name": "Application", "pk": "id", "attributes": ["client_id FK", "manager_id FK", "status Enum", "created_at DateTime"]}, {"name": "Client", "pk": "id", "attributes": ["name String", "inn String UNIQUE"]}]',
    relations_json='[{"from": "Application", "to": "Client", "cardinality": "many-to-one", "label": "belongs to"}]',
    source_artifact="governance_plans/4_3_crm_confirmed.md"
)
```

---

### `build_coverage_matrix`

Reports which requirements serve which business objective. Objectives come from the 6.2
`business_goal` nodes in the 5.1 graph (or `future_state_goals.json`); requirements come from
the 5.1 registry.

```
build_coverage_matrix(
    project_id="crm_2024"
)
```

**Signals (when the objectives are graph nodes):**
- 🔴 objective with no requirement serving it
- 🟢 1–9 requirements
- 🟡 10+ requirements on one objective — possible over-engineering, check for duplicates
- requirements not linked to any objective, grouped by type
- requirements traced to a business need but not to an objective — usually a need 6.2 has
  not refined into objectives yet

Coverage is computed by traversing the `satisfies` links the analyst declares (`derives`
links to an objective count too). **Nothing is inferred from wording** — an objective is
covered only when a requirement is actually linked to its node.

**Without objective IDs** (objectives from `future_state_goals.json`, a legacy "Business
objectives" section in the 4.3 artifact, or grouping by requirement source), no per-objective
claim is made: the objectives are listed as a checklist and the report states why.

Nodes other chapters keep in the same graph — `change_request` (5.4), `risk` (6.3),
`solution` (6.4), `test` (5.1) — are not counted as requirements here.

---

## Хранение артефактов

Все артефакты сохраняются в: `governance_plans/{project_id}_specs/`

```
governance_plans/crm_2024_specs/
├── US-001_submit_application.md
├── FR-001_auto_distribution.md
├── UC-001_review_application.md
├── uc_diagram_crm_use_cases.puml       ← сводная UC Diagram
├── BP-001_application_lifecycle.md
├── BP-001_application_lifecycle.puml   ← Activity Diagram
├── DD-001_application_entity.md
├── ERD-001_core_entities.md
└── ERD-001_core_entities.puml          ← ER Diagram
```

---

## Автоматическая регистрация в 5.1

Каждый созданный артефакт **автоматически** регистрируется в репозитории 5.1
(файл `governance_plans/{project_id}_traceability_repo.json`) со статусом `draft`.

Ты можешь:
- Сразу добавить связи через `add_trace_link` (5.1)
- Изменить статус через `update_requirement` (5.2) когда требование готово к верификации
- Проверить покрытие через `check_coverage` (5.1)

---

## Связи с другими задачами

| Откуда | Что берём |
|--------|-----------|
| 4.2/4.3 | Подтверждённые результаты выявления (вход для `analyze_elicitation_context`) |
| 5.1 | Репозиторий трассировки (7.1 пишет в него автоматически) |

| Куда | Что передаём |
|------|--------------|
| 7.2 | Спецификации требований для верификации |
| 7.3 | Спецификации требований для валидации |
| 5.3 | Список draft-требований для приоритизации |

---

## Справочники

- `references/modeling_guide.md` — как выбрать тип артефакта
- `references/templates.md` — шаблоны каждого артефакта и PlantUML-диаграмм
