---
name: value_recommend
description: >
  Скилл BABOK 7.6 — Анализ потенциальной ценности и рекомендация решения. Используй
  этот скилл когда BA хочет оценить ROI вариантов дизайна из 7.5, сравнить их по
  ценности и сформировать официальную рекомендацию спонсору.
  Триггеры: «оценка ценности», «analyze value», «рекомендация решения», «ROI»,
  «какой вариант выбрать», «potential value», «рекомендовать решение», «net value».
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: Analyze Potential Value and Recommend Solution (BABOK 7.6)

## Суть задачи

Ты помогаешь BA оценить потенциальную ценность каждого варианта дизайна из 7.5
и сформировать официальную рекомендацию спонсору.

**Ценность = Выгоды − Затраты − Риски**

Это финальная задача Главы 7. Результат — Recommendation Document, который передаётся
спонсору для принятия решения и в Главу 8 (Solution Evaluation) как baseline.

---

## Четыре легитимных исхода

| Тип | Когда |
|-----|-------|
| `recommend_option` | Один вариант явно лучше |
| `recommend_parallel` | Два варианта реализуются параллельно |
| `recommend_reanalyze` | Ни один вариант не подходит — нужен новый анализ |
| `no_action` | Изменение не оправдано — выгоды < затрат + рисков |

---

## Пайплайн (стандартный)

```
1. add_value_assessment(OPT-001)   — оценить каждый вариант
2. add_value_assessment(OPT-002)   — повторить для каждого
3. compare_value()                 — автоматический скоринг
4. [check_value_readiness()]       — опциональная pre-flight проверка
5. save_recommendation()           — финальный Recommendation Document
```

---

## Когда читать references/

Читай `references/value_assessment_guide.md` когда:
- BA спрашивает как классифицировать тип выгоды или затрат
- Нужно объяснить формулу Value Score (ADR-043)
- BA не уверен какой `recommendation_type` выбрать
- Нужны примеры success_metrics

---

## MCP-инструменты

### `add_value_assessment`
Оценить один вариант дизайна: выгоды, затраты, риски.
- Идемпотентен по `option_id` — повторный вызов обновляет оценку
- Читает `{project}_risks.json` если существует (из 6.3)
- Вызывается по одному разу на каждый вариант из 7.5

### `compare_value`
Автоматическая Value Score матрица по всем вариантам.
- Формула: Benefits×2.0 + Alignment×1.5 − Cost×1.5 − Risk_Penalty×1.0
- Читает business_context для Alignment_Score (опционально)
- Выводит ranking и winner

### `check_value_readiness`
Опциональная pre-flight проверка перед `save_recommendation`.
- Проверяет полноту оценок и корректность данных
- Только информирует — не блокирует
- Полезна при сложных проектах с 3+ вариантами

### `save_recommendation`
Финальный Recommendation Document.
- Обязательный параметр `recommendation_type` (Literal — 4 исхода)
- `success_metrics_json` обязателен для `recommend_option` и `recommend_parallel`
- Генерирует `7_6_recommendation_*.md` через save_artifact

---

## Советы BA

- Начни с `add_value_assessment` для каждого варианта прежде чем делать выводы
- Для `no_action` и `recommend_reanalyze` не нужен `recommended_option_id`
- Success metrics должны быть измеримыми — "улучшить NPS" не подходит, "NPS > 8" — да
- Риски можно передать вручную если файл 6.3 не существует

---

## Файлы задачи

- Читает: `{project}_design_options.json` (7.5), `{project}_business_context.json` (7.3),
  `{project}_architecture.json` (7.4), `{project}_risks.json` (6.3, опционально)
- Пишет: `{project}_recommendation.json`, `7_6_recommendation_*.md`
