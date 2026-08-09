---
name: requirements_architecture
description: >
  Скилл BABOK 7.4 — Определение архитектуры требований. Используй этот скилл когда
  BA хочет выстроить целостную картину из разрозненных требований: определить слои
  архитектуры, задать представления (views), связать требования с компонентами системы.
  Триггеры: «архитектура требований», «requirements architecture», «слои требований»,
  «структура требований», «views», «как организовать требования», «requirements structure».
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL.md — BABOK 7.4 Define Requirements Architecture

## Суть задачи

**Архитектура требований** отвечает на вопрос: **«Как наши требования образуют целостную картину?»**

Место в цепочке:
- **7.1 Specify** → Создаём требования (артефакты: BP, US, FR, BR, DD, ERD)
- **7.2 Verify** → Проверяем качество формулировок
- **7.3 Validate** → Проверяем ценность для бизнеса
- **7.4 Architecture** → **Организуем требования в связную структуру** ← мы здесь
- **7.5 Design Options** → Определяем варианты решения

**Ключевые понятия:**
- **Viewpoint (точка зрения)** — перспектива, с которой стейкхолдер смотрит на систему
- **View (представление)** — подмножество req для конкретного viewpoint

Разные стейкхолдеры видят систему по-разному: заказчик — через процессы, разработчик — через функции,
архитектор данных — через модели данных. 7.4 организует требования так, чтобы каждый видел «своё».

---

## Автоматический маппинг по типам артефактов

Платформа автоматически распределяет req по точкам зрения:

| Тип артефакта | Точка зрения |
|---------------|-------------|
| `business_process` (BP) | Бизнес-процессы |
| `data_dictionary` (DD), `erd` (ERD) | Данные и информация |
| `user_story` (US), `use_case` (UC) | Пользователи и взаимодействие |
| `functional` (FR), `non_functional` (NFR) | Функциональность |
| `business_rule` (BR) | Бизнес-правила |
| `business` (BG-узлы) | Не включается в viewpoints |

---

## Pipeline (шаги по порядку)

```
1. analyze_requirements_architecture  ← automatically builds viewpoints from the 5.1 repository
2. add_custom_viewpoint               ← [optional] add a project-specific viewpoint
3. declare_stakeholder_interest       ← state whose interests each requirement touches
4. check_architecture_gaps            ← find gaps: coverage matrix + semantics
5. save_architecture_snapshot         ← lock in the architecture → hand off to 4.4 and 7.5
```

---

## Инструменты MCP

### 1. `analyze_requirements_architecture`

**Когда:** в начале работы над архитектурой — строит полную картину из репозитория.

```
analyze_requirements_architecture(project_id = "crm_upgrade")
```

**What it does:**
- Reads all requirements from the 5.1 repository (`{project}_traceability_repo.json`)
- Distributes them across viewpoints according to VIEWPOINT_MAP
- Builds a coverage matrix: BG × viewpoints
- Shows custom viewpoints if already added
- Takes into account business_context from 7.3 (BG list)

**Что возвращает:**
- Сводная таблица: viewpoint → количество req → список ID
- Coverage matrix: какие BG покрыты какими точками зрения
- Кастомные viewpoints (если есть)
- Подсказка: какие разрывы стоит проверить

---

### 2. `add_custom_viewpoint`

**Когда:** проект требует дополнительной точки зрения (регуляторные требования, безопасность, миграция).

```
add_custom_viewpoint(
  project_id = "crm_upgrade",
  viewpoint_id = "security",
  label = "Безопасность и доступ",
  description = "Требования к аутентификации, авторизации, шифрованию данных",
  req_ids_json = '["NFR-003", "NFR-007", "FR-015", "BR-002"]',
  stakeholder_roles = "Архитектор безопасности, CISO"
)
```

**Important:** custom viewpoints are defined via `req_ids`, not via types.
"Security" is a cross-cutting slice over FR/NFR/BR — only the BA knows exactly which requirements belong to it.

**Валидация:** инструмент проверяет что все переданные req_ids существуют в репозитории 5.1.

---

### 3. `declare_stakeholder_interest`

**When:** once you know which requirements touch which people — usually right after
`analyze_requirements_architecture`, and again whenever elicitation turns up someone new.

```
declare_stakeholder_interest(
  project_id    = "crm_upgrade",
  stakeholder   = "Ivan Petrov",              # a NAME or a ROLE — both resolve
  req_ids_json  = '["FR-001", "FR-002"]',
  note          = "owns the revenue report these feed"
)
```

**This is the one stakeholder relation you state by hand.** It is deliberately not the
same as two facts the platform already holds:

| Relation | Who writes it | What it means |
|----------|---------------|---------------|
| declared interest | **7.4 — you, with this tool** | this requirement touches their interests |
| `owner` | 7.1 | who is answerable for the WORDING of the requirement |
| RACI | 5.5 | their role in a DECISION on an approval package |

**You do not re-enter the last two.** `check_architecture_gaps` and the Architecture
Document read them directly and say where each tie came from, so a person who owns a
requirement or voted on it in 5.5 already counts as covered.

⚠️ **Ownership is computed on the fly, so handing it over can silently uncover
somebody.** Because 7.4 reads `owner` at check time instead of storing a copy (nothing
here can go stale), a single `update_requirement(new_owner = ...)` in 5.2 can turn the
previous owner into a **new critical gap**: their one recorded tie was the owner field,
and it now points at somebody else. 5.2 warns when it happens. If the previous owner's
interests are still touched, record that here with `declare_stakeholder_interest` — a
declared interest is the one tie the platform keeps.

**Repeat calls MERGE** — a second call never erases what an earlier one recorded. To
withdraw a declaration, call again with `remove = True`. The reply always prints counts
("declared on 2 requirement(s)", "already declared on 1"), so a no-op is visible.

**A stakeholder the registry does not know is still recorded, with a warning** — the
registry is a living document and you may be entering someone you met an hour ago. An
unknown *requirement ID*, by contrast, is refused outright: that vocabulary is the
project's own graph, and a typo there is cheapest to fix at the call.

**A TYPE is refused, a STATUS is not.** The 5.1 graph also holds risks (6.3), business
goals (6.2), change requests (5.4), the 6.4 solution scope and test cases. Those are
**not requirements**, so declaring an interest in one is refused by name — the tool
would otherwise report "declared on 1 requirement(s)" about a risk, count it as
coverage, and print its id in a document whose header says the project has no such
requirement. An **archived** requirement (deprecated / superseded / retired) is a
different matter: it is still a requirement, so the declaration is recorded, with a
warning that the coverage check will not count it as live representation.

**The `note` reaches the reader.** Whatever you write there is printed under the
requirement it belongs to in the Architecture Document — it is the one place a sponsor
can see *why* the interests are touched, in your own words.

---

### 4. `check_architecture_gaps`

**Когда:** после `analyze_requirements_architecture` — найти слабые места.

```
check_architecture_gaps(project_id = "crm_upgrade")
```

**Two levels of checking:**

**Level 1 — Coverage matrix:**
- Stakeholder with no recorded tie to any requirement → `critical`
- Stakeholder reachable only by a word shared with a requirement title → `warning`
- Stakeholder traceable only **outside** the requirements — a risk (6.3), a business goal
  (6.2) or a change request (5.4) carries their name or a word of it → `warning`, and the
  message says which kind of node it found, so the BA knows where to go and look
- Stakeholder whose every recorded tie points at an **archived** requirement
  (deprecated / superseded / retired in 5.2) → `warning`
- Archived requirements leave level 2 entirely: nobody is advised to write a use case
  for a retired requirement, and a live UC whose only BP was deprecated is reported as
  hanging rather than as covered. In the Architecture Document they stay in the
  viewpoint tables, tagged `_(archived)_`, and `Total req` still counts them.
- BG with no viewpoint coverage → `warning`
- Empty viewpoint → `info`
- Registry read but holding nobody identifiable → `info` (nobody was checked, and
  the report says so rather than reporting a clean sheet)

**Level 2 — Semantic gaps (uses the 5.1 graph):**
- UC with no corresponding BP → `warning`
- NFR not linked to an FR → `warning`
- FR with no UC/US → `info`

**How the stakeholder verdict is reached.** Three sources count as evidence:
a declared interest (7.4), being a requirement's `owner` (7.1), and an approval decision
on that requirement (5.5). A shared word with a requirement title is a fourth source,
kept because it is how this check used to work — but it is a coincidence, not a fact, so
it now yields a warning that names its own weakness instead of a critical verdict.

⚠️ **Интерпретация:** уровень 2 зависит от полноты связей в 5.1.
Если BA не добавлял трассировку через 5.1 — много ложных срабатываний. Учитывай это.

---

### 5. `save_architecture_snapshot`

**Когда:** архитектура готова — перед передачей в 4.4 (коммуникация) и 7.5 (дизайн).

```
save_architecture_snapshot(
  project_id = "crm_upgrade",
  version = "v1.0",
  notes = "Первая версия архитектуры требований. Покрыто 5 viewpoints, 2 critical gaps устранены.",
  author = "Иванов А."
)
```

**What it creates:**
- A snapshot in `{project}_architecture.json` (history is not overwritten)
- A Markdown document via `save_artifact` → handed off to 4.4 and 7.5

**The gap block is recomputed at save time, not read back.** The workflow below puts
`declare_stakeholder_interest` between the gap check and the snapshot on purpose, so a
stored block would report gaps you had just resolved — right underneath a concerns
section, computed live, saying the opposite about the same person. That also means a
project which never calls `check_architecture_gaps` still gets a real gap table rather
than a row of zeros.

---

## Типичный рабочий сценарий

### Начало работы
1. Убедись что в 7.1 созданы артефакты разных типов (BP, US, FR и т.д.)
2. Вызови `analyze_requirements_architecture` — получи полную картину

### If the project is standard
3. `declare_stakeholder_interest` — record whose interests each requirement touches
4. `check_architecture_gaps` — find gaps
5. Resolve critical gaps: declare the interests you know (7.4), create missing requirements (7.1), or add traceability (5.1)
6. `save_architecture_snapshot(version="v1.0")` — lock it in

### If the project is regulated (banking, healthcare, government)
3. `add_custom_viewpoint` — add viewpoints "Security", "Audit and Compliance"
4. `declare_stakeholder_interest` — regulators and compliance officers rarely own or approve individual requirements, so their interest usually has to be stated explicitly
5. `check_architecture_gaps` — check, accounting for custom viewpoints
6. `save_architecture_snapshot` — lock it in

### Agile project (iterative work)
- Call `analyze_requirements_architecture` at the end of each sprint
- Declare interests for the requirements the sprint added — the declaration merges, so this is safe to repeat
- Take a snapshot after each significant increment of requirements
- Hand off the Architecture Document to the next sprint's planning

---

## Файлы, которые создаёт задача 7.4

| Файл | Содержит |
|------|----------|
| `{project}_architecture.json` | Viewpoints, views, gaps, snapshot history |
| `{project}_traceability_repo.json` | The `stakeholders` field on requirement nodes — declared interests only (7.4 writes this one field; everything else in the file belongs to chapter 5) |
| `7_4_architecture_*.md` | Architecture Document → 4.4, 7.5 |

---

## Связи с другими задачами

| From | What comes in |
|------|----------------|
| 5.1 | Requirements repository — basis for viewpoint mapping and BFS gap analysis |
| 4.2 | Stakeholder registry — coverage check; the name↔role bridge for declared interests |
| 5.5 | Approval decisions — a vote on a requirement is evidence that it touches the voter |
| 7.1 | Artifact types — automatic mapping to viewpoints; the `owner` field — evidence of interest |
| 7.3 | business_context (BG) — coverage matrix |

| Куда | Что передаём |
|------|-------------|
| 4.4 | Architecture Document — артефакт для коммуникации со стейкхолдерами |
| 7.5 | Architecture Document — входной артефакт для Design Options |

---

## Детальная методология

- Viewpoints, маппинг типов, разрывы, фреймворки, паттерны проблем →
  `references/architecture_guide.md`
