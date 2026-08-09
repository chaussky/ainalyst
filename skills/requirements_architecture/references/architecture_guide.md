# architecture_guide.md — Архитектура требований (BABOK 7.4)

## Что такое архитектура требований

**Архитектура требований** — это организация требований в связную структуру, где каждое
требование занимает своё место и понятно как оно соотносится с другими.

Это ответ на вопрос: **«Как наши требования образуют цельную картину?»**

BABOK определяет два ключевых понятия:

| Понятие | Определение | Пример |
|---------|-------------|--------|
| **Viewpoint** (точка зрения) | Перспектива, с которой стейкхолдер смотрит на систему | «Бизнес-процессы», «Данные», «Пользователи» |
| **View** (представление) | Конкретное подмножество требований для данной точки зрения | Все BP-артефакты, все FR-артефакты |

**Ключевой принцип:** у разных стейкхолдеров разные интересы. Финансовый директор смотрит на
систему через призму бизнес-процессов и целей, разработчик — через функциональность,
архитектор данных — через информационные объекты. Архитектура требований обеспечивает, чтобы
каждый стейкхолдер видел «свою» часть картины, а BA видел целое.

---

## Five viewpoints (automatic mapping)

The platform automatically organizes requirements into five standard viewpoints based on the
artifact type:

### 1. Business Processes
**Artifacts:** `business_process` (BP)
**Audience:** Business sponsor, process owners
**Question:** How will business processes change?
**Signs of completeness:** Every key business process is described. No Use Case lacks a corresponding BP.

### 2. Data and Information
**Artifacts:** `data_dictionary` (DD), `erd` (ERD)
**Audience:** Data architect, DBA
**Question:** What data is created, stored, transmitted?
**Signs of completeness:** All entities from the ERD are described in the DD. No entities with undefined attributes.

### 3. Users and Interaction
**Artifacts:** `user_story` (US), `use_case` (UC)
**Audience:** UX designer, developer, tester
**Question:** How do users interact with the system?
**Signs of completeness:** All user types are represented. Every US / UC traces to an FR.

### 4. Functionality
**Artifacts:** `functional` (FR), `non_functional` (NFR)
**Audience:** Developer, architect
**Question:** What must the system do, and how?
**Signs of completeness:** Every FR traces to a US or UC. Every NFR is linked to an FR.

### 5. Business Rules
**Artifacts:** `business_rule` (BR)
**Audience:** Business analyst, legal counsel, compliance officer
**Question:** What rules and constraints govern the system's behavior?
**Signs of completeness:** Business rules reference specific FRs or BPs.

---

## Кастомные точки зрения

Стандартные пять точек зрения покрывают большинство проектов. Однако в регуляторных,
финансовых и медицинских проектах могут потребоваться дополнительные:

**Примеры кастомных точек зрения:**
- **Безопасность и доступ** — требования к аутентификации, авторизации, шифрованию
- **Аудит и соответствие** — требования к логированию, SOX, GDPR, 152-ФЗ
- **Интеграции** — требования к API, интеграционным сценариям
- **Миграция данных** — требования к переносу исторических данных

**Key distinction:** custom viewpoints are defined via specific req_ids,
not via artifact types. This is because "Security" is not a separate requirement type,
but a cross-cutting slice over existing FR/NFR/BR. Only the BA knows exactly which requirements relate to security.

---

## Архитектурные разрывы

`check_architecture_gaps` проверяет архитектуру на двух уровнях:

### Уровень 1: Матрица покрытия

**What's checked:**
- Is there a stakeholder from the 4.2 registry with no recorded tie to any requirement?
- Is there a stakeholder whose every tie points at a requirement 5.2 has archived?
- Is there a business objective from business_context (7.3) not covered by any viewpoint?
- Is there an empty viewpoint (a viewpoint with no requirements)?

| Problem | Severity | What to do |
|---------|----------|-----------|
| Stakeholder with no recorded tie to any requirement | critical | Declare what you know with `declare_stakeholder_interest`, or create the missing requirements |
| Stakeholder reachable only by a shared title word | warning | Confirm it with `declare_stakeholder_interest` — a shared word is a coincidence, not a fact |
| Stakeholder traceable only OUTSIDE the requirements — named by a risk, a goal or a change request | warning | Go to the node that names them and record what actually holds among the requirements |
| Stakeholder whose every tie is to an archived requirement | warning | Re-declare against the replacement, or confirm the person is out of scope now |
| BG with no viewpoint coverage | warning | Check traceability in 5.1 or create the missing requirements |
| Empty viewpoint | info | Create artifacts of that type or remove the viewpoint |
| Registry read, but no row carries a name or a role | info | Nobody was checked — fill the registry in via the 3.2 or 4.2 tools |

The last row exists because a clean sheet and an unchecked sheet look identical otherwise.
A registry that is *absent* and a registry that is *present and unusable* are two different
facts, and the report states which one it met rather than printing zeros for both.

#### How the stakeholder verdict is reached

The platform asks four questions about each person in the registry, and says in the gap
text which ones it asked:

| Source | Written by | Counts as |
|--------|------------|-----------|
| A declared interest | 7.4, by the BA (`declare_stakeholder_interest`) | evidence |
| The requirement's `owner` | 7.1 | evidence |
| An approval decision on that requirement | 5.5 | evidence — a vote against counts too; opposing a requirement is the clearest possible sign it touches you |
| A word of 4+ letters shared with a requirement title or with another recorded name | nobody — it is a coincidence | heuristic only |
| The same, but found on a node that is NOT a requirement — a risk, a goal, a change request | nobody — it is a coincidence, and it sits outside the requirements | heuristic only, and the verdict says so |

Any one piece of **live** evidence and the stakeholder is covered, silently. Only the
heuristic and it is a warning that names its own weakness. Only evidence pointing at
archived requirements and it is also a warning, with its own wording. Nothing at all and
it is critical.

**A type is refused; a status is not.** The 5.1 graph holds more than requirements — risks
(6.3), business goals (6.2), change requests (5.4), the 6.4 solution scope, test cases.
None of them is a requirement, so none is searched for EVIDENCE and
`declare_stakeholder_interest` refuses one by name: recording it would let a business goal
silence a coverage gap, and would print an id under a heading counting requirements that
do not include it.

They do stay in the COINCIDENCE pool, which is a different thing. That pool is only ever
matched against, never rendered, and can only ever produce a warning — so a role named by
a risk title, or a person who owns a change request, is reported as "traceable only
outside the requirements" rather than as having nothing at all. Removing them from the
pool as well was tried and measured: against the pre-branch baseline it turned four kinds
of silence into red gaps, which is the single outcome decision 6 forbids. The objection
that the older wording answered — a warning claiming the word came from "a requirement
title" when it came from a risk — is answered in the sentence, where it belongs. An **archived** requirement is the opposite case — deprecated,
superseded or retired is a stage, not a category, so the declaration is accepted with a
warning, shown in the document marked `archived`, and simply not counted as live coverage.

The same rule holds everywhere else the archived requirement appears, because one id
governed by two rules on one page is how a signed document contradicts itself:

- the viewpoint tables still list it, tagged `_(archived)_` — the table is read by
  developers and by 7.5, and a retired requirement must not read there as one to build;
- `Total req` still counts it — marking adds a fact, it does not move a released number;
- level 2 skips it, as a subject and as a target: no one is advised to write a use case
  for a retired requirement, and a live use case whose only business process was
  deprecated is reported as hanging rather than as covered.

**Why the heuristic was kept rather than deleted.** It is how this check worked before the
model existed. Removing it would have handed every existing project a batch of new critical
findings on the day of the upgrade — about people whose coverage had not changed at all.
Demoting it adds information without taking any away.

**Names match through the registry.** The BA may write a role ("Product Owner") where 7.1
recorded a name ("Ivan Petrov"); the registry ties the two together, so either resolves to
the same person. An exact match is evidence; a partial one ("Priya" against "Priya Nair")
is a heuristic, for the same reason a shared title word is.

### Уровень 2: Семантические разрывы

Проверки, выходящие за рамки матрицы — на основе связей в репозитории 5.1:

| Gap | Severity | Explanation |
|-----|----------|--------------|
| UC with no BP | warning | A user interacts, but the business process isn't described |
| NFR with no FR | warning | A non-functional constraint is left "hanging" with no link to a function |
| FR with no UC or US | info | A function is described, but the usage scenario isn't documented |

**⚠️ Важно об уровне 2:** проверки семантических разрывов зависят от полноты графа 5.1.
Если BA добавил мало связей в трассировку — будет много ложных срабатываний (FR без UC не
потому что UC не написан, а потому что связь не добавлена). Интерпретируй результаты
с учётом этого контекста.

---

## Фреймворки архитектуры требований

BABOK описывает несколько концептуальных фреймворков. На платформе используется упрощённый
подход: автоматический маппинг + кастомные точки зрения. Для справки — основные фреймворки:

### Business Analysis Core Concept Model (BACCM)
Шесть взаимосвязанных концепций: Изменение, Нужда, Решение, Контекст, Стейкхолдер, Ценность.
Используется как философская основа, не как операционный инструмент.

### Zachman Framework (упрощённый)
Матрица «кто, что, где, когда, почему, как» × «контекст, концепция, логика, физика».
Полезен для Enterprise Architecture, избыточен для типичного IT-проекта.

### Agile: Story Map
Горизонтальная ось — пользовательские активности (эпики),
вертикальная — детализация (US). Хорошо работает в Scrum/Kanban.

**На практике:** для большинства проектов достаточно пяти стандартных точек зрения
платформы. Фреймворки нужны при работе в крупном корпоративном контексте.

---

## Снапшоты архитектуры

By analogy with the baseline in 5.5, task 7.4 supports snapshots:

**Когда делать снапшот:**
- Перед передачей архитектуры в 7.5 (Design Options)
- После существенного изменения скоупа (Change Request)
- По завершении каждой итерации в Agile-проектах

**Что фиксирует снапшот:**
- Состав viewpoints (автоматические + кастомные)
- Views — какие req входят в каждую точку зрения
- Открытые разрывы на момент снапшота
- Версия (v1.0, v1.1) и примечания

---

## Связь с другими задачами

| Задача | Роль в 7.4 |
|--------|-----------|
| **5.1** (Traceability) | Граф связей — основа для BFS-анализа разрывов уровня 2 |
| **4.2** (Conduct Elicitation) | Реестр стейкхолдеров — проверка покрытия в уровне 1 |
| **7.1** (Specification) | Репозиторий артефактов — источник для автоматического viewpoint-маппинга |
| **7.3** (Validate) | business_context — BG для матрицы покрытия |
| **4.4** (Communicate) | Architecture Document передаётся как артефакт для коммуникации |
| **7.5** (Design Options) | Architecture Document — входной артефакт для дизайна решения |

---

## Паттерны типичных архитектурных проблем

### «Острова требований»
Несколько изолированных кластеров req без связей между собой. Признак: граф 5.1 несвязный.
Что делать: проверить связи через `run_impact_analysis` (5.1), добавить трассировку.

### «Перекос в сторону функциональности»
Много FR/NFR, мало BP/US/UC. Разработчик видит что делать, но бизнес не видит контекст.
Что делать: создать BP и US/UC для ключевых функций.

### «Данные без процессов»
Хорошо описан ERD + DD, но нет BP описывающих как данные создаются и используются.
Что делать: создать BP для ключевых data flows.

### «Бесхозные NFR»
NFR не привязаны к конкретным FR. «Система должна работать быстро» — к чему именно?
Что делать: для каждого NFR добавить связь `satisfies` к конкретным FR в 5.1.
