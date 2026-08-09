# User Guide
## AI-powered Platform AInalyst
**Download:** https://github.com/chaussky/ainalyst.git

**Телеграм:** https://t.me/platform_ainalyst

---

# Глава 3 — Business Analysis Planning and Monitoring

## Общая характеристика Главы 3

Глава 3 BABOK — «Business Analysis Planning and Monitoring» — это фундамент, на котором строится весь проект. Именно здесь находятся ответы на вопросы, которые важно прояснить ещё до того, как вы начнёте работать с требованиями: как именно мы работаем, с кем, по каким правилам, где храним всё созданное и как понимаем, что движемся в нужном направлении.

Без Главы 3 всё остальное превращается в хаос: BA не понимает, зачем вообще документирует, стейкхолдеры ждут разного результата, изменения требований вносятся бесконтрольно, а конфликты между участниками никто не замечает заранее.

На практике большинство BA эту главу либо пропускают, либо выполняют «по памяти» — интуитивно, без фиксации. Именно здесь платформа даёт наибольший относительный прирост: она структурирует то, что обычно остаётся неформализованным.

---

## Задача 3.1 — Plan BA Approach (Выбор подхода)

### Краткое описание

BA определяет методологию работы на проекте: Waterfall, Agile или Hybrid. Это первое стратегическое решение — и оно влияет на всё, что будет дальше: как выявляются требования, как утверждаются изменения, насколько детальна документация.

### Боли и проблемы BA

**«Всегда Agile, потому что все так говорят»** — пожалуй, самая частая ошибка. BA выбирает методологию по умолчанию, не задумываясь о характеристиках конкретного проекта. В результате на регуляторном финтех-проекте работают без документации, а на небольшом ИТ-инструменте выстраивают монструозный Waterfall с тоннами артефактов.

**Нет обоснования** — даже если BA выбрал правильно, решение нигде не зафиксировано. Через месяц спонсор спрашивает «а почему мы так работаем?» — и BA не может ответить с данными.

**Регуляторный контекст игнорируется** — compliance-требования (банковское регулирование, GDPR, ISO) предполагают определённый уровень формальности. Чисто Agile-подход в таких проектах создаёт риски аудита, а BA об этом просто не думает на старте.

**Методология выбирается один раз и забывается** — а потом в середине проекта выясняется, что подход не работает для данного контекста, и команда вынуждена перестраиваться на ходу с большими потерями.

### Что мы реализовали

**Матрица выбора подхода** — платформа анализирует два параметра: ожидаемую частоту изменений требований и уровень неопределённости. На основе их комбинации (9 ячеек матрицы) она рекомендует один из трёх подходов вместе с набором техник BABOK.

**Regulatory override** — если проект имеет регуляторные требования, платформа автоматически корректирует рекомендацию: чистый Agile превращается в Hybrid с compliance-gates. Это защита от методологической ошибки в контексте аудита.

**Фиксация решения с контекстом** — рекомендованный подход, параметры, которые к нему привели, и заметки BA сохраняются в `ba_plan.json`. Это живой артефакт — он передаётся дальше по цепочке (в задачу 5.5 для governance-контекста).

**Техники BABOK к подходу** — платформа сразу рекомендует конкретные техники, соответствующие выбранной методологии. BA не ищет что применять — он получает готовый список.

### Ценности для BA

- **Экономия времени и снижение когнитивной нагрузки.** Методологическое решение, которое обычно BA принимает интуитивно за 5 минут (или копирует с прошлого проекта), теперь выносится на поверхность через три вопроса и получает структурированное обоснование. Весь разговор занимает 3–5 минут в диалоге с AIналитиком.
- **Защищаемая позиция перед стейкхолдерами.** Когда спонсор спрашивает «почему Hybrid, а не Agile?» — BA открывает артефакт и показывает: вот частота изменений High, вот неопределённость High, вот регуляторный контекст, вот почему это Hybrid. Решение принято с данными, а не «так принято».
- **Страховка от методологических ошибок.** Платформа не позволит просто написать «Agile» в регуляторном проекте без объяснений — regulatory override поднимает этот вопрос автоматически. Это снижает риск дорогостоящего разворота методологии в середине проекта.
- **Связность с остальной платформой.** Выбранный подход влияет на поведение других задач: в Главе 5 уровень формальности governance будет согласован с ним, в Главе 7 подход к спецификации (User Stories vs. формальные требования) будет следовать тому же решению.

### Как пользоваться: пример

BA начинает новый проект — внутренний портал заявок для HR-отдела в банке.

Он просто описывает ситуацию AIналитику:

> *«Новый проект — HR-портал для банка. Требования ещё размытые, HR не знает точно что хочет. Есть ли регуляторные ограничения — неясно, нужно уточнить у комплаенса.»*

AIналитик задаёт два уточняющих вопроса о частоте изменений и неопределённости. BA отвечает. AIналитик рекомендует Hybrid с конкретными техниками и объясняет почему. BA говорит «согласен, сохрани» — и решение зафиксировано.

> BA не выбирал параметры вручную, не открывал таблицу, не запоминал команды. Просто описал контекст — получил обоснованное решение.

### Optional step 3.1b: Plan BA Activities and Timing

BABOK 3.1 has two more elements beyond choosing an approach: which business analysis
activities will be performed (element .3), and when — in specific phases or iteratively
(element .4). This step is optional, and it's worth taking once the approach is settled:
call `plan_ba_activities` with the project ID. Leave the timing form unspecified and the
platform derives it from the chosen approach (Predictive → phases, Adaptive → iterations);
a plain Hybrid sits between the two on purpose, so the platform asks the BA to state the
form rather than guess it. Without any periods, the platform generates a starting skeleton
(two iterations or three stages, depending on the form) that the BA edits and re-runs.

Example call:

> *"Plan the BA activities for the HR portal project: two iterations, the first covers
> elicitation and current-state analysis with high effort, the second covers prioritization
> and specification with medium effort, planned for August and September."*

The result is saved into `ba_plan.json` and rendered in the report as a new
`## 3.1b BA Activities and Timing` section: the timing form and its source, a table of
periods (BABOK tasks, deliverables, effort, timing), and any timing constraints the BA
named (a regulatory deadline, vendor availability).

This isn't filed away either: Task 5.5 `prepare_approval_package` takes the methodology
straight from the planned timing form, so the BA no longer states Predictive/Agile a
second time when preparing an approval package. Task 4.1 `save_elicitation_plan` names the
work period that covers elicitation, with its planned effort, right in the session plan.

---

## Задача 3.2 — Plan Stakeholder Engagement (Карта стейкхолдеров)

### Краткое описание

BA составляет реестр всех участников проекта, определяет их влияние и интерес, назначает стратегии коммуникации и расписание взаимодействия. Это «живой документ» — он начинается с 1–2 имён и органично растёт по ходу проекта.

### Боли и проблемы BA

**Реестр стейкхолдеров — «мёртвый» документ.** BA создаёт таблицу в начале проекта, кладёт в папку и больше не открывает. Через два месяца там 4 устаревших строки, хотя реальных стейкхолдеров уже 12.

**The communication strategy lives in someone's head.** The BA remembers "write to James once a week, Rachel only on request," but nothing is written down. If the BA changes or gets sick, all of that information simply gets lost.

**Конфликт интересов не виден заранее.** BA не замечает, что два ключевых стейкхолдера имеют противоположные цели, пока не появляется открытый конфликт — и тогда уже приходится гасить пожар вместо управляемой фасилитации.

**Блокеры обнаруживаются поздно.** Стейкхолдер с высоким влиянием и негативным отношением к проекту — это управляемая ситуация, если обнаружить её на старте. Если обнаружить за неделю до согласования — это уже катастрофа.

**Не знают «кого ещё позвать».** BA общается с теми, кого знает. Каждое интервью открывает новых участников, но связи между ними никто не отслеживает.

### Что мы реализовали

**Power/Interest матрица с автоматической классификацией** — BA вводит влияние и интерес каждого стейкхолдера, платформа автоматически определяет квадрант (Key Players / Context Setters / Subjects / Crowd) и назначает стратегию коммуникации с рекомендуемой частотой.

**Живой реестр** — реестр не статичный документ. Задача 4.2 (анализ интервью) обновляет его через `update_stakeholder_registry`. Каждый раз, когда стейкхолдер называет нового участника, — он попадает в реестр с пометкой об источнике.

**Детекция блокеров** — платформа автоматически флагует стейкхолдеров с `attitude=Blocker` и выводит их отдельно. Это сигнал: данный человек требует особого внимания прямо сейчас.

**Расписание коммуникации** — частота и триггеры для каждого стейкхолдера фиксируются здесь и используются задачей 4.4 для проверки: кому давно не писали, у кого сработал триггер.

**Интеграция с задачей 4.5** — изменение attitude (был Champion, стал Neutral) фиксируется через `update_engagement_status` с историей: что было, что стало, что планируется.

### Ценности для BA

- **The stakeholder registry finally lives.** This is probably the hardest artifact to maintain in BA practice. The platform builds its update into the workflow: after every interview, AInalyst offers to add the participants who were mentioned. The registry grows organically instead of requiring a separate effort to "refresh the table."
- **Nothing gets lost when a project changes hands.** The new BA opens the registry and sees who's involved, how to treat them, when they last talked, and whether there were engagement issues. All the context that usually lives in one person's head is documented.
- **Early detection of engagement risk.** When James stops answering emails, it gets logged as a 🟡 signal, and the platform suggests possible reasons and tactics. The BA reacts proactively, before the problem becomes critical.
- **The communication schedule removes the nagging worry of "did I forget to write to someone."** Task 4.4 checks the schedule and produces a prioritized list of who to write to today. The BA doesn't have to keep it in their head.

### Как пользоваться: пример

На старте проекта BA знает только двух человек. Он говорит AIналитику:

> *"Stakeholders: Patricia, CFO, very influential, very interested, supports the project. Michael, head of IT, high influence, medium interest, skeptical."*

AInalyst immediately determines: Patricia is a Key Player (Manage Closely, weekly), Michael is a Context Setter with a negative attitude (Keep Satisfied, needs special attention). The registry is saved.

A week later, during an interview, Patricia mentions Diane, the chief accountant, who also works with the system. The BA tells AInalyst:

> *"Patricia mentioned Diane, the chief accountant, who also uses the system."*

And Diane gets added to the registry with a note about the source.

---

## Задача 3.3 — Plan BA Governance (Правила принятия решений)

### Краткое описание

BA устанавливает «правила игры» для проекта: кто принимает финальные решения по требованиям, как обрабатываются запросы на изменение, как разрешаются конфликты, куда эскалировать если что-то пошло не так.

### Боли и проблемы BA

**«А кто вообще принимает решения здесь?»** — вопрос, который BA задаёт в середине проекта, когда прилетает первый серьёзный CR. Выясняется, что у Product Owner нет полномочий, у спонсора нет времени, а разработчики уже начали делать по-своему.

**Scope creep без governance** — без зафиксированного процесса CR любое пожелание стейкхолдера превращается в требование. BA не может сказать «нет» без формальной процедуры. В результате скоуп расползается, команда злится, дедлайны срываются.

**«Помнишь, мы договорились что...»** — отсутствие зафиксированных договорённостей создаёт почву для конфликтов. Через три месяца каждый помнит по-своему. BA не может сослаться на документ.

**Разный уровень формальности для разных проектов** — маленький внутренний проект и критичная система для 500 пользователей требуют очень разных процессов. BA применяет один шаблон для всех — либо избыточно формально, либо рискованно легко.

### Что мы реализовали

**Шаблоны governance по уровням критичности** — платформа предлагает три уровня (High/Medium/Low) с готовыми процессами: контроль изменений, кто согласовывает, цикл ревью, цепочка эскалации. BA не придумывает с нуля — выбирает подходящий шаблон и дополняет под специфику.

**Фиксация лиц принятия решений** — явно зафиксировано, кто именно подписывает требования и CR. Это прямой вход для задачи 5.4 (оценка CR): Decision Record уходит именно этому человеку, не абстрактному «спонсору».

**Planning how requirements will be prioritized.** Who takes part, by which technique, against which criteria. Task 5.3 then runs the session and reconciles it against the plan.

**Chapter 5 actually reads this section.** Task 3.3 is not a reference document the BA re-applies from memory. The approval package in Task 5.5 prints the planned approvers and the response deadline; Task 5.5 and Task 5.4 both check whether the person who recorded a decision is one of the planned decision-makers; Task 5.4 carries the escalation path into the CR Decision Record; Task 5.3 checks the session's technique and its participants and reconciles participation in the result report. The project criticality also supplies the default traceability level for Task 3.4.

**Everything read from the plan is a cross-check or a default, never an override.** If Task 5.3 runs with a different technique than the one planned, the session keeps the technique the BA chose and says the plan disagrees. The same holds everywhere: the platform reports the difference, and the BA decides which of the two is out of date. Decisions stay with the analyst.

**Plan roles; the platform recognizes people.** Task 3.3 records roles ("Product Owner"), but a CR is resolved by a person and a requirement is approved by a person. The stakeholder registry (built in Task 3.2 and kept up to date through Chapter 4) is what ties a name to a role, so "John Smith approved it" is recognized as the planned Product Owner. Without a registry the platform stays quiet instead of reporting a name it cannot match as a breach of governance — one more reason to do Task 3.2 before the Chapter 5 work.

**Governance decision archive.** Everything recorded in Task 3.3 lives in `ba_plan.json` and is available at any time. To the question "how did we agree to handle changes?" the answer is in a single file.

### Ценности для BA

- **The BA gets "cover" for saying no.** When yet another change request shows up, the BA can say: "Under our process, this is a CR that needs to be submitted in this format and approved by James." That's not a refusal, it's a process. Professional scope protection.
- **The first CR doesn't turn into a crisis.** If governance isn't documented, the first serious change request causes chaos: nobody knows who decides, how to assess impact, or whether already-completed work needs to be redone. When governance is in place, it's just a routine procedure.
- **The level of formality matches the context.** A small internal tool doesn't get buried in bureaucracy. A mission-critical system gets the right level of control. The platform helps find that balance instead of forcing a single standard.
- **The rules don't quietly go stale.** A plan nobody reads drifts away from the project within a month, and nobody notices until an audit. Here, the moment a CR is resolved by someone outside the planned authority or a prioritization session runs with a different technique, the BA sees it — in the delivered document, not in a JSON file.

### Как пользоваться: пример

BA говорит:

> *"This is a critical project: an order management system for 300 users. Decisions are made by Victor (CEO), Susan (Product Owner), and me as Lead BA."*

AIналитик предлагает шаблон High-критичности: формальный CR с CAB, еженедельный ревью, эскалация BA → PM → Steering Committee. BA может принять как есть или скорректировать. Сохраняется одной фразой.

---

## Задача 3.4 — Plan Information Management (Управление информацией)

### Краткое описание

BA определяет, где и как хранятся требования и артефакты проекта, кто имеет доступ, насколько детальна трассировка. Это своего рода «архитектурный» договор — он влияет на то, насколько легко потом работать с Главой 5.

### Боли и проблемы BA

**Требования «везде и нигде».** Часть в Confluence, часть в email, часть в Jira, часть в голове разработчика. Когда нужно найти актуальную версию требования — никто не знает, где она.

**Трассировка «как будет удобно».** Никто не договорился заранее, насколько детально отслеживать связи. В итоге BA строит полный граф от бизнес-целей до тест-кейсов, а команда не понимает зачем это нужно и не поддерживает.

**Доступ неструктурирован.** Разработчики случайно редактируют требования. Стейкхолдеры не знают, где смотреть актуальную версию. Все ходят к BA лично — он превращается в узкое место.

**Confluence настроен «потом».** Интеграция с корпоративными системами откладывается и в итоге так и не настраивается. BA дублирует артефакты вручную.

### Что мы реализовали

**Договор о трассировке с тремя уровнями** — Lite (только источники), Standard (FR + тест-кейсы), Full (полная цепочка бизнес-цели → код). BA выбирает уровень один раз, и платформа ведёт трассировку в соответствии с ним на протяжении всей Главы 5.

**Реестр инструментов хранения** — зафиксировано, где хранятся какие типы артефактов. Не просто «Confluence», а конкретно: «Confluence — финальные спецификации; Jira — задачи и CR; локальный репозиторий — JSON-граф трассировки».

**Правила доступа** — явно зафиксировано, кто читает, кто редактирует, кто согласовывает.

**Интеграция с Confluence** — настраивается один раз через переменные окружения. После этого каждое обновление требования в задаче 5.2 автоматически синхронизируется с Confluence. BA больше не думает об этом.

**Three more decisions that other chapters act on, not just record.** The BA can also plan the level of detail each audience gets, the scope and repository for reuse, and which requirement attributes this project maintains (Minimum / Standard / Full). These aren't filed away: Task 4.4 states the planned level of detail in every communication package it builds, and Task 5.2 ranks reuse candidates by the planned scope and audits exactly the planned attribute set. A project that skips this planning has nothing read from it: 4.4 stays silent about detail levels, and 5.2 starts its reuse search at `initiative` and audits `owner` only. (Two repairs that shipped with the feature do reach every project, plan or no plan: the health report's action list is numbered from 1 instead of opening at 2, and the reuse report no longer calls its ranking bonus a minimum.)

### Value for the BA

- **«Где актуальная версия?» — больше не вопрос.** Один зафиксированный источник правды. Все знают, куда смотреть.
- **Уровень трассировки согласован до начала работы.** Это предотвращает конфликт в середине проекта, когда BA построил полный граф, а PM говорит «это избыточно». Или наоборот — когда аудиторы требуют трассировку, которую никто не вёл.
- **Confluence перестаёт быть ручной работой.** Если настроена интеграция — обновление требования автоматически публикуется. BA не копирует артефакты вручную между системами.

---

## Задача 3.5 — Evaluate BA Performance (Оценка эффективности BA)

### Краткое описание

BA оценивает текущее состояние практики бизнес-анализа в команде или организации, выявляет проблемные зоны и составляет конкретный план улучшений. Задача опциональная — она нужна, когда есть явные проблемы или при онбординге на новый проект.

### Боли и проблемы BA

**Симптомы видны, причины — нет.** «Разработчики постоянно переспрашивают» — это симптом. Причина может быть в недостаточной детальности требований, или в отсутствии acceptance criteria, или в том, что требования меняются уже в спринте. Без структурированного взгляда BA лечит симптомы, а не причины.

**Нет метрик — нет разговора.** BA не может аргументировать инвестиции в улучшение практики, если нет данных. «Мне кажется, что качество улучшилось» — не аргумент. «Defect Rate снизился с 15% до 5%» — аргумент.

**Стандартные проблемы — стандартные решения, но их нужно вспомнить.** BA знает, что делать со scope creep или с отсутствием шаблонов — но на это нужно время и когнитивный ресурс. Особенно при онбординге на новый проект.

### Что мы реализовали

**Библиотека проблем → рекомендации** — BA называет проблемы в свободной форме, платформа сопоставляет их с базой известных ситуаций и даёт конкретные рекомендации. «Scope creep» → «Усилить Governance: формализовать процесс CR через 5.4». «Нет метрик» → список метрик с описанием, как считать.

**Фиксация метрик с baseline и target** — не просто «улучшить», а «Defect Rate: с 15% до 5%». Это основа для последующего измерения улучшений.

**Связь с остальными задачами** — выявленные проблемы часто требуют усиления конкретных задач платформы. Платформа указывает, куда именно: «слабая трассировка → настроить 5.1», «scope creep → усилить 5.4».

### Ценности для BA

- **Структурированный онбординг на новый проект.** BA пришёл на проект с существующей командой. Он называет что видит: «нет шаблонов, долгое согласование, слабая трассировка» — и получает план улучшений с приоритетами и конкретными шагами.
- **Аргументация для руководства.** «Нам нужно ввести формальный CR-процесс» с данными о текущих потерях и целевыми метриками — это совсем другой разговор со спонсором, чем просто запрос.
- **Личная рефлексия для опытного BA.** Полезно не только при онбординге, но и после завершённого проекта: что работало, что нет, что улучшить в следующий раз.

---

## Финальный синтез по Главе 3

**Общая ценность Главы 3 для BA — это переход от «я работаю по наитию» к «у нас есть фундамент».** Артефакты Главы 3 не только документируют начальные решения — они используются на протяжении всего проекта: реестр стейкхолдеров растёт до конца Главы 4, governance работает в каждой задаче Главы 5, информационная архитектура определяет, как Confluence получает данные.

**Ответственность BA в Главе 3 минимальна технически.** Не нужно помнить ни одной команды. Нужно: описать контекст проекта, ответить на 2–3 уточняющих вопроса AIналитика, сказать «сохрани». Вся техническая работа — выбор параметров, создание JSON, сохранение артефактов — выполняется AIналитиком. BA получает готовые документы в `governance_plans/reports/`.
