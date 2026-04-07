---
name: risk_assessment
description: >
  Скилл BABOK 6.3 — Оценка рисков. Используй этот скилл когда BA хочет собрать,
  структурировать и оценить риски проекта: провести risk matrix, определить tolerance,
  задать стратегии реагирования и сформировать рекомендацию для спонсора.
  Триггеры: «оценка рисков», «assess risks», «risk matrix», «риски проекта»,
  «вероятность и impact», «risk register», «толерантность к риску», «risk assessment».
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: 6.3 — Assess Risks (Оценка рисков)

**Глава BABOK:** 6 — Strategy Analysis  
**Задача:** 6.3 Assess Risks  
**MCP-сервер:** `skills/risk_assessment_mcp.py`

---

## Зачем эта задача

Риски — это неопределённость, которая **угрожает бизнес-целям**.
Цель 6.3: идентифицировать риски, оценить их полуколичественно (likelihood × impact),
спланировать ответные меры и дать спонсору обоснованную рекомендацию:
proceed / proceed with mitigation / do not proceed.

**Ключевые входы:**
- 6.1 `{project}_current_state.json` — корневые причины, бизнес-потребности
- 6.2 `{project}_future_state.json` — ограничения, gap-анализ
- 4.2 результаты выявления — риски, упомянутые стейкхолдерами
- Реестр стейкхолдеров 3.2 — для назначения owner

**Ключевые выходы:**
- `{project}_risk_assessment.json` — полный реестр рисков (→ 6.4)
- `{project}_risk_assessment_report.md` — отчёт для спонсора

---

## Когда читать references

| Ситуация | Читай |
|----------|-------|
| Нужна помощь с категоризацией или формулировкой риска | `references/risk_assessment_guide.md` |
| Непонятно как оценить likelihood/impact | `references/risk_assessment_guide.md` §2–3 |
| Спонсор не задал tolerance явно | `references/risk_tolerance_guide.md` §5 |
| Нужны отраслевые ориентиры | `references/risk_tolerance_guide.md` §4 |
| Непонятно что значит результат `run_risk_matrix` | `references/risk_assessment_guide.md` §10 |

---

## Pipeline — 7 шагов

```
scope_risk_assessment
      ↓
import_risks_from_context      ← опциональный, но рекомендуемый
      ↓
add_risk × N                   ← основной цикл, повторяй столько раз сколько рисков
      ↓
set_risk_tolerance
      ↓
run_risk_matrix
      ↓
generate_recommendation
      ↓
save_risk_assessment
```

---

## Шаг 1 — `scope_risk_assessment`

**Что делает:** фиксирует скоуп: тип инициативы, глубина анализа,
источники рисков, связь с проектами 6.1/6.2.

**Параметры:**
- `project_id` — тот же что в 6.1/6.2
- `initiative_type` — process_improvement / new_system / regulatory / cost_reduction / market_opportunity / other
- `analysis_depth` — quick (только High) / standard (H+M) / comprehensive (все)
- `source_project_ids` — список project_id из 6.1/6.2 для автоимпорта (опционально)
- `ba_notes` — дополнительный контекст

**Вопросы BA перед вызовом:**
> 1. Какой тип инициативы (см. initiative_type)?
> 2. Насколько глубоким должен быть анализ? (quick = час работы, comprehensive = полдня)
> 3. Есть ли уже заполненные артефакты 6.1 или 6.2 для этого проекта?

---

## Шаг 2 — `import_risks_from_context` (рекомендуется)

**Что делает:** сканирует артефакты 6.1, 6.2, 4.2 и предлагает черновики рисков.
Черновики имеют статус `draft` — BA решает какие подтверждать через `add_risk`.

**Параметры:**
- `project_id`
- `source_project_ids` — список project_id для сканирования

**Что делать с результатом:**
Инструмент вернёт список черновиков. Для каждого черновика:
- Хочешь добавить → вызови `add_risk` с данными черновика (возможно скорректировав)
- Не релевантен → просто пропусти

**Graceful degradation:** если артефакты 6.1/6.2 не найдены — продолжаем без них.

---

## Шаг 3 — `add_risk` (повтори для каждого риска)

**Что делает:** добавляет риск в реестр. Автоматически:
- Присваивает `risk_id` (RK-001, RK-002...)
- Вычисляет `risk_score = likelihood × impact`
- Устанавливает `status = identified`

**Обязательные параметры:**
- `project_id`
- `category` — strategic / operational / financial / technical / regulatory / people / external
- `source` — change / current_state / future_state / requirement / stakeholder / assumption / constraint
- `description` — формат «Если X, то Y»
- `likelihood` — 1–5 (см. references/risk_assessment_guide.md §2)
- `impact` — 1–5 (см. references/risk_assessment_guide.md §3)
- `response_strategy` — accept / mitigate / transfer / avoid

**Рекомендуемые параметры:**
- `likelihood_rationale` — обоснование оценки вероятности
- `impact_rationale` — обоснование оценки воздействия
- `mitigation_plan` — обязателен если strategy=mitigate
- `owner` — stakeholder_id из реестра 3.2

**Правило формулировки:** «Если [триггер/условие], то [последствие]»
Плохо: «Риск интеграции». Хорошо: «Если API legacy-системы не поддерживает нужные методы, то интеграция займёт на 6 недель больше».

**Сколько рисков достаточно?**

| Глубина | Минимум рисков |
|---------|---------------|
| quick | 3–5 |
| standard | 7–15 |
| comprehensive | 15–30 |

Качество важнее количества — лучше 7 хороших рисков чем 25 расплывчатых.

---

## Шаг 4 — `set_risk_tolerance`

**Что делает:** задаёт tolerance level и числовой порог High-рисков.

**Параметры:**
- `project_id`
- `tolerance_level` — risk_averse / neutral / risk_seeking
- `max_acceptable_score` — score ≥ этого = High risk (default: 15)
- `organization_context` — контекст (отрасль, тип)
- `sponsor_risk_appetite` — позиция спонсора (текст)

**Если спонсор не задал tolerance явно:** используй вопросы из
`references/risk_tolerance_guide.md` §5 для определения.

**Быстрый ориентир:**
- Банк / госсектор / фармацевтика → `risk_averse`, порог 10–12
- Коммерческая компания, стандартный проект → `neutral`, порог 15
- Стартап / digital-трансформация → `risk_seeking`, порог 18–20

---

## Шаг 5 — `run_risk_matrix`

**Что делает:** классифицирует риски по зонам (Low/Medium/High),
строит cumulative profile, готовит данные для рекомендации.

**Параметры:** только `project_id`

**Читай результат:**
- `high_risks_count` — количество рисков выше порога
- `total_score` — суммарная «тяжесть»
- `zones` — список рисков с зонами 🟢🟡🔴

**После вызова:** обязательно обсуди с BA топ-3 High-риска перед следующим шагом.

---

## Шаг 6 — `generate_recommendation`

**Что делает:** детерминированная логика определяет тип рекомендации,
Claude пишет narrative rationale (2–4 предложения с конкретными данными).

**Параметры:**
- `project_id`
- `potential_value_summary` — краткое описание ожидаемой ценности из 6.2
  (если 6.2 заполнена — подтянется автоматически)

**Типы рекомендаций:**

| Тип | Когда |
|-----|-------|
| `proceed_despite_risk` | Нет рисков выше порога |
| `proceed_with_mitigation` | Есть High-риски, mitigation возможен |
| `seek_higher_value` | Рисковый профиль не соответствует ожидаемой ценности |
| `do_not_proceed` | Критичные риски без возможности mitigation |

**Твоя задача (Claude):** написать 2–4 предложения rationale с конкретными цифрами.
Например: «Из 12 идентифицированных рисков 3 находятся в High-зоне (score 15–20).
Наиболее критичен риск интеграции (RK-007, score 20): рекомендуется провести прототипирование
в Sprint 0 до старта разработки. При выполнении mitigation-планов суммарный профиль
снижается с 94 до ~55 — проект может идти вперёд.»

---

## Шаг 7 — `save_risk_assessment`

**Что делает:**
- Сохраняет `{project}_risk_assessment.json` в DATA_DIR (вход для 6.4)
- Генерирует Markdown-отчёт через `save_artifact()`
- Опционально: регистрирует риски в репозитории 5.1 как узлы типа `risk`

**Параметры:**
- `project_id`
- `push_to_traceability` — True если ведёшь трассировку 5.1 (default: False)
- `traceability_project_id` — project_id репозитория 5.1 (если отличается)

**Когда push_to_traceability=True:**
- Каждый RK-xxx регистрируется как узел `risk` в репозитории 5.1
- Создаются связи типа `threatens`: RK-001 threatens BN-001 и т.д.

**После сохранения — сообщи BA:**
1. Путь к JSON (для 6.4 Define Change Strategy)
2. Путь к Markdown-отчёту (для спонсора)
3. Топ-3 приоритетных риска для немедленного действия

---

## Быстрые ответы на типичные вопросы BA

**«Сколько рисков нужно найти?»**
Достаточно чтобы покрыть основные угрозы целям проекта. Quick = 3–5,
standard = 7–15. Лучше меньше но с чёткими mitigation-планами.

**«Как выбрать между mitigate и avoid?»**
Avoid — если риск Critical (impact=5) и mitigation технически невозможен или
дороже потенциальной выгоды. В остальных случаях — mitigate с конкретным планом.

**«Нужно ли заполнять 6.1 и 6.2 перед 6.3?»**
Нет, 6.3 работает независимо. Но если 6.1/6.2 заполнены — `import_risks_from_context`
сэкономит время и не даст пропустить очевидные риски.

**«Что делать если спонсор говорит "у нас нет рисков"?»**
Используй `import_risks_from_context` — артефакты 6.1/6.2 почти всегда содержат
скрытые риски в ограничениях и gap-анализе. Покажи конкретные черновики.

---

## Связь с другими задачами

| Задача | Связь |
|--------|-------|
| ← 6.1 | RCA и бизнес-потребности → источники рисков |
| ← 6.2 | Ограничения и gaps → черновики рисков |
| ← 4.2 | risks_mentioned стейкхолдеров → черновики |
| → 6.4 | `{project}_risk_assessment.json` → вход Define Change Strategy |
| → 7.6 | Рисковый профиль учитывается при оценке ценности вариантов |
| → 5.1 | push_to_traceability=True → узлы risk + связи threatens |
