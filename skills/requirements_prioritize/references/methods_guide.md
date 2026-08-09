# Справочник: Методы приоритизации требований (BABOK 5.3)

## Four methods — when to choose which

| Метод | Лучше всего подходит | Требует от команды | Не подходит когда |
|-------|---------------------|--------------------|-------------------|
| **MoSCoW** | Agile, fixed deadline, well-understood scope | Stakeholder opinions only | Many dependencies, precise quantitative scoring needed |
| **WSJF** | SAFe, product teams, competing backlogs | Cost estimates from developers | No effort estimates, team unfamiliar with the method |
| **Impact/Effort** | Initial ranking, limited resources, visualization | Relative impact and effort estimates | Precise numeric calculation required |
| **Time Boxing / Budgeting** | Fixed deadline or fixed budget; second pass after Must Inflation | A cost/size estimate per requirement + the capacity | Capacity genuinely unknown; scope cannot be cut |

**Selection rule:**
- No cost estimates → **MoSCoW** or **Impact/Effort**
- Cost estimates available + Agile project → **WSJF**
- Need to quickly rank 30+ requirements → **Impact/Effort** first, then MoSCoW for Must candidates
- Complex Enterprise project with dependencies → **WSJF** + automatic dependency-violation check from 5.1
- Fixed deadline or fixed budget → **Time Boxing/Budgeting**
- Over 60% Must after a MoSCoW pass → **Time Boxing/Budgeting** as a second pass: the
  capacity, not the stakeholders, does the cutting

---

## Метод 1 — MoSCoW

### Четыре категории

| Категория | Смысл | Типичная доля в проекте |
|-----------|-------|------------------------|
| **Must** | Без этого проект не имеет смысла. Провал при отсутствии. | ≤ 60% |
| **Should** | Высокая ценность, но можно выпустить без в первой версии | 20–30% |
| **Could** | Желательно, реализуется если остаётся время и бюджет | 10–20% |
| **Won't** | Сознательно исключаем из текущей итерации (не «никогда») | любое количество |

### Шкала оценки
BA вводит одно из: `Must` / `Should` / `Could` / `Won't` — по каждому требованию, для каждого стейкхолдера.

### Агрегация при нескольких стейкхолдерах

**Правило по умолчанию (взвешенное голосование по influence):**

```
Взвешенная оценка = Σ (оценка_стейкхолдера × вес_influence)
Вес: High = 3, Medium = 2, Low = 1
```

Маппинг числовых оценок: Must=4, Should=3, Could=2, Won't=1

Итоговый порог:
- ≥ 3.5 → **Must**
- ≥ 2.5 → **Should**
- ≥ 1.5 → **Could**
- < 1.5 → **Won't**

### Типичные ошибки

- 🔴 **Must inflation** — более 60% требований в Must → сессия не работает, нужна повторная фасилитация
- 🔴 **Must зависит от Won't** → логическое противоречие, автоматически детектируется через 5.1
- 🟡 **«Won't» понят как «никогда»** → важно объяснить стейкхолдерам: Won't = «не в этой итерации»
- 🟡 **Пустая категория Could** → подозрительно, обычно означает что Should и Won't не разграничены

---

## Метод 2 — WSJF (Weighted Shortest Job First)

### Формула

```
WSJF = Cost of Delay ÷ Job Size

Cost of Delay (CoD) = Business Value + Time Criticality + Risk Reduction / Opportunity Enablement
```

**Принцип:** делаем сначала то, что приносит максимальную ценность за минимальное время.

### Четыре компонента

| Компонент | Что оценивается | Типичный вопрос стейкхолдеру |
|-----------|----------------|------------------------------|
| **Business Value (BV)** | Ценность для бизнеса при реализации | «Насколько это ценно для ваших целей?» |
| **Time Criticality (TC)** | Насколько ценность падает со временем | «Что будет если мы сделаем это на квартал позже?» |
| **Risk Reduction / OE** | Снижает риск или открывает возможности | «Это блокирует другие инициативы?» |
| **Job Size (JS)** | Усилия на реализацию (от разработчиков) | Предоставляет команда реализации |

### Шкалы (два варианта — выбирается перед сессией)

**Fibonacci (рекомендуется для опытных команд — как в SAFe):**
`1, 2, 3, 5, 8, 13` — относительные оценки, не абсолютные.
Ключевое: сначала выбирается эталонное требование = 3 (среднее), остальные оцениваются относительно него.

**Линейная (1–10) — проще для новых команд:**
`1` = минимально, `10` = максимально.
Минус: люди тяготеют к средним оценкам (5–7), теряется дифференциация.

### Интерпретация результата

```
WSJF > 5.0  → 🔴 Высокий приоритет — делать немедленно
WSJF 2.0–5.0 → 🟡 Средний приоритет
WSJF < 2.0  → 🟢 Низкий приоритет — делать когда освободятся ресурсы
```

*Пороги условные — важнее относительное ранжирование внутри набора требований.*

### Пример расчёта

| Требование | BV | TC | RR/OE | CoD | JS | WSJF |
|------------|----|----|-------|-----|----|------|
| FR-001 | 8 | 5 | 3 | 16 | 3 | **5.3** |
| FR-002 | 5 | 2 | 1 | 8 | 5 | **1.6** |
| FR-003 | 13 | 8 | 5 | 26 | 8 | **3.3** |

Порядок: FR-001 → FR-003 → FR-002

### Типичные ошибки

- 🔴 **Маленький Job Size = автоматически высокий WSJF** — нужно проверять: может «маленькое» требование реально крупное
- 🟡 **Job Size от BA, не от разработчиков** — оценки усилий должна давать команда реализации
- 🟡 **Все CoD одинаковые** — стейкхолдеры не дифференцировали, нужна повторная сессия

---

## Метод 3 — Impact/Effort Matrix

### Четыре квадранта (названия по умолчанию)

```
HIGH IMPACT
    │
    │  Big Bets          Quick Wins
    │  (высокий impact,  (высокий impact,
    │   высокий effort)   низкий effort)
    │
    ├───────────────────────────────── EFFORT
    │
    │  Thankless Tasks   Fill-ins
    │  (низкий impact,   (низкий impact,
    │   высокий effort)   низкий effort)
    │
LOW IMPACT
         HIGH EFFORT      LOW EFFORT
```

### Шкала оценки

**Impact** (ценность/влияние): `Low` / `Medium` / `High`
**Effort** (усилия/сложность): `Low` / `Medium` / `High`

### Маппинг квадрантов → приоритет (настраивается BA перед сессией)

**Дефолтный маппинг (рекомендуется как отправная точка):**

| Квадрант | Impact | Effort | Дефолтный приоритет MoSCoW |
|----------|--------|--------|---------------------------|
| Quick Wins | High | Low | Must |
| Big Bets | High | High | Should |
| Fill-ins | Low | Low | Could |
| Thankless Tasks | Low | High | Won't |

**Настраиваемый маппинг:** BA может изменить любое соответствие перед сессией.
Например, в регуляторном проекте Big Bets → Must (несмотря на высокий effort).

### Интерпретация при Medium

Если impact = Medium или effort = Medium — требование попадает в «серую зону».

Правило по умолчанию:
- Medium/Low → как High/Low для приоритизации
- Medium/High → как Low/High
- Medium/Medium → Must/Should на усмотрение BA (флагируется отдельно)

### Когда использовать как основной метод

- Команда не привыкла к числовым оценкам
- Нужно быстро расставить 30+ требований на воркшопе
- Визуализация для стейкхолдеров (матрица наглядна)
- Как первичный фильтр перед более точным MoSCoW/WSJF

---

## Method 4 — Time Boxing / Budgeting

BABOK 10.33.3 .3: prioritization "based on the allocation of a fixed resource".
Time boxing uses the amount of work the team can deliver in a period; budgeting uses
a fixed amount of money. The arithmetic is the same — only the unit differs.

### What it needs

| Input | Where it comes from |
|---|---|
| `capacity` + `capacity_unit` | The BA, when opening the session |
| `cost` per requirement | The team's estimate, supplied like any other score (e.g. as `stakeholder_id="DEV-TEAM"`) |
| `value` per requirement | Optional. Given → used; omitted → the requirement's current priority in the 5.1 graph |

`cost` is averaged across whoever supplied it **without** influence weighting — a size
estimate is a fact about the work, not an opinion. Where estimates disagree, the report
prints the spread instead of hiding it inside the average.

### How the box is filled

1. Requirements are ordered by value (Must → Should → Could → Won't), then cheapest
   first, then by id.
2. They are added while `cumulative + cost <= capacity`.
3. A requirement that does not fit is skipped, and **cheaper ones below it are still
   considered** — the report names every requirement that was skipped over, so the
   trade-off is visible rather than silent.

The box covers the **whole backlog**, not only what was scored: a requirement nobody
estimated is named explicitly rather than quietly missing from the document.

### What the result means

- **In the box** — the requirement keeps its own value label (a `Could` in the box
  stays `Could`: it was committed, but it is the bottom of the value order).
- **Cut** — `Won't`, in the literal MoSCoW sense of "won't have **this time**".
- **Not estimated** — no priority is written at all. A requirement with no cost
  cannot be placed in a capacity box, and calling it `Won't` would be a conclusion
  drawn from missing data.

### Dependencies

A requirement in the box that depends on a cut one makes the box infeasible. The
platform flags it as a dependency violation and leaves the decision to the BA — raise
the prerequisite's value, drop the dependent requirement, or decompose it. It does
**not** quietly pull prerequisites in: that would rewrite the value order the
stakeholders agreed, and the signed artefact would not show it.

### Common mistakes

- **Capacity taken from a plan instead of from history.** Use what the team actually
  delivered, not what was promised.
- **Costs from one optimistic voice.** Where estimates differ, the report prints the
  spread — a 3-vs-13 disagreement is a conversation, not an average.
- **Treating the box as a commitment for all time.** It is one period. Re-run it.

---

## Eight BABOK factors — mapping to the methods

| BABOK factor | MoSCoW | WSJF | Impact/Effort | Time Boxing |
|-------------|--------|------|---------------|-------------|
| Benefit | ✅ Business Value | ✅ BV component | ✅ Impact | ✅ the value ranking |
| Penalty | ✅ Must if the penalty is critical | ✅ RR/OE component | ✅ Impact | ⬜ via the value ranking only |
| Cost | ⬜ not accounted for | ✅ Job Size | ✅ Effort | ✅ **the fixed resource itself** |
| Risk | ⬜ partially | ✅ RR/OE component | ⬜ partially via Impact | ⬜ |
| Dependencies | ⚠️ needs manual check | ⚠️ needs manual check | ⚠️ needs manual check | ⚠️ needs manual check |
| Time sensitivity | ⬜ not accounted for | ✅ TC component | ⬜ not accounted for | ✅ the period is the constraint |
| Stability | ⬜ | ⬜ | ⬜ | ⬜ |
| Regulatory compliance | ✅ Must by default | ✅ high CoD | ✅ Must via mapping | ✅ Must by default |

**Conclusion:** dependencies and stability are not automatically accounted for by any of the methods.
That is exactly why the platform integrates 5.3 with the 5.1 repository and the 5.2 attributes:
dependencies and stability are checked **before** and **after** the priority calculation.

---

## Комбинированный подход

Для крупных проектов рекомендуется двухэтапная приоритизация:

**Этап 1 (быстрый):** Impact/Effort → отсеять Thankless Tasks, выделить Quick Wins

**Этап 2 (точный):** MoSCoW или WSJF → детально приоритизировать оставшиеся (исключая Won't из этапа 1)

Это сокращает число требований для детального анализа на 20–30%.
