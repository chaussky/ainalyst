---
name: change_strategy
description: >
  Скилл BABOK 6.4 — Определение стратегии изменения. Используй этот скилл когда
  BA завершил анализ текущего/будущего состояния и оценку рисков и готов определить
  стратегию: выбрать вариант изменения (big_bang/phased/pilot_first), оценить готовность
  организации, сравнить варианты по взвешенным критериям и зафиксировать скоуп решения.
  Триггеры: «стратегия изменения», «варианты решения», «скоуп», «готовность организации»,
  «compare options», «change strategy», «define solution scope», «transition states».
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: 6.4 — Define Change Strategy (Определение стратегии изменения)

**Глава BABOK:** 6 — Strategy Analysis  
**Задача:** 6.4 Define Change Strategy  
**MCP-сервер:** `skills/change_strategy_mcp.py`

---

## Зачем эта задача

6.4 — **кульминация Главы 6**. Это синтез всего что сделано в 6.1–6.3:
- Из 6.1: знаем текущее состояние и бизнес-потребности (BN-xxx)
- Из 6.2: знаем целевое состояние, цели (BG-xxx) и GAP-анализ
- Из 6.3: знаем риски (RK-xxx) и рекомендацию

Задача: сформировать **обоснованную стратегию перехода** — что делаем, как, в каком порядке.

**Ключевые выходы:**
- `{project}_change_strategy.json` — машиночитаемый контракт для 7.x, 8.x
- Markdown-отчёт — стратегический документ для спонсора

---

## Когда читать references

| Ситуация | Читай |
|----------|-------|
| Нужно выбрать тип стратегии (big_bang/phased/pilot_first) | `references/change_strategy_guide.md` §2, §9 |
| Непонятно как категоризировать capabilities | `references/change_strategy_guide.md` §3 |
| Нужно определить gap_severity | `references/change_strategy_guide.md` §4 |
| Спонсор не понимает что такое opportunity cost | `references/change_strategy_guide.md` §5 |
| Нужна помощь с критериями сравнения | `references/change_strategy_guide.md` §6 |
| Непонятно как нарезать фазы | `references/change_strategy_guide.md` §7 |
| Нужно оценить измерение готовности | `references/readiness_guide.md` §2 |
| Спонсор не задал позицию по готовности | `references/readiness_guide.md` §6 |
| Нужны отраслевые ориентиры readiness | `references/readiness_guide.md` §5 |

---

## Pipeline — 7 шагов

```
scope_change_strategy
      ↓
define_solution_scope
      ↓
assess_enterprise_readiness
      ↓
add_strategy_option × N    ← минимум 2: один реальный + do_nothing (автодобавляется)
      ↓
compare_strategy_options
      ↓
define_transition_states × N фаз
      ↓
save_change_strategy
```

---

## Шаг 1 — `scope_change_strategy`

**Что делает:** Инициализирует 6.4 + автоимпорт контекста из 6.1, 6.2, 6.3.

**Параметры:**
- `project_id` — тот же что в 6.1/6.2/6.3
- `change_type` — transformation / process_improvement / technology_implementation / regulatory_compliance / other
- `time_horizon_months` — целевой горизонт в месяцах
- `methodology` — agile / waterfall / hybrid
- `source_project_ids` — JSON-список project_id из 6.1/6.2/6.3 (для автоимпорта)

**Что возвращает:** Сводку импортированного контекста (BN, BG, RK) + подтверждение инициализации.
Автоматически добавляет OPT-000 (do_nothing) в список вариантов.

**Вопросы BA перед вызовом:**
> 1. Какой тип изменения — глубокая трансформация или точечное улучшение?
> 2. Есть ли жёсткий срок (регуляторный, контрактный)?
> 3. Agile, waterfall или гибридный подход в организации?

---

## Шаг 2 — `define_solution_scope`

**Что делает:** Формирует список capabilities с gap_severity и явные исключения из скоупа.

**Параметры:**
- `project_id`
- `capabilities_json` — JSON-массив объектов capability (см. формат ниже)
- `explicitly_excluded` — JSON-список того, что явно НЕ входит
- `scope_summary` — 2–3 предложения: что делаем и чего не делаем

**Формат capability:**
```json
{
  "name": "CRM система (базовый модуль)",
  "category": "technology",
  "description": "Замена текущей системы учёта клиентов",
  "gap_severity": "high",
  "gap_source": "6.2:gap_analysis",
  "in_scope": true
}
```

**Категории:** process / technology / data / people / org_structure / knowledge / location

**Вопросы BA:**
> 1. Что именно должна уметь организация после проекта, чего не умеет сейчас?
> 2. Что точно НЕ входит? (важно зафиксировать для предотвращения scope creep)
> 3. Можно ли сослаться на gap_analysis из 6.2? (тогда gap_source = "6.2:gap_analysis")

---

## Шаг 3 — `assess_enterprise_readiness`

**Что делает:** Оценивает 6 измерений готовности организации по шкале 1–5.
Вычисляет итоговый readiness_score и вердикт (ready / proceed_with_caution / not_ready).

**Параметры:**
- `project_id`
- `leadership_commitment` — 1–5 + `leadership_rationale`
- `cultural_readiness` — 1–5 + `cultural_rationale`
- `resource_availability` — 1–5 + `resource_rationale`
- `operational_readiness` — 1–5 + `operational_rationale`
- `technical_readiness` — 1–5 + `technical_rationale`
- `change_history` — 1–5 + `change_history_rationale`

**Интерпретация:**
- score ≥ 4.0 → `ready`
- 2.5–3.9 → `proceed_with_caution` (нужны подготовительные меры)
- < 2.5 → `not_ready` (сначала программа готовности)

**Если BA не знает как оценить измерение:** читай `references/readiness_guide.md` §6 для вопросов.

---

## Шаг 4 — `add_strategy_option` (повтори N раз)

**Что делает:** Добавляет вариант стратегии в реестр опций.

OPT-000 (do_nothing) добавлен автоматически на шаге 1. Добавляй реальные варианты (min 1).

**Параметры:**
- `project_id`
- `name` — название варианта
- `strategy_type` — big_bang / phased / pilot_first (не do_nothing — он уже есть)
- `investment_level` — high / medium / low
- `timeline_months` — срок реализации
- `linked_risks` — JSON-список RK-xxx, которые вариант снижает или усугубляет
- `risk_impact` — mitigates / exacerbates / neutral (для каждого варианта)
- `pros` — JSON-список преимуществ
- `cons` — JSON-список недостатков

**Сколько вариантов достаточно?** Минимум 2 реальных + do_nothing. Оптимально 3–4.

---

## Шаг 5 — `compare_strategy_options`

**Что делает:** Взвешенная матрица сравнения → winner (рекомендованный вариант) +
opportunity cost для отвергнутых + narrative.

**Параметры:**
- `project_id`
- `scores_json` — JSON-матрица оценок: `{"OPT-001": {"alignment_to_goals": 4, "risk_mitigation": 3, ...}}`
- `weights_json` — опционально переопределить дефолтные веса (сумма должна быть 100)
- `custom_criteria_json` — опциональные дополнительные критерии
- `opportunity_cost` — текст: что теряем, выбрав winner вместо остальных

**Дефолтные критерии и веса:**

| Критерий | Вес | Оцениваем |
|----------|-----|-----------|
| alignment_to_goals | 25% | Достижение BG из 6.2 |
| risk_mitigation | 20% | Снижение топ-рисков из 6.3 |
| cost | 20% | Инверсия стоимости |
| time_to_value | 15% | Скорость первой ценности |
| org_readiness_fit | 10% | Соответствие readiness_score |
| feasibility | 10% | Реализуемость |

**Твоя задача (Claude):** После вызова — написать narrative: почему winner победил,
с ссылками на конкретные данные (риски, цели, readiness).

---

## Шаг 6 — `define_transition_states` (повтори для каждой фазы)

**Что делает:** Описывает фазу перехода — что реализуется, что закрывается, что остаётся.

**Параметры:**
- `project_id`
- `phase_number` — номер фазы (1, 2, 3...)
- `phase_name` — название фазы
- `duration_months` — длительность
- `capabilities_delivered` — JSON-список capabilities реализуемых в этой фазе
- `gaps_closed` — JSON-список названий gaps закрытых после фазы
- `risks_remaining` — JSON-список RK-xxx рисков которые остаются после фазы
- `value_realizable` — описание ценности реализуемой к концу фазы

**Правило:** Каждая фаза должна давать standalone value — иначе пересмотри нарезку.

**Количество фаз:** Зависит от strategy_type:
- big_bang → 1 фаза
- phased → 2–5 фаз
- pilot_first → обычно 2–3: pilot + rollout + (опционально) scale

---

## Шаг 7 — `save_change_strategy`

**Что делает:**
- Сохраняет `{project}_change_strategy.json` в DATA_DIR (контракт для 7.x, 8.x)
- Генерирует Markdown-отчёт через `save_artifact()`
- Опционально: регистрирует solution в репозитории 5.1 как узел типа `solution`

**Параметры:**
- `project_id`
- `push_to_traceability` — True если ведёшь трассировку 5.1 (default: False)
- `traceability_project_id` — если репозиторий 5.1 под другим project_id

**При push_to_traceability=True:**
- Создаётся узел SOL-001 типа `solution`
- Связи: SOL-001 satisfies BG-xxx (для каждого business goal из 6.2)

**После сохранения — сообщи BA:**
1. Выбранная стратегия и обоснование
2. Путь к JSON (для 7.x)
3. Что нужно сделать с самыми низкими измерениями readiness перед стартом

---

## Быстрые ответы на типичные вопросы BA

**«Зачем рассматривать do_nothing?»**
BABOK требует явно обосновать почему бездействие хуже. Это делает решение защищаемым
перед советом директоров: «мы рассмотрели статус-кво — вот почему он неприемлем».

**«Сколько transition states нужно?»**
Для phased — 2–5. Больше 5 фаз часто говорят о нечётком скоупе или избыточной
детализации. Один transition state = big_bang.

**«Если readiness_score низкий — отменяем проект?»**
Нет — это сигнал. Либо меняем strategy_type на pilot_first/phased,
либо добавляем подготовительную фазу 0 (организационная готовность).

**«Где граница между 6.4 и 7.1?»**
6.4 определяет ЧТО (capabilities и скоуп) и КОГДА (фазы).
7.1 определяет КАК ИМЕННО — детальные требования к каждой capability.

---

## Связь с другими задачами

| Задача | Связь |
|--------|-------|
| ← 6.1 | Бизнес-потребности BN-xxx → контекст capabilities |
| ← 6.2 | BG-xxx + gap_analysis → capabilities и фазы |
| ← 6.3 | RK-xxx → linked_risks в опциях + risks_remaining в фазах |
| → 7.1 | solution_scope.capabilities → что специфицировать |
| → 7.4 | transition_states → архитектура требований по фазам |
| → 7.5 | selected_option + rejected → ограничения дизайна |
| → 7.6 | value_realizable по фазам → анализ потенциальной ценности |
| → 5.1 | push_to_traceability → узел solution + связи satisfies |
| → 8.x | transition_states + risks_remaining → baseline для Solution Evaluation |
