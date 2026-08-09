---
name: planning_prep
description: >
  Скилл BABOK Глава 3 — Планирование и мониторинг бизнес-анализа. Используй этот скилл
  всегда, когда бизнес-аналитик начинает новый проект или инициативу и нужно спланировать
  подход к работе. Триггеры: "как мне подойти к этому проекту", "какую методологию выбрать",
  "кто мои стейкхолдеры", "как организовать работу с требованиями", "планирование БА",
  "governance", "как хранить требования", "оценить эффективность аналитики",
  "начать бизнес-анализ", "спланировать анализ".
  Скилл ведёт BA по пяти задачам Главы 3: подход → стейкхолдеры → governance →
  хранение информации → оценка эффективности.
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---

# BABOK Глава 3 — Планирование и мониторинг бизнес-анализа

Твоя роль — помочь бизнес-аналитику выстроить фундамент работы на проекте:
выбрать подход, определить стейкхолдеров, установить правила принятия решений
и организовать хранение информации. Без этого фундамента остальные задачи BABOK
выполняются хаотично.

Веди пользователя пошагово. Каждая задача — отдельный шаг. Не перегружай вопросами.

---

## Пять задач Главы 3

### Задача 3.1 — Выбор подхода к бизнес-анализу

Помоги BA выбрать методологию работы исходя из контекста проекта.

Задай уточняющие вопросы, если контекст не указан:
- Как часто меняются требования?
- Насколько высока неопределённость в проекте?
- Есть ли строгие регуляторные требования (compliance)?

**Логика выбора:**

| Ситуация | Подход |
| :--- | :--- |
| Требования стабильны, неопределённость низкая | Predictive (Waterfall) |
| Высокая динамика или неопределённость | Adaptive (Agile) |
| Нужен баланс гибкости и контроля | Hybrid |
| Agile + строгий compliance | Hybrid с compliance-gates |

После выбора подхода — предложи сохранить решение через MCP-инструмент `suggest_ba_approach`.

**Optional step 3.1b — plan the BA activities and their timing.** BABOK 3.1 has two more
elements: which BA activities are performed (.3) and when — in specific phases or
iteratively (.4). Offer `plan_ba_activities` after the approach is chosen; leave the
timing form empty to derive it from the approach (Predictive → phases, Adaptive → iterations,
a plain Hybrid does not resolve and the tool asks instead of guessing). It records work
periods (BABOK tasks, deliverables, effort, timing) in the same `ba_plan.json`. Two chapters
then read it automatically: 5.5 `prepare_approval_package` takes the methodology from the
planned timing form instead of asking the BA a second time, and 4.1 `save_elicitation_plan`
names the period that covers elicitation work.

---

### Задача 3.2 — Планирование вовлечения стейкхолдеров

Помоги составить карту стейкхолдеров и выбрать стратегию работы с каждым.

**Важно:** реестр стейкхолдеров — это живой документ. В начале проекта
известны 1–2 человека (обычно спонсор). Каждое интервью добавляет новых.
Реестр никогда не бывает "закрыт" — он растёт на протяжении всего проекта.

Типичная цепочка роста:
```
Спонсор → называет руководителей → те называют экспертов →
эксперты называют смежные отделы → и так далее
```

После каждой сессии выявления реестр обновляется через
`update_stakeholder_registry` (MCP задачи 4.2).

Для каждого стейкхолдера определи:
- Влияние (High / Medium / Low) — способность влиять на проект
- Интерес (High / Medium / Low) — заинтересованность в результате
- Отношение (Champion / Neutral / Blocker)
- Статус охвата: Выявлен / В плане / Не охвачен
- **Частота коммуникации** — как часто получает информацию
- **Триггер коммуникации** — при каком событии обязательно уведомить

**Расписание коммуникаций — шаблон по матрице:**

| Квадрант | Частота | Типичные триггеры |
| :--- | :--- | :--- |
| High influence / High interest | После каждого значимого шага | Любое решение, изменение требований, риски |
| High influence / Low interest | По milestone или по запросу | Только критичные решения и блокеры |
| Low influence / High interest | После сессий выявления с участием | Follow-up после интервью, статус-апдейт |
| Low influence / Low interest | Редко, по необходимости | Только если напрямую затронуты |

Расписание фиксируется в профайле стейкхолдера и используется задачей 4.4
(`check_communication_schedule`) для контроля — кому давно не писали и у кого
сработал триггер.

**Матрица Power/Interest:**

| Влияние ↑ / Интерес → | Low | High |
| :--- | :--- | :--- |
| **High** | Keep Satisfied — информировать о вехах | Manage Closely — вовлекать в каждое решение |
| **Low** | Monitor — общая рассылка | Keep Informed — демо, статус-апдейты |

**Вопросы для расширения реестра** (задавай на каждом интервью):
- "С кем вы согласовываете изменения в этом процессе?"
- "Кто ещё использует результаты этой работы?"
- "Чья работа изменится, если мы реализуем это?"
- "Кто может заблокировать или замедлить проект?"

Используй MCP-инструмент `plan_stakeholder_engagement` для формирования матрицы.

---

### Задача 3.3 — Планирование Governance

Помоги установить правила принятия решений и контроля изменений.

Key questions:
- Who makes the final decisions on requirements?
- How are changes handled — formally (CR + CAB) or flexibly (through the PO)?
- How are conflicts escalated?
- How long do approvers get to respond?
- How will requirements be prioritized, by whom, and against which criteria?

**Шаблон ответа по критичности:**

| Критичность | Контроль изменений | Согласование |
| :--- | :--- | :--- |
| High | Формальный CR → CAB | Sponsor + PO |
| Medium | PO одобряет через Backlog | PO + Lead BA |
| Low | Фиксация в Jira, устно | Lead BA |

The template is a **default**, not a verdict: whatever the BA states explicitly is
recorded as stated, and the plan says which values were declared and which came from
the template.

Use the MCP tool `plan_ba_governance`.

**3.3 is read by Chapter 5 — this is not a reference document:**

| Decision | BABOK element | Who reads it |
|---|---|---|
| Decision makers | .1 | 5.5 `prepare_approval_package` prints them; 5.5 `record_approval_decision` and 5.4 `resolve_cr` cross-check who actually decided |
| Escalation path | .1 | 5.4 `resolve_cr` carries it into the CR Decision Record |
| Response deadline | .4 | 5.5 states it on the approval package |
| Prioritization technique, participants, criteria | .3 | 5.3 cross-checks the session and reconciles participation in the result report |
| Project criticality | .1 | seeds 3.4's traceability level, if the BA does not state one |

Every one of those is a **cross-check or a default — never an override.** 5.3 keeps the
`method` the BA chose even when the plan names another technique (it selects the whole
aggregation algorithm); 5.5 keeps an explicit RACI; a stated traceability level wins
over the seed. The BA is told about the difference and decides.

**Plan roles here; the checks resolve names through the stakeholder registry.** 3.3
records roles ("Product Owner"), while a decision in 5.4 or 5.5 and a scoring session in
5.3 are usually recorded against a person ("John Smith"). The registry that 3.2 seeds
and 4.2 maintains ties the two together, so the person is recognised as the planned
role. With no registry the platform says nothing rather than reporting a name it cannot
match as a governance breach — one more reason to run 3.2 before the Chapter 5 work.

**A plan made before this feature keeps its wording.** If 3.3 was planned in an earlier
version, re-running it preserves the text that is there; the BA Plan marks those values
"carried over from an earlier plan" rather than crediting them to the analyst, because
their origin genuinely cannot be recovered. Re-state any field to make it yours.

Re-running 3.3 MERGES, same as 3.4: an omitted parameter keeps its previous value,
`"[]"` clears a list and `"-"` clears a text field. `project_criticality` is required
only the first time.

Nothing here is required either: with no 3.3 plan, 5.3, 5.4 and 5.5 behave exactly as
they did before and say nothing about a plan.

---

### Задача 3.4 — Управление информацией

Помоги спланировать где и как хранятся требования и артефакты.

Вопросы для обсуждения:
- Какие инструменты уже используются в команде?
- Нужна ли трассировка требований и насколько детальная?
- Кто имеет доступ к артефактам — только BA или вся команда?

**Уровни трассировки:**

| Уровень | Что означает |
| :--- | :--- |
| High | Бизнес-цели → FR → Тест-кейсы → Код |
| Medium | FR связаны с задачами Jira |
| Low | Базовая нумерация требований |

Используй MCP-инструмент `plan_information_management`.

**3.4 also plans three things other chapters then act on:**

| Decision | BABOK element | Who reads it |
|---|---|---|
| Level of detail per audience | .2 | 4.4 `prepare_communication_package` |
| Reuse scope + repository + categories | .4 | 5.2 `find_reusable_requirements` |
| Attribute set (Minimum / Standard / Full) | .6 | 5.2 `check_requirements_health` |

Re-running 3.4 MERGES: an omitted parameter keeps its previous value. Clear a list
with `"[]"`, a text field with `"-"`, an enum with `"None"` — with two exceptions:
`storage_tools_json` can never be cleared (a plan with nowhere to store anything is an
unfinished task, not an empty field), and clearing `access_rules` restores its standing
default instead of emptying it. Clearing `attributes_preset` leaves any
`additional_attributes_json` in force, so clear both if the project should fall back to
the platform default.

Nothing here is required: with no 3.4 plan, 4.4 reads nothing new and 5.2 falls back to
`initiative` for reuse and to the single `owner` check for health.

The reuse scope **ranks** — a requirement at or above the target scores one point more.
It does not hide anything below the target; most requirements are never tagged with a
scope, and filtering would empty the report.

---

### Задача 3.5 — Оценка эффективности БА

Помоги выявить проблемы в текущей практике и предложи улучшения.

Признаки проблем, на которые стоит обратить внимание:
- Требования часто меняются уже в разработке
- Разработчики жалуются на непонятные или противоречивые требования
- Нет единого места хранения требований
- Onboarding новых BA занимает больше месяца
- Нет метрик качества требований

Используй MCP-инструмент `evaluate_ba_performance` для формирования плана улучшений.

---

## Когда использовать MCP-инструменты

Все пять задач поддержаны MCP-сервером (`skills/planning_mcp.py`). Вызывай инструменты
когда нужно сохранить артефакт или получить структурированный вывод:

| Задача | MCP-инструмент |
| :--- | :--- |
| 3.1 Plan approach | `suggest_ba_approach` |
| 3.1b Plan BA activities and timing (optional) | `plan_ba_activities` |
| 3.2 Stakeholders | `plan_stakeholder_engagement` |
| 3.3 Governance | `plan_ba_governance` |
| 3.4 Хранение информации | `plan_information_management` |
| 3.5 Оценка эффективности | `evaluate_ba_performance` |
| Финализация | `save_ba_plan` |

All tools take `project_id` as the first parameter. Artifacts are saved to
`governance_plans/data/<project_id>/<project_id>_ba_plan.json` and
`governance_plans/reports/<project_id>/` — one folder per project.
