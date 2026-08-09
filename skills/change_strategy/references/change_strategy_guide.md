# change_strategy_guide.md — Руководство по определению стратегии изменения

## 1. Что такое стратегия изменения (BABOK 6.4)

Стратегия изменения — это **обоснованный выбор** того, как организация перейдёт
из текущего состояния (6.1) в целевое состояние (6.2), с учётом рисков (6.3)
и готовности организации.

Результат 6.4 — не просто «сделаем это так», а структурированный документ:
- **Solution Scope** — что именно входит в скоуп решения (capabilities)
- **Change Strategy** — из каких вариантов выбрали и почему
- **Transition States** — этапы перехода, что реализуется на каждом

---

## 2. Типы стратегий изменения

### big_bang
**Суть:** Переход за один раз — новое решение запускается полностью, старое выключается.

**Когда подходит:**
- Системы малого масштаба
- Высокая зависимость компонентов друг от друга (нельзя внедрить частично)
- Жёсткие регуляторные сроки
- Команда опытная, риски управляемы

**Преимущества:** Скорость, одна волна изменений, нет долгого co-existence
**Риски:** Высокий операционный риск, нет пути отступления

---

### phased
**Суть:** Поэтапный переход — функциональность и capability-блоки внедряются последовательно.

**Когда подходит:**
- Большие системы с независимыми функциональными блоками
- Организация с низкой change_history
- Нужно реализовывать ценность постепенно
- Финансирование приходит траншами

**Преимущества:** Управляемый риск, ранняя ценность, обратная связь после каждой фазы
**Риски:** Длительный период co-existence, усложнённая архитектура переходного состояния

---

### pilot_first
**Суть:** Сначала пилот на ограниченной аудитории → валидация → масштабирование.

**Когда подходит:**
- Высокая неопределённость в решении
- Нужна валидация гипотез до полного инвестирования
- Есть подходящая «безопасная» пилотная группа
- Инновационное или неопробованное решение

**Преимущества:** Минимальный риск, реальные данные до масштабирования
**Риски:** Более долгий путь к полной реализации, риск «вечного пилота»

---

### do_nothing
**Суть:** Не менять ничего — оставить текущее состояние как есть.

**Когда подходит:** Никогда (как выбранный вариант). Используется как **baseline**
для сравнения: что произойдёт если мы ничего не сделаем?

**Обязательный к рассмотрению по BABOK** — чтобы BA явно обосновал:
«Текущее состояние неприемлемо, потому что...»

---

## 3. Capability Categories

Capability — это **способность**, которую организация приобретёт в результате изменения.

| Категория | Что включает |
|-----------|-------------|
| `process` | Бизнес-процессы, workflows, регламенты |
| `technology` | Программные системы, инфраструктура, интеграции |
| `data` | Данные, аналитика, хранилища, качество данных |
| `people` | Знания, навыки, компетенции персонала |
| `org_structure` | Организационная структура, роли, ответственность |
| `knowledge` | Документация, база знаний, стандарты |
| `location` | Физические офисы, точки присутствия, логистика |

---

## 4. Gap Severity — от 6.2 к 6.4

В `define_solution_scope` каждый capability получает `gap_severity`:

| Уровень | Значение | Как это влияет на стратегию |
|---------|----------|-----------------------------|
| `none` | Capability уже есть | Может быть вне активного скоупа |
| `low` | Небольшой gap, несложно закрыть | Обычно в ранних фазах phased |
| `medium` | Значимый gap, требует усилий | Планируется в основных фазах |
| `high` | Критичный gap, сложно закрыть | Часто определяет структуру фаз |

**`gap_severity` is yours, not the platform's.** The 6.2 gap analysis is auto-imported
into 6.4, but it stores `complexity` — how hard the change is — and that is a different
question from how big the gap is. The two share the words low/medium/high and mean
different things, so the import never writes `gap_severity`. The saved Change Strategy
document prints 6.2's `complexity` next to your value on each capability's line,
labelled "effort, not gap size", and leaves the judgement to you.

`gap_source` names **which 6.2 element** this capability covers, and that declaration is
the only link between the two chapters — the platform never infers it from the category
(6.2's eight elements and 6.4's seven categories overlap on just two values):

- `6.2:technology`, `6.2:policies`, `6.2:capabilities`, … — the 6.2 element covered.
  Valid elements: `business_needs`, `org_structure`, `capabilities`, `technology`,
  `policies`, `architecture`, `assets`, `external`.
- `manual` — the BA determined it independently, without reference to a 6.2 element.
- `6.2:gap_analysis` — the legacy form. It names a source, not an element, and is still
  accepted; coverage for that capability is then reported as **uncheckable**, not as
  uncovered.

With the element named, `define_solution_scope` and the final Change Strategy document
both report: which analysed gaps are covered, which no in-scope capability declares,
which are deliberately left out of scope, how many capabilities could not be checked,
and which analysed elements are context rather than a capability target.
Where no gap analysis was imported, the platform says it did not check — it never
reports a count it cannot support.

Two of the eight valid elements, `business_needs` and `external`, are excluded from
that count and from the "no in-scope capability declares" line by default — they are
reported on a separate "Context elements" line instead. `business_needs` sits in every
one of 6.2's default element sets, and `external` describes outside influences; neither
is something a capability closes, so charging them against the denominator would
manufacture an accusation out of a vocabulary mismatch, not a real gap. A capability
whose `gap_source` explicitly names one of them overrides the default and pulls the
element back into the count — the analyst's declaration always outranks the platform's.

---

## 5. Opportunity Cost — почему это важно

**Определение:** Opportunity Cost варианта A = лучшее из того, от чего отказываемся, выбрав A вместо остальных вариантов.

**BABOK требует:** При выборе стратегии — явно зафиксировать что именно теряем,
отвергая альтернативы. Это делает решение защищаемым перед спонсором.

**Формат:**
> «Выбрав `phased` вместо `pilot_first`, мы отказываемся от возможности
> валидировать решение на реальных пользователях до полного внедрения.
> Принятое допущение: требования достаточно понятны и пилот не нужен.»

**Типичные ошибки BA:**
- «Мы выбрали вариант A потому что он лучше» — нет comparison
- Сравнение только по стоимости, без учёта time-to-value и risk
- Отвергнутые варианты упоминаются вскользь без обоснования

---

## 6. Weighted comparison criteria

Дефолтные критерии и их смысл:

| Критерий | Что оценивает | Дефолтный вес |
|----------|--------------|---------------|
| `alignment_to_goals` | Насколько вариант достигает business goals из 6.2 | 25% |
| `risk_mitigation` | Насколько вариант снижает топ-риски из 6.3 | 20% |
| `cost` | Инверсия уровня инвестиций (low cost = высокий балл) | 20% |
| `time_to_value` | Скорость получения первой ценности | 15% |
| `org_readiness_fit` | Соответствие readiness_score из оценки готовности | 10% |
| `feasibility` | Техническая и операционная реализуемость | 10% |

**Шкала оценки:** 1–5 (1=плохо, 5=отлично) по каждому критерию.
**Weighted Score** = Σ(оценка × вес / 100).

**Кастомные критерии:** можно добавить через `custom_criteria_json`.
Сумма весов (дефолтные + кастомные) должна быть 100%.

---

## 7. Transition States — структурированный план фаз

Transition State = промежуточное состояние на пути к целевому.

Каждая фаза должна отвечать на вопросы:
1. **Что capabilities реализуется** в этой фазе?
2. **Какие gaps закрываются** к концу фазы?
3. **Какие риски остаются** после фазы (из 6.3)?
4. **Какая ценность реализуема** к концу фазы (из 6.2)?

**Правило «каждая фаза = standalone value»:**
Если Фаза 1 не даёт самостоятельной ценности — это признак неправильной нарезки фаз.
Спонсор должен видеть ROI уже после первой фазы.

**Пример для phased-стратегии (CRM upgrade):**

| Фаза | Capabilities | Gaps closed | Value |
|------|-------------|-------------|-------|
| 1 (3 мес) | CRM базовый + интеграция с колл-центром | gap_crm_data | Операторы видят историю клиента |
| 2 (5 мес) | Аналитический модуль + автоматизация | gap_reporting | Сокращение ручной отчётности на 60% |
| 3 (4 мес) | Self-service + мобильный | gap_self_service | NPS +15 пунктов |

---

## 8. Solution Scope — что включать и что явно исключать

`explicitly_excluded` — это не «то что мы забыли», это **осознанные решения**.

**Зачем фиксировать исключения:**
- Предотвращает scope creep в Главе 7
- Устанавливает ожидания стейкхолдеров
- Создаёт основу для будущих фаз или отдельных инициатив

**Примеры хороших формулировок исключений:**
- «Миграция исторических данных из Archive_2015–2018 — вне скоупа: данные невостребованы»
- «Мобильное приложение для клиентов — вне скоупа: выделено в отдельную инициативу Q3»
- «Интеграция с партнёрскими API — вне скоупа до завершения фазы 2»

---

## 9. Когда выбрать каждую стратегию — матрица решений

| Фактор | big_bang | phased | pilot_first |
|--------|----------|--------|-------------|
| Масштаб | Малый / средний | Любой | Любой |
| Зрелость org_readiness | Высокая | Средняя | Любая |
| Неопределённость решения | Низкая | Средняя | Высокая |
| Зависимость компонентов | Высокая | Низкая | Средняя |
| Финансирование | Единовременное | Поэтапное | Поэтапное |
| Приоритет time-to-value | Не критичен | Важен | Важен |
| Наличие пилотной группы | Не нужна | Не нужна | Обязательна |

---

## 10. Downstream-контракт (что используют задачи 7.x и 8.x)

| Поле в JSON | Кто использует | Зачем |
|-------------|---------------|-------|
| `solution_scope.capabilities` | 7.1 | Что специфицировать |
| `change_strategy.transition_states` | 7.4 | Архитектура по фазам |
| `change_strategy.selected_option_id` | 7.5 | Ограничения дизайна |
| `change_strategy.options[].pros/cons` | 7.5 | Контекст отвергнутых альтернатив |
| `transition_states[].value_realizable` | 7.6 | Ценность по фазам |
| `transition_states[].risks_remaining` | 8.x | Baseline рисков для мониторинга |
