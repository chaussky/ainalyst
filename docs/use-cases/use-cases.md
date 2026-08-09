## AI-powered Platform AInalyst
**Download:** https://github.com/chaussky/ainalyst.git

**Телеграм:** https://t.me/platform_ainalyst

---

# Варианты использования AI Платформы AIналитик
## Use Cases — возможные сценарии работы бизнес-аналитика в Платформе. Ситуации и имена вымышлены, любые совпадения случайны

---

В пользовательской инструкции мы рассматривали возможности платформы через один сквозной проект. Здесь — другой подход: независимые сценарии из разных индустрий и разных рабочих ситуаций. Каждый показывает конкретную боль и то, как платформа её снимает.

Контексты разные. Аналитики разные. Но принцип один: вы описываете ситуацию — платформа делает работу.

---

## UC-01 — Когда аналитик уходит из проекта

> **Для кого:** Руководители отделов бизнес-анализа, технические директора, PM
> **Боль:** Ключевой BA уволился, ушёл в отпуск, заболел — и весь контекст проекта исчез вместе с ним
> **Фичи:** Реестр стейкхолдеров (3.2), Decision Log (4.5), граф трассировки (5.1), история CR (5.4), статусы согласования (5.5)

### Ситуация

It's month five of a project to implement an assortment management system at a large retail chain. The key business analyst, Anthony, the person who knows every stakeholder personally, remembers why FR-034 was dropped back in March, and keeps three unresolved approval conditions with the CFO in his head, suddenly resigns.

На проекте: 14 стейкхолдеров с разной историей вовлечённости, 87 требований в разных статусах, 9 принятых Change Request, и через 3 недели презентация Steering Committee.

Руководитель отдела BA в панике. Новый аналитик Юлия выходит на проект в понедельник.

Это типичная ситуация, которая в большинстве компаний превращается в кризис: несколько недель уходит на «войну с архивами», интервью с теми кто «что-то помнит», и попытки восстановить контекст по переписке в почте и мессенджерах.

С AIналитик эта история выглядит иначе.

### Что делает Юлия

Она открывает AIналитик, смотрит на папку проекта и пишет одну фразу:

> **Julia:** I just started on the assortment-2026 project. The previous business analyst, Anthony, resigned. Tell me about the current state: stakeholders, open questions, unresolved approvals.

### Как отвечает AIналитик

AIналитик читает все артефакты проекта и за несколько секунд выдаёт структурированную сводку:

---

> **AIналитик:** Проект assortment-2026, активная фаза — lifecycle. Вот текущий контекст:
>
> **Stakeholders (14 people):**
> Karen Foster (CFO): Key Player, Manage Closely. Status: ⚠️ Concerned since March 28. Last interaction: April 3, an email that went unanswered. Needs attention.
> Michael Turner (IT Director): Context Setter. Status: ✅ Champion. Active.
> *(12 more participants with history and statuses)*
>
> **Открытые вопросы по согласованию:**
> 3 conditional approval не закрыты. Один просрочен: условие финансового директора по FR-037 (security review) — дедлайн был 1 апреля.
>
> **Recent decisions from the Decision Log:**
> March 15: FR-034 moved to v2. Reason: high cost, low priority after prioritization. Decision made by Anthony together with the Product Owner.
> March 22: CR-008 (ERP integration) approved with a condition: implement asynchronously.
>
> Хочешь, чтобы я показал полный реестр стейкхолдеров или сразу перешли к незакрытым согласованиям?

---

Юлия продолжает:

> **Юлия:** Покажи детально ситуацию с финансовым директором — почему Concerned и что с просроченным условием?

---

> **AInalyst:** Karen Foster moved to Concerned status on March 28, after the CR-008 meeting. In the Decision Log: she raised security concerns about the ERP integration. Anthony promised a security review by April 1.
>
> CR-008 condition: "FR-037 must pass a security review before development of the integration module begins."
> Status: ⛔ Overdue. Owner: Anthony (resigned).
>
> Recommendation: write to Karen today, introduce yourself, explain the situation, and agree on a new deadline. Should I draft the email?

---

> **Юлия:** Да, подготовь. И обнови ответственного по этому условию на меня.

### Что получает Юлия

За 20 минут она знает:

- Кто из стейкхолдеров требует немедленного внимания и почему
- Почему было принято каждое ключевое решение за последние два месяца
- Что конкретно нужно сделать сегодня, чтобы не провалить презентацию через 3 недели
- Полную историю каждого требования — откуда взялось, как менялось, кто согласовал

Контекст, который обычно живёт в голове одного человека и исчезает вместе с ним, — здесь зафиксирован, структурирован и доступен новому аналитику с первой минуты.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — всё делает AIналитик автоматически.*

При первом запросе AIналитик обращается к нескольким источникам одновременно: читает реестр стейкхолдеров с историей изменений статусов (MCP-сервер главы 3 — `planning_mcp`), достаёт Decision Log со всеми зафиксированными решениями (MCP-сервер задачи 4.5 — `elicitation_collaborate_mcp`), проверяет статусы согласования и открытые условия (MCP-сервер задачи 5.5 — `requirements_approve_mcp`). Граф трассировки (MCP-сервер задачи 5.1 — `requirements_traceability_mcp`) позволяет по любому требованию мгновенно ответить «откуда это взялось и что за ним тянется».

All this information accumulated in structured JSON files in the `governance_plans/data/` folder throughout the project, every time Anthony saved interview results, updated a stakeholder status, recorded a decision, or closed a CR. Automatically, as a side effect of routine work.

Для Юлии это означает: она получает не папку с документами, которые нужно читать часами, а живую структурированную память проекта, с которой можно сразу разговаривать.

---

## UC-02 — Выбор методологии: одна фича, два совершенно разных результата

> **Для кого:** Бизнес-аналитики любого уровня
> **Боль:** Методология выбирается «по умолчанию» — без анализа контекста и с риском дорогостоящей ошибки
> **Фичи:** Матрица выбора подхода, regulatory override (задача 3.1)

### Ситуация

Один и тот же аналитик. Одна и та же функция платформы. Два проекта — и принципиально разные результаты. Хорошая иллюстрация того, как платформа работает не по шаблону, а по контексту.

**Проект A:** HR-стартап, автоматизация онбординга. Команда пять человек, заказчик сам не знает что хочет, всё будет меняться.

**Проект B:** Система оценки кредитных рисков в банке. Требования формально определены. Есть регуляторные обязательства перед ЦБ, через год аудит. Команда хочет Scrum — «мы всегда так делаем».

BA Paul opens AInalyst for each project.

### What Paul does: Project A

> **Paul:** New project. HR startup, we're automating employee onboarding. Small team, the client doesn't fully know what they want yet, requirements will definitely change.

### Как отвечает AIналитик — Проект A

---

> **AIналитик:** Два уточняющих вопроса:
> 1. Как часто будут меняться требования — редко / регулярно / постоянно?
> 2. Насколько высока неопределённость в понимании конечного результата прямо сейчас?

> **Paul:** Constantly. Uncertainty is high.

> **AIналитик:** Рекомендация: **Adaptive (Agile)**.
>
> Обоснование: высокая частота изменений + высокая неопределённость — классический Agile-контекст. Итеративные циклы позволят проверять гипотезы без дорогостоящих переделок.
>
> Рекомендованные техники BABOK: User Stories, Story Mapping, Iterative Elicitation, Product Backlog Refinement.
>
> Сохранить решение?

---

### What Paul does: Project B

> **Paul:** New project. A bank, credit risk assessment system. Requirements are laid out in regulatory documents, the team wants Scrum. There are central bank regulatory requirements, and an audit in a year.

### Как отвечает AIналитик — Проект B

---

> **AIналитик:** ⚠️ Регуляторный контекст обнаружен.
>
> Команда хочет Scrum — я понимаю логику. Но в данном контексте это создаёт серьёзный риск. Вот почему:
>
> Регуляторный аудит ЦБ требует полной трассировки: каждое требование должно быть документировано, согласовано и иметь доказательство выполнения. В чистом Scrum это не предусмотрено — артефакты фиксируются по минимуму, а история изменений не строгая.
>
> **Рекомендация: Hybrid (Predictive + Adaptive).**
>
> Predictive-слой: фиксация требований, трассировка, compliance gates перед каждым релизом, аудиторский след.
> Adaptive-слой: итеративная разработка, спринты, демо стейкхолдерам.
>
> Это позволяет команде работать по Scrum внутри итераций — и при этом пройти аудит без авралов.
>
> Сохранить решение и сформировать план BA с compliance-чеклистом?

---

### What Paul gets

В первом случае — быстрое подтверждение правильного интуитивного решения. Во втором — защита от ошибки, которую он мог бы не заметить сам, и которая вскрылась бы только во время аудита.

Платформа не просто подбирает методологию по параметрам. Она замечает контекст, который меняет правила — и объясняет почему.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — всё делает AIналитик автоматически.*

MCP-сервер фазы `planning` (`planning_mcp`) при вызове инструмента `select_ba_approach` анализирует переданные параметры через матрицу `APPROACH_MATRIX`: частота изменений, неопределённость, размер команды, временной горизонт. Для Проекта B срабатывает отдельная проверка `REGULATORY_OVERRIDE` — если в контексте обнаружен регуляторный надзор, рекомендация автоматически корректируется до Hybrid вне зависимости от остальных параметров. Результат сохраняется в `ba_plan.json` как официальное методологическое решение проекта.

---

## UC-03 — 90-минутное интервью становится структурированным артефактом

> **Для кого:** Бизнес-аналитики, работающие с интервью
> **Боль:** После интервью — часы ручного разбора записей, и всё равно что-то важное теряется
> **Фичи:** Обработка результатов выявления (задача 4.2)

### Ситуация

An insurance company. BA Daniel conducted a 90-minute interview with the director of claims settlement. The transcript is a raw Zoom recording: interruptions, digressions, two places where the interviewee contradicts herself, and one place where she clearly contradicts something the IT director said a week earlier. The file sits in the `inputs/` folder.

Daniel could spend two hours reviewing it by hand. Instead he writes one line.

### What Daniel does

> **Daniel:** Process the interview transcript with Helen Walsh from the file interview_helen_20260401.txt

### Как отвечает AIналитик

---

> **AIналитик:** Обработал транскрипт (94 мин, 8 400 слов). Вот результат:
>
> **Требования-кандидаты (14):**
> — FR-кандидат: Система должна автоматически рассчитывать срок выплаты на основе типа убытка. Источник: «мы тратим по 2 часа на каждый сложный случай только на расчёт сроков» (мин. 23).
> — NFR-кандидат: Время отклика при открытии карточки убытка — не более 3 секунд. Источник: «сейчас грузится по 10-15 секунд, люди уходят пить кофе».
> — *(ещё 12 требований)*
>
> **Business rules (3):**
> Category A claims (over 500K dollars) must go through senior expert review before payout.
>
> **Метрики:**
> — Целевое время обработки стандартного убытка: 4 рабочих дня (сейчас — 9).
>
> **Пробелы — нужно уточнить (2):**
> — Неясно: кто имеет право вручную переопределить автоматический расчёт срока?
> — Неясно: как система должна обрабатывать убытки по иностранным полисам?
>
> **Contradiction ⚠️:**
> Helen says: "the tax authority database integration is urgent, it's blocking our work." The IT director (interview from March 25): "the tax authority integration is next year, there's no capacity right now." Needs resolution.

> **Daniel:** Helen mentioned someone named Max from IT support, add him to the stakeholder registry.

> **AInalyst:** Added. Max (last name not mentioned): IT support, specific role not yet determined. Source: interview with Walsh, April 1, 2026, min. 47. Recommend confirming his last name and role at the next contact.

---

### What Daniel gets

Instead of two hours of manual review, a structured artifact in minutes. Every requirement is captured, the key metric wasn't lost, and the gaps and the contradiction are visible right away, while Helen still remembers the conversation and can easily answer a follow-up.

Max, whom Daniel "caught out of the corner of his ear," is now in the stakeholder registry with a note on where he came from.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

AIналитик читает файл из `inputs/` и передаёт его в MCP-сервер задачи 4.2 (`elicitation_conduct_mcp`). Инструмент `process_elicitation_results` анализирует текст и возвращает структурированный набор: требования-кандидаты по типам, бизнес-правила, метрики, пробелы, противоречия. Если в тексте найдены новые имена — предлагает вызов `update_stakeholder_registry`, который добавляет участника в `stakeholder_registry.json` с пометкой об источнике. Итоговый Markdown-артефакт сохраняется в `governance_plans/reports/` через `save_artifact` из `common.py`.

---

## UC-04 — Конфликт стейкхолдеров, который никто не заметил

> **Для кого:** Бизнес-аналитики на проектах с множеством стейкхолдеров
> **Боль:** Два стейкхолдера хотят противоположного — и никто не замечает до этапа согласования
> **Фичи:** Кросс-анализ нескольких сессий выявления (задача 4.2)

### Ситуация

A manufacturing holding. The project: a unified production planning system. Over three weeks, BA Natalie conducted four interviews: the production director, the chief technologist, the head of supply chain, and the CFO. She processed each interview separately, got the requirements, saved the artifacts, and moved on.

Всё шло хорошо, пока она не попросила платформу сравнить результаты.

### What Natalie does

> **Natalie:** Compare the results of the four interviews for the production-planning project. I want to understand where there are contradictions and where stakeholders agree.

### Как отвечает AIналитик

---

> **AIналитик:** Анализирую четыре артефакта выявления...
>
> **Consensus, stakeholders agree:**
> All four consider visualizing production capacity utilization a priority
> Three of four want integration with SAP ERP
>
> **Conflict 🔴, requires resolution:**
> Speed vs. data accuracy.
> Production director (Bennett): "The main thing is replanning speed. We need data within 15 minutes, even if it's slightly stale."
> CFO (Reed): "We need 100% real-time accuracy for financial reporting. Speed is secondary."
>
> Это фундаментальный архитектурный конфликт: real-time vs. batch processing. Нельзя удовлетворить оба требования без явного компромисса.
>
> **Пробел — никто не прояснил:**
> — Кто имеет право вручную корректировать план? Это критично для бизнес-правил.
>
> **Recommendation:** Hold a joint workshop with Bennett and Reed. There's no moving to architecture without a decision on data.
>
> Зафиксировать конфликт как открытый вопрос?

> **Natalie:** Yes. And suggest a workshop structure: what to discuss, in what order.

> **AIналитик:** Конфликт зафиксирован. Структура воркшопа на 60 минут:
>
> **Блок 1 (15 мин):** Показать оба требования на экране рядом. Попросить каждого сформулировать: что именно сломается, если принять требование другой стороны?
>
> **Блок 2 (20 мин):** Разобрать три варианта: (1) real-time для всех, (2) batch для всех, (3) разные потоки — финансовый модуль получает real-time, производственный — 15-минутные обновления.
>
> **Блок 3 (25 мин):** Выбрать вариант и зафиксировать решение.
>
> Твоя роль — фасилитатор, не арбитр. Ты структурируешь разговор, решение принимают они.

---

### What Natalie gets

Конфликт, который мог всплыть на этапе согласования требований (и потребовать переделки уже готовых артефактов), обнаружен сейчас — когда его ещё легко разрешить одним воркшопом. Есть конкретный план действий.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

MCP-сервер задачи 4.2 (`elicitation_conduct_mcp`) при вызове `compare_elicitation_results` читает сохранённые артефакты по всем указанным сессиям выявления. По каждой теме инструмент сопоставляет что сказал каждый стейкхолдер, ищет прямые противоречия и зоны консенсуса. Выявленный конфликт может быть сразу передан в задачу 4.5 (`elicitation_collaborate_mcp`) — зафиксирован в Decision Log как открытый вопрос, требующий разрешения через воркшоп или эскалацию.

---

## UC-05 — Стейкхолдер, который молча саботирует проект

> **Для кого:** Бизнес-аналитики, работающие в организациях со сложной политической средой
> **Боль:** Что-то явно идёт не так, но непонятно что — и как реагировать профессионально
> **Фичи:** Диагностика сигналов вовлечённости, история изменений статуса (задача 4.5)

### Ситуация

A government organization. A document archive digitization project. BA Steven has been on it for three months.

The deputy IT director, David, was initially one of the biggest supporters: he helped organize interviews, proposed ideas himself, showed up to every meeting. In the stakeholder registry: Champion status.

Three weeks ago something changed. David replies to emails after 3-4 days, briefly. He was silent through the entire last meeting. And yesterday the director wrote to Steven: "David sent me a list of project risks. Let's discuss."

Steven is confused and doesn't know how to interpret what's happening.

### What Steven does

> **Steven:** David used to actively support the project. For the last three weeks: he doesn't answer emails, stays silent in meetings, and yesterday wrote to the director going around me with a list of risks. What's going on and what should I do?

### Как отвечает AIналитик

---

> **AIналитик:** Сигнал 🟡 — требует проактивной реакции. Это паттерн пассивного сопротивления. Три наиболее вероятные причины:
>
> **Option 1: David doesn't feel heard.**
> He agrees publicly because disagreeing feels awkward in his role. He influences privately through the director, the only channel available to him. Tactic: a 1-on-1 meeting with no agenda. "I sense you have concerns. I want to hear them directly."
>
> **Вариант 2: Конкретные технические опасения, которые неудобно озвучивать публично.**
> Возможно, понимает что-то про архитектуру или интеграцию, чего другие не видят. На встречах молчит, потому что аудитория нетехническая. Тактика: та же встреча 1-на-1, с конкретным запросом: «Расскажи подробнее про риски, которые ты описал директору».
>
> **Option 3: A shift in leadership positioning or personal interests.**
> Something changed in the organizational context: new priorities, a threat to budget or to David's authority. Tactic: carefully probe through indirect sources before meeting directly.
>
> Какой вариант кажется тебе наиболее вероятным?

> **Steven:** Probably option 2, he definitely has technical knowledge the rest of us don't. I'll go through a 1-on-1. Update his registry status: was Champion, now Concerned. I've scheduled a meeting for Friday.

> **AIналитик:** Обновлено. История:
> Champion (с января 2026) → Concerned (14 апреля 2026).
> Причина: пассивное сопротивление, выход на директора в обход BA.
> Запланированное действие: встреча 1-на-1 в пятницу 18 апреля.
>
> После встречи возвращайся — обновим статус и зафиксируем что выяснилось.

---

### What Steven gets

Вместо тревожного «что-то не так, не знаю что» — конкретная диагностика с тремя гипотезами и тактиками для каждой. Конкретный следующий шаг.

And importantly: the status change history is recorded. If Steven goes on leave or leaves the project, the next analyst will open the registry and see this whole history. No need to explain "why David suddenly became a problem."

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — всё делает AIналитик автоматически.*

AIналитик передаёт описание ситуации в MCP-сервер задачи 4.5 (`elicitation_collaborate_mcp`). Инструмент `diagnose_engagement_signal` анализирует паттерн поведения и возвращает классификацию сигнала, вероятные причины и тактики. После того как BA принял решение, `update_engagement_status` обновляет запись в `stakeholder_registry.json` — не просто меняет текущий статус, а сохраняет полную историю с датой, причиной и запланированным действием. Эта история накапливается на протяжении всего проекта и доступна любому члену команды — в том числе новому аналитику, который придёт на замену.

---

## UC-06 — Подключение к проекту, который уже идёт

> **Для кого:** Бизнес-аналитики, которые начинают работать с платформой в середине проекта
> **Боль:** Много работы уже сделано без AIналитик — интервью проведены, требования собраны, переписка накоплена. Начинать заново нереально. Но и работать без структуры дальше — риск.
> **Фичи:** Инициализация проекта по готовым материалам, импорт требований из Confluence, гибкое переключение фаз

### Ситуация

A financial company. A credit underwriting process automation project has been running for three months. BA Kevin just joined the team, the previous analyst moved to another project.

Накоплено многое: страница в Confluence с 60 требованиями, четыре транскрипта интервью в общей папке, несколько цепочек писем со стейкхолдерами, неформальная таблица приоритетов в Excel. Всё это существует в разрозненном виде — нет единой структуры, нет трассировки, нет истории решений.

Начинать с нуля и переспрашивать стейкхолдеров о том, что уже обсуждалось, — значит терять их доверие. Но и двигаться дальше, держа всё в разных местах — значит рисковать.

Kevin decides to plug AInalyst into the live project right now.

### What Kevin does

Он запускает фазу `planning` и начинает не с «нового проекта», а с описания того, что уже есть:

> **Kevin:** I need to connect the platform to a project that's already underway. The project is called credit-underwriting-2026. It's been running three months, I just joined. Requirements are collected on a Confluence page called "Underwriting / System Requirements." I know six stakeholders: Peters (business owner), Grant (IT architect), Sheridan (compliance), and three more business analysts. Four interviews have been done, transcripts are in inputs/.

### Как отвечает AIналитик

---

> **AIналитик:** Понял — инициализирую проект на основе существующих материалов.
>
> **Шаг 1: Создаю структуру проекта.**
> Проект credit-underwriting-2026 зарегистрирован. Активная фаза: planning.
>
> **Step 2: Adding stakeholders.**
> Added all six. Peters: provisionally Key Player (confirm influence/interest when you can). Statuses set to Unknown, update after you've met them.
>
> **Шаг 3: Выгружаю требования из Confluence.**
> Читаю страницу «Андеррайтинг / Требования к системе»...
> Найдено: 58 требований. Структура неоднородная — часть в формате User Story, часть в свободном тексте, 7 строк без явного идентификатора.
>
> Что хочешь сделать?
> — (А) Импортировать как есть и потом верифицировать качество
> — (Б) Нормализовать формат при импорте — займёт немного дольше
> — (В) Сначала показать мне первые 10, чтобы принять решение

> **Kevin:** Let's go with option B, normalize on import.

> **AIналитик:** Нормализую... готово.
> Импортировано 58 требований: 51 корректно структурированы, 7 помечены как «требуют уточнения» — неполные формулировки, нет критериев приёмки. Покажу список позже.
>
> Рекомендую следующий шаг: переключиться в фазу `lifecycle` и запустить начальную трассировку — связать требования между собой и с бизнес-целями. Для этого мне нужно понять: есть ли уже зафиксированные бизнес-цели проекта, или начнём их формулировать с тобой?

---

> **Kevin:** Objectives aren't recorded yet, but Peters mentioned cutting application review time from 5 days to 2. That's the main goal.

> **AIналитик:** Фиксирую бизнес-цель: BG-001 — «Сократить время рассмотрения кредитной заявки с 5 до 2 рабочих дней к Q3 2026».
>
> Теперь посмотрим, какие из 58 требований на эту цель работают, а какие могут быть вне скоупа. Это займёт пару минут — запустить?

---

### What Kevin gets

За один сеанс работы — не с нуля, а ровно оттуда где остановился предыдущий аналитик:

- Все требования из Confluence в структурированном репозитории с идентификаторами
- Реестр стейкхолдеров с заготовкой для обновления статусов
- Первая сформулированная бизнес-цель
- Понимание какие требования подозрительны и требуют внимания

Платформа не заставляет начинать заново. Она встраивается в то, что уже есть.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

При инициализации существующего проекта AIналитик использует MCP-сервер фазы `planning` (`planning_mcp`) для создания базовой структуры: регистрирует проект, создаёт реестр стейкхолдеров с переданными именами. Для чтения Confluence задействован встроенный Confluence MCP-сервер — он напрямую читает страницу по названию и передаёт содержимое на обработку. Нормализация требований происходит через `requirements_traceability_mcp` (задача 5.1) — каждому требованию присваивается идентификатор, структура приводится к единому формату, проблемные записи помечаются флагом. Транскрипты из `inputs/` можно обработать в любой момент через фазу `elicitation`, не переходя к ней немедленно — порядок фаз гибкий.

---

## UC-07 — Когда на проекте нет бизнес-аналитика

> **Для кого:** Продакт-менеджеры, проджект-менеджеры, технические директора и CTO на проектах без выделенного BA
> **Боль:** Понимание продукта есть, но нет методологической экспертизы — требования размытые, стейкхолдеры говорят разное, документация отсутствует или устаревшая
> **Фичи:** Полный цикл BABOK-методологии под руководством платформы, без необходимости знать BABOK заранее

### Ситуация

Технологический стартап. Команда разрабатывает B2B SaaS-продукт для управления корпоративными командировками. Восемь человек: три разработчика, дизайнер, QA, CEO и CPO — он же де-факто продакт-менеджер.

CPO Alex understands the market and users well. But he has no experience with requirements methodology: requirements live in his head, in Notion as scattered notes, and in team chats. The architect has already rebuilt the booking module twice because "it turned out that wasn't what was meant."

Нанять BA в штат — дорого и преждевременно. Но продолжать работать как сейчас — значит продолжать переделывать.

Alex decides to try AInalyst on his own.

### What Alex does

Он ничего специально не готовит и не изучает BABOK. Просто открывает AIналитик и описывает ситуацию своими словами:

> **Alex:** We're building a B2B SaaS for corporate business travel. I'm the CPO, we don't have a BA. I want to get our requirements in order, right now it's all in my head and in Notion. We keep rebuilding things because of misunderstandings. Where do I start?

### Как отвечает AIналитик

---

> **AIналитик:** Хороший старт — ты правильно диагностировал проблему. Вот предлагаемый маршрут, коротко:
>
> 1. Сначала разберёмся кто твои стейкхолдеры и чьи интересы нужно учитывать — это займёт 15 минут.
> 2. Потом зафиксируем бизнес-цели проекта в измеримом виде — чтобы было понятно что считается успехом.
> 3. Затем перейдём к самим требованиям — структурируем то что уже есть и добавим то чего не хватает.
>
> Начнём? Расскажи: кто платит за ваш продукт и кто его использует — это разные люди?

> **Alex:** The company's HR director or CFO pays. It's used by the employees themselves who travel, and by travel coordinators who arrange everything.

> **AIналитик:** Отлично — у тебя три разные группы с потенциально разными потребностями. Продолжим по каждой. Ещё вопрос: есть ли кто-то внутри вашей команды, чьё мнение о продукте критично — например, CTO или кто-то кто работал с клиентами напрямую?

---

*Twenty minutes into the conversation, AInalyst has built a map of 8 stakeholders with roles and preliminary statuses. Alex didn't know the term "stakeholder registry," now he has a structured artifact for BABOK Task 3.2.*

---

> **Alex:** Okay, stakeholders are clear. What's next?

> **AIналитик:** Теперь цели. Ты упомянул что постоянно переделываете модуль бронирования. Попробуй сформулировать: что должно измениться в вашем продукте или процессе через полгода, чтобы ты сказал «мы сделали это правильно»?

> **Alex:** Well... travel coordinators stop calling us with questions every day. And developers stop rebuilding the same thing twice.

> **AIналитик:** Хорошо — это две разные цели, давай сделаем их измеримыми:
>
> BG-001 (черновик): «Снизить количество обращений travel-координаторов в поддержку на 70% к Q3 2026».
> BG-002 (черновик): «Сократить процент задач, возвращаемых на доработку из-за неясных требований, с текущего уровня до менее 10%».
>
> Как тебе такие формулировки? Если цифры не те — скажи, скорректируем.

---

From there, AInalyst walks Alex step by step through structuring the requirements, suggesting they record what's already built and what's planned, asking clarifying questions wherever the wording is vague, and pointing out contradictions between what's written in Notion and what Alex describes verbally.

### What Alex gets

Через несколько сеансов работы — без консультантов, без курсов по BABOK, без найма нового сотрудника:

- Реестр стейкхолдеров с ролями и приоритетами
- Сформулированные и валидированные бизнес-цели
- Структурированный репозиторий требований с трассировкой
- Понимание почему конкретные требования конфликтуют между собой — и как это разрешить

Methodology here became the platform's job, not his. Alex brought knowledge of the product and the market. The rest, process, structure, artifacts, AInalyst took on itself.

### Что происходит под капотом

> *Пользователь с этим не работает напрямую — Платформа всё делает автоматически.*

AIналитик адаптирует свои вопросы и объяснения под нетехническую аудиторию: термины BABOK не используются в диалоге, но методология соблюдается полностью. Под капотом задействованы те же инструменты что и в работе профессионального BA: `planning_mcp` формирует реестр стейкхолдеров (задача 3.2), `future_state_mcp` валидирует бизнес-цели по критериям SMART (задача 6.2), `requirements_traceability_mcp` инициализирует репозиторий и строит граф трассировки (задача 5.1). Разница только в том, что AIналитик берёт на себя функцию методолога — сам предлагает следующий шаг, объясняет зачем это нужно и адаптирует глубину погружения под собеседника.

---

## UC-08 — Impact Analysis при внезапном Change Request

> **Для кого:** Бизнес-аналитики на активных проектах
> **Боль:** Change Request «звучит просто» — но за ним тянется половина артефактов проекта, и никто этого не видит до разработки
> **Фичи:** BFS-обход графа трассировки, скоринг CR (задачи 5.1 + 5.4)

### Ситуация

A logistics company. The project: a route management system. Work is on track, everything on schedule. Then the commercial director sends BA Andrew a short message: "We need to add real-time CO2 emissions calculation for each route, for the ESG report. That's simple, right?"

At first glance, a small addition. But Andrew is experienced enough to be wary. "Simple" from a stakeholder's mouth is one of the most dangerous signals in requirements management.

Он открывает Платформу.

### What Andrew does

> **Andrew:** Open a change request: the commercial director wants to add real-time CO2 emissions calculation for each route. Says it's simple.

### Как отвечает AIналитик

---

> **AIналитик:** CR-011 создан. Запускаю impact analysis по графу трассировки...
>
> **Затронутые артефакты (11):**
>
> — FR-022 (расчёт стоимости маршрута) — прямая зависимость. CO₂ нужно считать на тех же данных о маршруте, что и стоимость. Изменение логики расчёта может затронуть FR-022.
> — NFR-003 (производительность: отклик API не более 500 мс) — ⚠️ **конфликт**. Расчёт CO₂ в реальном времени требует обращения к внешнему API эмиссий. Это добавляет минимум 200-400 мс к каждому запросу. NFR-003 окажется под угрозой.
> — ADR-002 (архитектурное решение: кэширование данных о маршрутах) — нужен пересмотр. Кэшированные данные не подходят для расчёта CO₂ в реальном времени.
> — TC-014, TC-015, TC-017 (три тест-кейса) — потребуют обновления.
> — *(ещё 5 артефактов второго уровня зависимости)*
>
> **Оценка CR:**
> Score: 5.8 — **Modify** (принять с условием).
>
> Рекомендация: принять CR-011, но изменить требование — убрать «реальное время». CO₂ считается асинхронно и доступен при следующем открытии маршрута. Это снимает конфликт с NFR-003 и не требует пересмотра ADR-002.
>
> Вынести на согласование с коммерческим директором?

> **Andrew:** Yes. And prepare the arguments for why real time isn't possible without consequences.

> **AIналитик:** Готово. Аргументы для встречи:
>
> Реальное время означает обращение к внешнему API при каждом открытии маршрута. Сейчас система обрабатывает до 800 запросов в минуту в пиковые часы. Добавление внешнего вызова увеличит среднее время отклика с текущих 320 мс до расчётных 680-900 мс — это нарушает SLA, согласованный с клиентами в NFR-003.
>
> Асинхронный вариант: CO₂ пересчитывается в фоне раз в 15 минут. Для ESG-отчёта это абсолютно достаточно — отчёты формируются раз в квартал.

---

### What Andrew gets

Он приходит к коммерческому директору не с отказом, а с данными и альтернативой. Разговор из «вы не хотите делать» превращается в «вот почему именно так и как мы это реализуем». CR принят — но в варианте, который не создаёт технического долга.

И важное: никто не «забыл» про три тест-кейса и архитектурное решение по кэшированию. Они в списке затронутых артефактов — их обновят до начала разработки, а не после.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

MCP-сервер задачи 5.4 (`requirements_assess_changes_mcp`) при получении CR выполняет обход графа трассировки в `traceability_repo.json` по алгоритму BFS (поиск в ширину) — находит все артефакты, связанные с изменяемыми требованиями, включая зависимости второго и третьего уровня. Инструмент `score_cr` присваивает оценку на основе количества затронутых артефактов, наличия конфликтов с NFR и сложности изменений. Статусы всех затронутых требований обновляются автоматически — помечаются как «требуют проверки в связи с CR-011». Результат сохраняется в Decision Log через `elicitation_collaborate_mcp`.

---

## UC-09 — Три метода приоритизации под разный контекст

> **Для кого:** Бизнес-аналитики на проектах с конкурирующими требованиями
> **Боль:** Приоритизация делается «по ощущениям» или превращается в политический торг — без защищаемого результата
> **Фичи:** MoSCoW, WSJF, Impact/Effort Matrix (задача 5.3)

### Ситуация

One tool, three fundamentally different scenarios. BA Rachel works on three projects at once. Each has its own audience, its own constraints, its own expectations for prioritization.

**Проект A:** Внутренний HR-инструмент, 25 требований, три стейкхолдера, дедлайн — через две недели. Нужно быстро.

**Проект B:** Продуктовая Agile-команда, 60 требований в backlog, нужно числовое ранжирование — чтобы у каждого требования был score и команда понимала порядок.

**Проект C:** Завтра воркшоп с тремя директорами. Аудитория нетехническая, числа отпугнут, нужно что-то наглядное на час.

### Проект A — MoSCoW за 20 минут

> **Rachel:** I need to prioritize 25 requirements for the HR tool. Three stakeholders, deadline in two weeks. Fast.

> **AIналитик:** Рекомендую MoSCoW — самый быстрый метод для небольшого набора с жёстким дедлайном. Запускаю сессию приоритизации. Буду называть требования по одному — скажи для каждого: Must / Should / Could / Won't.

*Через 20 минут — матрица MoSCoW с обоснованием и артефактом для стейкхолдеров.*

### Проект B — WSJF для Agile-команды

> **Rachel:** For the content management project I need numeric prioritization. 60 requirements, we work in Scrum, need a score for each.

> **AIналитик:** Рекомендую WSJF (Weighted Shortest Job First) — стандарт для SAFe и Agile-команд, даёт числовой score на основе бизнес-ценности, time-criticality и риска. Для 60 требований это оптимально.
>
> По каждому требованию нужно оценить три параметра от 1 до 10: Business Value, Time Criticality, Risk Reduction. Начинаем? Можем делать блоками по 10 — удобнее чем всё сразу.

*По итогу — ранжированный backlog с WSJF-score, готовый к загрузке в Jira.*

### Проект C — воркшоп с директорами

> **Rachel:** Tomorrow there's a workshop with three directors to prioritize product features. Non-technical audience, an hour max, needs to be visual, no formulas or numbers.

> **AIналитик:** Рекомендую Impact/Effort Matrix. Два измерения, никакой математики — директора сами расставляют фичи на поле «высокий/низкий impact» vs «высокий/низкий effort». Интуитивно понятно, вовлекает всех.
>
> Подготовлю материалы для воркшопа: список всех требований с описаниями на бизнес-языке, без технического жаргона. Готово — можешь распечатать или вынести на экран.

На следующий день после воркшопа:

> **Rachel:** Entering the workshop scores: FR-001, high impact, low effort; FR-007, high impact, high effort; FR-019, low impact, high effort...

> **AIналитик:** Строю матрицу...
>
> ⚠️ **Dependency violation обнаружен:**
> FR-019 попал в квадрант «не делаем» (низкий impact, высокий effort). Но FR-004 («быстрые победы», высокий приоритет) имеет прямую зависимость от FR-019 — без него FR-004 реализовать невозможно.
>
> Варианты:
> — (А) Повысить приоритет FR-019 — принять как вынужденный
> — (Б) Пересмотреть FR-004 — убрать зависимость или перенести в следующий релиз
>
> Что решаем?

### What Rachel gets

На каждом проекте — метод под контекст, а не «всегда MoSCoW». И главное: dependency violation на Проекте C всплыл прямо на воркшопе, пока директора ещё в комнате — а не на планировании спринта, когда менять что-либо уже болезненно.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платорма всё делает автоматически.*

MCP-сервер задачи 5.3 (`requirements_prioritize_mcp`) запускает сессию с выбранным методом через `start_prioritization_session`. Для WSJF инструмент `run_aggregation` применяет influence-веса стейкхолдеров из реестра (задача 3.2) — оценки более влиятельных участников весят больше. При финализации матрицы `resolve_conflict` проверяет граф трассировки на dependency violations — запрещено оставлять в «не делаем» требование, от которого зависят требования с высоким приоритетом. Результат сохраняется через `save_prioritization_result`.

---

## UC-10 — RCA: три техники для одной проблемы

> **Для кого:** Бизнес-аналитики на этапе стратегического анализа
> **Боль:** Проекты решают симптомы, а не причины — и проблема возвращается через год в другом виде
> **Фичи:** «Пять почему», Fishbone, Дерево проблем (задача 6.1)

### Ситуация

Три разных проекта, три разных инструмента. Один принцип: платформа не навязывает технику — она подбирает подходящую под контекст.

**Контекст A — медцентр:** Пациенты жалуются на долгое ожидание результатов анализов. BA нужен быстрый ответ — у него 20 минут до встречи с главврачом.

**Контекст B — банк:** Растёт отток клиентов. Причины явно многофакторные: жалобы на сервис, технологии, конкурентов, процессы. Нужна полная картина.

**Context C, manufacturing:** Needs an argument for a 15-million-dollar budget committee. The directors want to see cause-and-effect logic.

### Контекст A — «Пять почему» за 20 минут

> **BA Ian:** I need to quickly figure out why patients are waiting so long for test results. I have 20 minutes.

> **AIналитик:** Запускаю «Пять почему» — самый быстрый метод для линейной проблемы.
>
> Почему пациенты долго ждут результаты?

> **Ian:** The lab enters results into the system late.

> **AIналитик:** Почему лаборатория поздно передаёт?

> **Ian:** Lab technicians enter data manually at the end of their shift, not right away.

> **AIналитик:** Почему вносят в конце смены?

> **Ian:** Because the data entry system only sits on one computer in the corner, it's inconvenient to walk over there after every test.

> **AIналитик:** Корневая причина: **инфраструктурное ограничение** — недостаточное количество точек ввода данных. Это не проблема мотивации или процесса.
>
> Бизнес-потребность BN-001: «Обеспечить лаборантам возможность вносить результаты немедленно после выполнения анализа».
>
> Зафиксировать?

*Two questions, and the root cause is found. Ian walks into the meeting with the chief physician with a concrete diagnosis, not a vague "we need to improve processes."*

### Контекст B — Fishbone для многофакторной проблемы

> **BA Olivia:** The bank is losing clients. The causes are definitely multifactorial, complaints about everything. We need the full picture.

> **AIналитик:** Для многофакторной проблемы рекомендую Fishbone (диаграмма Исикавы). Он структурирует причины по категориям и не даёт упустить целую ветку факторов.
>
> Предлагаю категории для банковского контекста: Сервис, Технологии, Процессы, Персонал, Продукт, Внешняя среда. Какие из них точно релевантны?

> **Olivia:** All six.

> **AIналитик:** Начнём с Технологий — там обычно самые конкретные факторы. Что ты знаешь о технологических проблемах?

> **Olivia:** Opening an account takes 4 days, there's no online application. The mobile app crashes on transfers above 100,000. There's no integration with the Faster Payments System.

> **AIналитик:** Зафиксировал три фактора в ветку Технологии. Переходим к Сервису?

*После заполнения всех шести веток:*

> **AIналитик:** Синтез: выделяется три группы корневых причин.
>
> **Технологический разрыв** — продукт отстаёт от рыночных стандартов по 5 из 8 ключевых параметров. Это объясняет 40% упоминаний в жалобах.
>
> **Процессная медлительность** — среднее время решения проблемы клиента 6.2 дня vs. 1.8 у лидера рынка.
>
> **Продуктовый пробел** — отсутствие кэшбека и накопительных программ при наличии их у трёх прямых конкурентов.
>
> Регистрирую три бизнес-потребности: BN-001, BN-002, BN-003. Перейдём к формулировке целевого состояния?

### Что получает BA

В обоих случаях — не просто список причин, а структурированная бизнес-потребность с идентификатором, которая автоматически становится корневым узлом графа трассировки. Все последующие требования проекта будут к ней привязаны — и в любой момент можно будет проверить: а это требование вообще решает ту проблему, ради которой затеяли проект?

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

The Task 6.1 MCP server (`current_state_mcp`) supports three modes through the `run_root_cause_analysis` tool: `five_whys`, `fishbone`, and `problem_tree`. AInalyst picks the mode based on context: number of factors, presence of organizational pressure, time constraints. When the analysis is done, `register_business_need` creates a BN-xxx record in `traceability_repo.json` as a root node of the graph, all subsequent business objectives and requirements will inherit traceability links from it.

---

## UC-11 — SMART-цели и GAP-анализ: от размытых намерений к защищаемым целям

> **Для кого:** Бизнес-аналитики на этапе определения будущего состояния
> **Боль:** Цели формулируются так, что непонятно достигнуты ли они — а GAP между «сейчас» и «хотим» никто не измерял
> **Фичи:** SMART-валидация бизнес-целей, GAP-анализ (задача 6.2)

### Ситуация

An EdTech company. A new LMS (learning management system) is launching. BA Chloe is starting the analysis phase, needing to record the future-state objectives.

Первая попытка формулировки — такая, какую обычно приносят с совещания по стратегии.

### What Chloe does

> **Chloe:** Recording the project objective: improve employee engagement in training.

### Как отвечает AIналитик

---

> **AIналитик:** ❌ Цель не прошла SMART-валидацию.
>
> Проблемы:
> — **Не измерима:** «улучшить вовлечённость» — как мы узнаем что достигли цели?
> — **Нет временного горизонта:** к когда?
> — **Нет базовой метрики:** что является отправной точкой?
>
> Попробуем переформулировать. Что сейчас измеряется в вашей системе обучения? Есть ли данные по completion rate или другим метрикам?

> **Chloe:** Yes, completion rate right now is 34%. We want 70% by year end.

> **AIналитик:** Новая формулировка: «Увеличить completion rate корпоративных обучающих программ с 34% до 70% к Q4 2026».
>
> ✅ SMART-проверка пройдена:
> — Specific: completion rate как метрика
> — Measurable: 34% → 70%
> — Achievable: рост на 36 п.п. за год — амбициозно, но реалистично при смене платформы
> — Relevant: напрямую связано с бизнес-потребностью BN-001
> — Time-bound: Q4 2026
>
> Зафиксировать как BG-001?

> **Chloe:** Yes. Now run gap analysis.

> **AInalyst:** Gap analysis completed — **lms_2026**
>
> **Elements analyzed:** 3
> **Current-state baseline:** ✅ from 6.1
>
> ---
>
> ## Technology and Infrastructure (`technology`)
>
> **Change type:** ⬆️ Improve
> **Complexity:** 🔴 High
>
> **Current state:** Desktop-only LMS, no mobile client...
> **Target state:** Responsive platform, full course completion from a phone...
>
> **Gap:** Current: Desktop-only LMS, no mobile client... → Target: Responsive platform, full course completion from a phone...
>
> ## Capabilities and Processes (`capabilities`)
>
> **Change type:** ⬆️ Improve
> **Complexity:** 🟡 Medium
>
> **Current state:** Content refreshed ad hoc, no review cycle...
> **Target state:** Mandatory annual review of every course...
>
> **Gap:** Current: Content refreshed ad hoc, no review cycle... → Target: Mandatory annual review of every course...
>
> ## Business Architecture (`architecture`)
>
> **Change type:** 🆕 New
> **Complexity:** 🟡 Medium
>
> **Current state:** *(no 6.1 data)*
> **Target state:** LMS ↔ HR system integration, progress visible in the employee profile...
>
> **Gap:** No current state — the element is being created from scratch. Target: LMS ↔ HR system integration...
>
> One gap card per future-state element you captured, each with a change type and a complexity rating. `technology` is the hardest of the three — hitting 70% isn't realistic without it. Pass this to the design phase as a basis for requirements?

---

### What Chloe gets

Instead of a vague "improve engagement," a concrete, measurable target and one clearly described gap per future-state element, each rated for how hard the change is. The gap analysis shows immediately: not everything needs fixing, and `technology` is where the effort sits.

И важное: BG-001 теперь зафиксирована в трассировочном репозитории. Когда в фазе design появятся требования к мобильному доступу — они автоматически будут привязаны к этой цели. В любой момент можно будет спросить: «какие требования работают на цель BG-001?» — и получить полный список.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

The Task 6.2 MCP server (`future_state_mcp`), when `define_goals_and_objectives` is called, runs the wording through a SMART check — a metric, a time horizon, a baseline, and a target value. An objective that fails is still **recorded**, marked `smart_validated: false`, and the weakness is named in the answer: the platform warns, it does not block, so a goal is never lost because its wording was not ready yet. Once objective BG-001 is in place, the `run_gap_analysis` tool compares the current and future states element by element — one gap card for each of the future-state elements captured, out of the eight BABOK defines — and returns them with a change type (`new` where there is no current state, `improve` where there is) and a complexity rating (low / medium / high). It assigns no gap IDs and no priorities: how big a gap is stays the analyst's judgement, recorded later as `gap_severity` in 6.4. The result is saved to `gap_analysis.json` and imported automatically in Task 6.4, where the platform reports which of those gaps the solution scope covers.

---

## UC-12 — Верификация требований: Junior BA работает как Senior

> **Для кого:** Junior BA, тимлиды, руководители практики бизнес-анализа
> **Боль:** Требования уходят в разработку «сырыми» — и проблемы формулировок вскрываются уже в тестировании
> **Фичи:** Проверка качества требований по 9 характеристикам BABOK (задача 7.2)

### Ситуация

Финтех-стартап. Роман работает бизнес-аналитиком чуть больше года. Он написал 40 требований к новому модулю оценки кредитоспособности — потратил на это неделю, несколько раз перечитал, остался доволен. Завтра планирует передать в разработку.

Перед передачей он решает прогнать через платформу.

### Что делает Роман

> **Роман:** Проверь качество требований по модулю кредитной оценки. Все 40 штук, файл requirements_credit_v3.md.

### Как отвечает AIналитик

---

> **AIналитик:** Проверяю 40 требований по 9 характеристикам BABOK...
>
> **Итог проверки:**
> — ✅ Корректных: 29 из 40
> — ⚠️ С замечаниями: 11 требований
>
> **Найденные проблемы по типам:**
>
> 🔴 **Ambiguity (6 случаев)** — размытые формулировки:
> FR-007: «Система должна быстро обрабатывать заявки». Что значит «быстро»? Нет измеримого критерия.
> FR-014: «Интерфейс должен быть удобным для пользователя». Неверифицируемо — каков критерий приёмки?
> *(ещё 4 требования)*
>
> 🟡 **Not Atomic (3 случая)** — одно требование содержит несколько несвязанных:
> FR-023: «Система должна рассчитывать кредитный рейтинг И отправлять уведомление И сохранять историю расчётов». Три разных требования в одном.
>
> 🟡 **Missing Acceptance Criteria (2 случая):**
> FR-031, FR-038 — требования корректные по формулировке, но нет ни одного критерия приёмки. Разработчик не поймёт когда считать задачу выполненной.

> **Роман:** Покажи как исправить FR-007.

> **AIналитик:** Исходный вариант:
> *«Система должна быстро обрабатывать заявки»*
>
> Проблема: «быстро» — субъективный критерий. Разработчик сделает «быстро» по своему пониманию, тестировщик проверит по своему.
>
> Исправленный вариант:
> *«Система должна рассчитывать кредитный рейтинг заявителя за не более чем 3 секунды с момента получения всех необходимых данных при стандартной нагрузке (до 100 одновременных запросов)»*
>
> Что изменилось: добавлена измеримая метрика (3 сек), условие измерения (стандартная нагрузка) и граничное значение (100 запросов). Это требование теперь верифицируемо.
>
> Исправить остальные 5 ambiguity-случаев в том же режиме?

---

### Что получает Роман

11 проблем, которые разработчики обнаружили бы в процессе реализации — каждая из которых превратилась бы в уточняющие вопросы, переписку, потерянное время и, возможно, переделку. Найдены за несколько минут до передачи, а не после.

Для Junior BA это не просто исправление конкретного документа. Разбор каждого случая — обучение на реальном материале: почему формулировка плохая и как должна выглядеть хорошая. После десяти таких сессий качество требований меняется на уровне привычки.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

The Task 7.2 MCP server (`requirements_verify_mcp`), when `check_req_quality` is called, checks each requirement against two groups of BABOK characteristics: Group A (atomic, unambiguous, verifiable, feasible, necessary) and Group B (prioritized, complete, consistent, traceable). Each problem gets a VI-xxx identifier in the verification tracker. After a fix, the BA marks the requirement via `mark_req_verified`, the status changes from `draft` to `verified`. Once all requirements are checked, `save_artifact` generates a Verification Report in `governance_plans/reports/`.

---

## UC-13 — Оценка готовности организации к изменениям

> **Для кого:** Бизнес-аналитики и PM на крупных трансформационных проектах
> **Боль:** Директор хочет запустить всё сразу — а организация объективно не готова. Но «я так чувствую» — не аргумент
> **Фичи:** Organizational Readiness Assessment, матрица вариантов изменения (задача 6.4)

### Ситуация

A pharmacy chain, 150 retail locations nationwide. The director of development, Hastings, has set the goal: roll out a new inventory management system across all locations at once by September 1. "Big bang." The team is afraid to push back, the director is used to fast results.

BA Вера понимает: что-то здесь не так. Прошлые крупные внедрения в компании заканчивались хаосом — но об этом не принято говорить открыто. У неё нет полномочий сказать «нет», но есть обязанность представить данные.

Она открывает AIналитик.

### Что делает Вера

> **Вера:** Нужно оценить готовность организации к изменениям по проекту внедрения WMS. Директор планирует big bang к 1 сентября, 150 точек одновременно. Хочу получить объективную картину.

### Как отвечает AIналитик

---

> **AIналитик:** Запускаю Organizational Readiness Assessment по шести измерениям. Буду задавать вопросы по каждому — отвечай от 1 до 5, где 1 — критически низко, 5 — полностью готовы.
>
> **Вовлечённость руководства.** Насколько топ-менеджмент активно поддерживает изменение — выделяет ресурсы, публично транслирует важность?

> **Вера:** 4 — директор лично инициировал проект, бюджет выделен.

> **AIналитик:** **Культурная готовность.** Как в компании обычно реагируют на изменения — персонал принимает новое или сопротивляется? Были крупные изменения за последние 2 года?

> **Вера:** 2 — люди привыкли работать по-старому, последнее внедрение CRM два года назад прошло тяжело, треть магазинов саботировала полгода.

> **AIналитик:** **История изменений.** Насколько успешно компания реализовывала крупные проекты трансформации раньше?

> **Вера:** 1 — честно говоря, ни один крупный проект не был завершён в срок и без потерь.

---

*После шести вопросов:*

---

> **AIналитик:** Итоговый Readiness Score: **2.4 / 5.0** — статус **Proceed with Caution**.
>
> Детализация по измерениям:
> — Вовлечённость руководства: 4/5 ✅
> — Культурная готовность: 2/5 ⚠️
> — История изменений: 1/5 🔴
> — Техническая зрелость: 2/5 ⚠️
> — Ресурсная готовность: 3/5 ✅
> — Коммуникационная зрелость: 2/5 ⚠️
>
> **Ключевой риск:** Высокая вовлечённость директора создаёт иллюзию готовности. Но культурное сопротивление + негативная история + низкая техническая зрелость — это три независимых фактора провала, каждый из которых в одиночку способен остановить big bang в точках.
>
> Сравниваю варианты стратегии изменения...

> **AIналитик:** **Анализ трёх вариантов:**
>
> **Вариант A — Big Bang (как планирует директор):**
> Скорость: максимальная. Риск: критический. При score 2.4 вероятность успеха big bang — менее 30% по историческим данным аналогичных внедрений.
>
> **Вариант B — Pilot First (рекомендуемый):**
> Запуск в 5-10 пилотных точках с разным профилем — разный регион, размер, опыт персонала. 2-3 месяца. По результатам пилота — корректировка и масштабирование.
>
> **Вариант C — Phased Rollout:**
> Волнами по 30-40 точек, каждые 6 недель. Риск ниже big bang, но выше пилота.
>
> **Взвешенная оценка:** Вариант B (Pilot First) набирает наивысший балл с учётом профиля рисков и текущей готовности. Срок достижения полного покрытия — декабрь 2026 вместо сентября. Разница: 3 месяца против высокой вероятности провала и повторного внедрения.
>
> Сформировать отчёт с обоснованием для директора?

> **Вера:** Да. И добавь в отчёт что нужно сделать до пилота — минимальный набор условий.

---

### Что получает Вера

Не «мне кажется, это рискованно», а структурированная оценка с баллами по шести измерениям, сравнительный анализ трёх вариантов и конкретная альтернатива с обоснованием. Теперь разговор с директором — не про страхи, а про данные.

И вторая ценность: если директор всё равно настоит на big bang — в Decision Log зафиксировано что риски были представлены, оценены и осознанно приняты. Это профессиональная страховка.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

The Task 6.4 MCP server (`change_strategy_mcp`), when `assess_enterprise_readiness` is called, collects scores across six standard dimensions and computes a weighted Readiness Score, change history and cultural readiness carry extra weight since they're the strongest predictors of failure. The `compare_strategy_options` tool builds a weighted matrix for each option against: speed, risk, cost, fit with the readiness profile. The result, with the recommended option, is saved to `{project}_change_strategy.json` and used when generating the final artifact via `save_artifact`.

---

## UC-14 — Один артефакт для пяти аудиторий

> **Для кого:** Бизнес-аналитики на проектах со сложной коммуникацией
> **Боль:** Каждую аудиторию нужно по-разному — директор не будет читать техспецификацию, юрист не поймёт User Stories, разработчик не нуждается в бизнес-обосновании
> **Фичи:** Коммуникационный пакет с адаптацией под роль (задача 4.4)

### Ситуация

Крупный ритейлер. Проект — новая система лояльности. BA Марина завершила набор требований: 12 подтверждённых функциональных требований, три NFR, два бизнес-правила. Хороший набор — теперь его нужно разослать заинтересованным сторонам.

Проблема: аудитории принципиально разные.

Директор по маркетингу хочет понять бизнес-ценность — и ничего больше. CTO хочет видеть интеграционные зависимости и архитектурные последствия. Тимлид разработки — конкретные пользовательские истории с критериями приёмки. QA-лид — перечень тестируемых условий. Юрист — только то, что касается GDPR и персональных данных.

Обычный путь — пять разных документов, пять отдельных сессий редактирования. Марина пробует другой.

### Что делает Марина

> **Марина:** Подготовь коммуникационный пакет по требованиям системы лояльности для пяти аудиторий: директор по маркетингу, CTO, тимлид разработки, QA-лид, юрист. Исходник — approved_requirements_loyalty_v2.md.

### Как отвечает AIналитик

---

> **AIналитик:** Читаю требования... Готово. Генерирую пять версий.
>
> **Версия 1 — Директор по маркетингу (бизнес-резюме, 1 страница):**
> Акцент: что получит бизнес, в каких метриках, к какому сроку. Технические детали исключены. Три ключевых тезиса: накопительная механика увеличивает retention на прогнозируемые 12-18%, персонализированные офферы запускаются автоматически, интеграция с мобильным приложением готова к Q3.
>
> **Версия 2 — CTO (технический обзор):**
> Акцент: интеграционные точки, зависимости от существующей инфраструктуры, NFR по производительности и безопасности. Приложен список открытых архитектурных вопросов, требующих решения до дизайна.
>
> **Версия 3 — Тимлид разработки (User Stories + AC):**
> 12 требований переформатированы в User Stories с полными критериями приёмки. Definition of Done по каждой истории. Зависимости между историями отмечены.
>
> **Версия 4 — QA-лид (тест-матрица):**
> Для каждого требования — тестируемые условия, позитивные и негативные сценарии, граничные значения. Формат готов к импорту в TestRail.
>
> **Версия 5 — Юрист (GDPR-срез):**
> Только требования, затрагивающие персональные данные: сбор, хранение, передача третьим лицам, срок хранения, механизм отзыва согласия. Для каждого — ссылка на соответствующую статью GDPR.
>
> Все пять документов сохранены в `governance_plans/reports/`. Хочешь сначала просмотреть какой-то конкретный?

> **Марина:** Покажи версию для юриста — хочу убедиться что ничего не пропустила.

> **AIналитик:** Показываю GDPR-срез.
> Найдено 4 требования с GDPR-релевантностью:
> — FR-003: сбор email и телефона при регистрации → ст. 6(1)(b) — согласие на обработку
> — FR-007: передача данных партнёрам для персонализированных офферов → ст. 28 — договор с обработчиком данных
> — FR-009: история покупок хранится 3 года → ст. 5(1)(e) — ограничение хранения
> — FR-011: удаление аккаунта → ст. 17 — право на забвение
>
> ⚠️ **Замечание:** FR-007 требует явного указания в пользовательском соглашении каких именно партнёров и с какой целью. В текущей формулировке это не специфицировано. Рекомендую уточнить до юридического согласования.

---

### Что получает Марина

Пять документов из одного исходника — за одну команду. Каждый адаптирован под язык и потребности аудитории. И дополнительно: платформа сама обнаружила потенциальную GDPR-проблему в FR-007, которую Марина могла не заметить при подготовке юридической версии.

Вместо полудня редактирования — несколько минут и пять готовых артефактов.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

MCP-сервер задачи 4.4 (`elicitation_communicate_mcp`) при вызове `prepare_communication_package` запускает пять параллельных генераций с разными `role`-параметрами: `executive`, `cto`, `dev_lead`, `qa_lead`, `legal`. Каждый профиль определяет фильтр релевантных требований, уровень детализации и формат вывода. Для юридического профиля дополнительно срабатывает GDPR-анализ — инструмент проверяет каждое требование на наличие маркеров персональных данных и сопоставляет со статьями регламента. После генерации `log_communication` фиксирует факт рассылки в журнал коммуникаций, `check_communication_schedule` проверяет не пропущен ли плановый срок по кому-то из адресатов.

---

## UC-15 — Повторное использование требований на новом проекте

> **Для кого:** Бизнес-аналитики в организациях с несколькими похожими проектами
> **Боль:** Каждый раз пишем одно и то же с нуля — авторизация, роли, уведомления, логирование. Хотя это уже делали трижды
> **Фичи:** Поиск и повторное использование требований (задача 5.2)

### Ситуация

Компания-разработчик корпоративного ПО. За три года реализовала три похожих проекта: портал для HR, внутренняя CRM и система документооборота. Каждый раз BA писал требования к авторизации, ролевой модели и системе уведомлений — заново, «с чистого листа».

Now a fourth project is starting: an employee self-service portal. BA Adam knows: authentication, roles, and notifications are coming again. He decides not to reinvent the wheel.

### What Adam does

> **Adam:** Starting a new project: self-service-portal-2026. Before writing requirements for authentication and the role model, check if there's anything reusable from past projects.

### Как отвечает AIналитик

---

> **AIналитик:** Ищу по тегу `authentication` и `authorization` в репозиториях hr-portal-2024, crm-internal-2024, docflow-2025...
>
> Найдено: 8 требований с тегом `authentication`.
>
> **По статусам:**
> — ✅ Approved: 6 требований
> — ⚠️ Approved with notes: 2 требования (есть замечания, требуют проверки актуальности)
>
> **Список:**
> — FR-AUTH-001: Система должна поддерживать SSO через корпоративный LDAP. Источник: hr-portal-2024. Статус: approved. Использовано в 2 проектах.
> — FR-AUTH-002: Сессия пользователя должна завершаться автоматически через 30 минут неактивности. Источник: crm-internal-2024. Статус: approved.
> — FR-AUTH-003: Попытки входа с неверным паролем блокируются после 5 неудачных попыток. Источник: hr-portal-2024. Статус: approved. Требование прошло security review.
> — *(ещё 5 требований)*
>
> По ролевой модели (`roles`, `rbac`) найдено ещё 11 требований. Показать?

> **Adam:** Yes. And tell me right away, of what you found, what can be added to the new project unchanged?

> **AIналитик:** Из 19 найденных требований:
>
> — **Добавить без изменений (13):** базовая авторизация, SSO, блокировка по попыткам, ролевые права чтения/записи, логирование входов. Они не зависят от специфики бизнес-процессов.
>
> — **Адаптировать перед использованием (4):** требования к ролям, специфичным для предыдущих доменов (например, «роль HR-менеджера» в hr-portal — неприменима напрямую, нужна адаптация).
>
> — **Не переиспользовать (2):** требования с замечаниями из security review 2024 года — архитектура изменилась, они устарели.
>
> Добавить 13 требований в репозиторий self-service-portal-2026 с сохранением ссылки на источник?

> **Adam:** Yes, add them.

> **AIналитик:** Готово. 13 требований добавлены в репозиторий self-service-portal-2026. Источник и версия сохранены для трассировки. Общая экономия: примерно 3-4 часа формулировок и согласований.
>
> Теперь можешь сосредоточиться на том, что действительно уникально для этого проекта.

---

### What Adam gets

Три-четыре часа работы, которую он уже делал — не делаются снова. 13 требований в новом репозитории с первой минуты, все прошедшие согласование на прошлых проектах. И важно: трассировка сохранена — если в будущем в исходном требовании обнаружится проблема, платформа уведомит о всех проектах где оно используется.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

MCP-сервер задачи 5.2 (`requirements_maintain_mcp`) при вызове `find_reusable_requirements` выполняет поиск по тегам и ключевым словам во всех репозиториях `traceability_repo.json`, доступных в рабочей директории платформы. Статус `approved` является фильтром — требования в статусе `draft` или `rejected` в результаты не попадают. При добавлении в новый репозиторий через `init_traceability_repo` каждое переиспользуемое требование сохраняет ссылку на источник (`source_project`, `source_id`), что обеспечивает двустороннюю трассировку: из нового проекта к исходному и обратно.

---

## UC-16 — Orphan-требования и управление допущениями

> **Для кого:** Бизнес-аналитики на проектах с «разросшимся» скоупом
> **Боль:** В репозитории копятся требования, которые непонятно зачем — и допущения, которые никто не проверял
> **Фичи:** Проверка бизнес-выравнивания, реестр допущений (задача 7.3)

### Ситуация

A large telecom. The project: a self-service portal for B2B clients: contract management, invoice viewing, support tickets. The repository has grown to 55 requirements. BA Stephanie suspects some of them appeared "along the way," with no link to real business objectives. And one critical assumption that nobody has verified is bothering her too.

### What Stephanie does

> **Stephanie:** Check business alignment for all 55 requirements on the b2b-portal-2026 project. I want to find orphan requirements, ones not linked to any business objective.

### Как отвечает AIналитик

---

> **AIналитик:** Запускаю проверку по графу трассировки...
>
> Из 55 требований — 7 orphan-требований (нет связи ни с одной бизнес-целью или бизнес-потребностью):
>
> — FR-041, FR-042, FR-043: требования к мобильному приложению. Мобильное приложение не входит в скоуп b2b-portal-2026 согласно ba_plan.json.
> — FR-047, FR-048: требования к биллинговой логике. Биллинг принадлежит системе ERP-billing — это чужой домен.
> — FR-033, FR-039: дублируют FR-011 и FR-019 с незначительными отличиями в формулировке.
>
> Рекомендации: первые пять — вынести за скоуп или передать в соответствующие проекты. Последние два — проверить и при подтверждении дубля удалить.
>
> Что делаем с каждым?

> **Stephanie:** Accepted for all seven. Now I want to log a critical assumption: we're assuming the ERP system supports a REST API for exporting invoice data. This hasn't been confirmed.

> **AIналитик:** Фиксирую допущение AS-001:
> «ERP-система (SAP версии x.x) поддерживает REST API и предоставляет endpoint для выгрузки данных о счетах по клиенту».
>
> Уровень риска: **high_risk** — если допущение окажется ложным, это блокирует реализацию FR-008, FR-012, FR-015, FR-021 (все требования к просмотру счетов, итого 4 требования напрямую зависят от этого API).
>
> ⚠️ **Предупреждение:** Валидация требований FR-008, FR-012, FR-015, FR-021 заблокирована до подтверждения AS-001. Рекомендую инициировать техническую консультацию с архитектором ERP до завершения фазы design.
>
> Назначить ответственного за верификацию допущения?

> **Stephanie:** Yes, owner is Grant (IT architect). Deadline: April 18.

---

### What Stephanie gets

Seven "extra" requirements removed before development, that's several days of developer work saved that wasn't needed. A critical assumption is logged, its risk assessed, and four dependent requirements are flagged "don't validate until confirmed." Grant knows what's expected of him and by when.

Если бы допущение не было зафиксировано — его, возможно, обнаружили бы в середине разработки, когда разработчик попытался бы вызвать несуществующий API.

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

The Task 7.3 MCP server (`requirements_validate_mcp`), when `check_business_alignment` is called, does a BFS traversal of the graph in `traceability_repo.json`, for each requirement looking for a path to a business-need root node. Requirements with no such path get the `orphan` status. When an assumption is logged via `log_assumption`, the tool automatically computes an impact_score, the number of requirements that depend on that assumption. If the score exceeds a threshold, or the risk level is `high_risk`, all dependent requirements are flagged `blocked_by_assumption`, and their status in the approval cycle is frozen until the assumption is verified.

---

## UC-17 — Финальная рекомендация спонсору с Value Score

> **Для кого:** Бизнес-аналитики, готовящие рекомендацию для высшего руководства
> **Боль:** «Мы рекомендуем вариант B» — звучит как мнение. А не как вывод из анализа
> **Фичи:** Взвешенная оценка вариантов решения, Recommendation Document (задача 7.6)

### Ситуация

Производственная компания. Текущая MES-система (управление производством) устарела: ломается, не интегрируется с новым оборудованием, поддержка вендора прекратится через год. Совет директоров ждёт рекомендацию: что делать.

BA Ian put together three options. Now he doesn't just need to choose, he needs to defend the choice in front of people who will ask uncomfortable questions.

**Option A, Build:** Build a custom system. Budget 40 million dollars, 18-month timeline.
**Option B, Buy SAP ME:** Purchase and implement an off-the-shelf solution. Budget 25 million dollars, 8-month timeline.
**Option C, Hybrid Odoo:** Implement Odoo customized for manufacturing specifics. Budget 18 million dollars, 12-month timeline.

### What Ian does

> **Ian:** I need to compare three options for replacing the MES and prepare a recommendation for the board. Options: Build (40M / 18 mo), SAP ME (25M / 8 mo), Hybrid Odoo (18M / 12 mo). Critical requirements: SCADA loop integration, compliance with Russian production accounting regulations, scalability to 3 new plants.

### Как отвечает AIналитик

---

> **AIналитик:** Запускаю оценку по пяти параметрам: Benefits, Strategic Alignment, Cost, Risk, Implementability. Начнём с ключевого ограничения.
>
> Ты упомянул интеграцию с SCADA-контуром как критическое требование. Уточни: есть ли у каждого варианта готовый коннектор или потребуется кастомная разработка?

> **Ian:** SAP ME, no ready connector for our SCADA. Needs custom development, that's +4-5 months and +8-10 million on top. Build, we write it ourselves, already included in the estimate. Odoo, there's a ready module, tested on a similar production line.

> **AIналитик:** Ключевое: это меняет картину по Варианту B. Реальные параметры SAP ME: бюджет 33-35 млн, срок 12-13 месяцев. Пересчитываю оценки...
>
> **Итоговая таблица Value Score:**
>
> | Параметр (вес) | Build | SAP ME (скорр.) | Hybrid Odoo |
> |---|---|---|---|
> | Benefits (×2.0) | 7.2 | 8.1 | 7.8 |
> | Strategic Alignment (×1.5) | 8.0 | 7.5 | 8.2 |
> | Cost (×1.5, инверт.) | 4.0 | 5.8 | 8.5 |
> | Risk (×1.0, инверт.) | 5.5 | 6.2 | 7.0 |
> | Implementability (×1.0) | 5.0 | 6.5 | 7.8 |
>
> **Итоговый Value Score:**
> — Build: 52.3
> — SAP ME (скорректированный): 61.4
> — **Hybrid Odoo: 73.1** ✅ Рекомендуется
>
> Hybrid Odoo лидирует несмотря на отсутствие бренда «SAP». Решающие факторы: готовый SCADA-коннектор снимает главный технический риск, стоимость на 40% ниже Build при сопоставимых benefits, и mitigation-план для Odoo проработан — для SAP ME этот риск остался бы открытым.
>
> Success metrics для фиксации до старта проекта:
> — OEE (Overall Equipment Effectiveness): цель +8% к Q4 2027
> — Время переналадки линии: −30% к Q2 2027
> — Интеграционные инциденты: не более 2 в месяц в первый год
>
> Сформировать Recommendation Document для совета директоров?

> **Ian:** Yes. And add a section on "what happens if we do nothing," for the directors who'll want to defer the decision.

---

### What Ian gets

Рекомендация с числами, которые можно проверить. Совет директоров видит не «мы думаем, что Odoo лучше», а взвешенную матрицу с формулой и параметрами, которые можно оспорить — и при необходимости пересчитать с другими весами прямо на встрече.

И важно: success metrics зафиксированы до начала разработки. Через полтора года, когда система заработает, будет понятно достигнут ли результат — и не будет споров «а что мы вообще планировали».

### Что происходит под капотом

> *Бизнес-аналитик с этим не работает напрямую — Платформа всё делает автоматически.*

The Task 7.6 MCP server (`value_recommend_mcp`), when `add_value_assessment` is called, records each option's parameters, then `compare_value` applies the weighted formula: Benefits×2.0 + Alignment×1.5 − Cost×1.5 − Risk_Penalty×1.0. Adjusting SAP ME's real parameters for SCADA is a change to the Cost and Risk inputs before running the formula, not an exclusion from consideration. The `save_recommendation` tool generates the final Recommendation Document: an options table, the rationale for the choice, success metrics with baseline and target values, and a risk section. The document is saved to `governance_plans/reports/` and is ready to hand to stakeholders.

---

## Заключение: почему это работает — и для кого

Reading all 17 scenarios above closely, one common thread stands out: in none of them does the business analyst type commands, recall tool names, or dig through documentation. Julia just talks about the project. Andrew describes the commercial director's request. Roman asks to "check the requirements." Ordinary human sentences, and the platform does the work.

Это не случайность и не маркетинговый приём. Это архитектурное решение.

### Как это устроено под капотом

Under the hood, AInalyst runs 21 specialized skills and 22 MCP servers with 114 tools, each of which "knows" a specific BABOK task: how to do it correctly, what to watch for, what artifact to produce.

Каждый скилл написан по строгой спецификации и содержит YAML-заголовок с триггерами — смысловыми паттернами, которые описывают когда именно этот скилл должен сработать. Когда бизнес-аналитик пишет что-то в чат, AIналитик анализирует запрос, сопоставляет его с триггерами, активирует нужный скилл — и тот вызывает соответствующие инструменты из MCP-серверов. Бизнес-аналитик не знает что именно произошло под капотом. Ему это и не нужно: он видит результат.

Именно поэтому один и тот же разговорный запрос «что происходит с этим стейкхолдером» запускает диагностику сигналов вовлечённости, а «сравни интервью» — кросс-анализ нескольких сессий выявления. Не потому что BA выбрал правильный инструмент, а потому что платформа сама знает какой инструмент здесь нужен.

### Что это даёт на практике

**Снижение когнитивной нагрузки.** Проект может идти месяцами — стейкхолдеры, решения, требования, условия согласования, история изменений. Удержать всё это в голове невозможно. AIналитик фиксирует каждый шаг и хранит контекст в структурированных артефактах. В любой момент можно спросить «что сейчас открыто по согласованиям» или «почему было принято вот это решение в марте» — и получить ответ немедленно. Не нужно поднимать переписку, листать папки, опрашивать коллег.

**Методологическая страховка.** BABOK — это 500 страниц структурированной экспертизы. Знать его «на зубок» не обязан никто, но работать по его принципам — значит делать работу правильно. AIналитик встроил эту экспертизу в процесс: он не даёт пропустить важный шаг, предупреждает о рисках, подсказывает следующее действие и вовремя напоминает о дедлайнах. BA, который плохо ориентируется в методологии, работает с платформой так же уверенно, как опытный специалист, — потому что платформа ведёт его по процессу.

### Для кого это сделано

Сценарии выше охватывают очень разную аудиторию — намеренно.

**Опытный бизнес-аналитик** получает инструмент, который снимает рутину: структурирует транскрипты, строит матрицы трассировки, генерирует коммуникационные пакеты для разных аудиторий. Он освобождает время для того, что действительно требует экспертизы, — анализа, интерпретации, принятия решений.

**Начинающий или менее методологически подготовленный BA** получает надёжного проводника. Платформа не осуждает за незнание BABOK — она просто помогает сделать правильно: задаёт нужные вопросы, объясняет почему формулировка не прошла валидацию, показывает как должно выглядеть хорошее требование.

**Продакт-менеджер или проджект-менеджер**, на чьём проекте нет выделенного BA, получает возможность работать по профессиональной методологии — не изучая её специально. Платформа адаптирует язык под собеседника и берёт на себя роль методолога, пока PM остаётся в своей зоне ответственности: знание продукта, рынка, команды.

**Стартапер или небольшая команда**, у которых нет бюджета на штатного аналитика, получают структурированную среду для работы с требованиями с первого дня — вместо того чтобы годами накапливать хаос в Notion и мессенджерах.

---

Разные роли, разный опыт, разный контекст. Одна платформа. Потому что в основе — не список функций, а принцип: **вы приносите знание о своём проекте и продукте, AIналитик берёт на себя всё остальное.**
