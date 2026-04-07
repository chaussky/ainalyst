# Value Assessment Guide — BABOK 7.6

## Суть задачи

Задача 7.6 (Analyze Potential Value and Recommend Solution) — финальная синтезирующая
задача Главы 7. BA оценивает потенциальную ценность каждого варианта дизайна (из 7.5)
и даёт официальную рекомендацию спонсору.

**Главная формула:** Ценность = Выгоды − Затраты − Риски

---

## Четыре легитимных исхода по BABOK

| Тип | Когда применять |
|-----|----------------|
| `recommend_option` | Один вариант явно превосходит остальные по Value Score и соответствует стратегии |
| `recommend_parallel` | Два варианта реализуются параллельно (пилот + основная разработка, A/B) |
| `recommend_reanalyze` | Ни один вариант не удовлетворяет требованиям — нужен новый раунд анализа |
| `no_action` | Выгоды не превышают затраты и риски; изменение не оправдано |

> ⚠️ Зрелый BA всегда рассматривает все четыре исхода, включая "ничего не делать".
> `no_action` — это не провал, а честная аналитика.

---

## Типы выгод

| Тип | Описание | Примеры |
|-----|----------|---------|
| `financial` | Прямой денежный эффект | Снижение затрат, рост выручки |
| `operational` | Эффективность процессов | Ускорение обработки, снижение ошибок |
| `strategic` | Стратегический позиционирование | Выход на новый рынок, конкурентное преимущество |
| `regulatory` | Соответствие требованиям | Снижение регуляторных рисков, соответствие GDPR |
| `user_experience` | Опыт пользователей | Удовлетворённость, Net Promoter Score |

---

## Типы затрат

| Категория | Описание |
|-----------|----------|
| `development` | Разработка и внедрение |
| `acquisition` | Покупка лицензий, оборудования |
| `maintenance` | Поддержка и сопровождение |
| `operations` | Операционные расходы |
| `resources` | Найм, обучение персонала |
| `opportunity` | Альтернативные издержки |

---

## Value Score — формула (ADR-043)

```
Value Score = (Benefits_Score × 2.0) + (Alignment_Score × 1.5)
            - (Cost_Score × 1.5) - (Risk_Penalty × 1.0)
```

### Маппинг качественных оценок

**Benefits (magnitude × confidence):**
- magnitude: Low=1 / Medium=2 / High=3
- confidence: Low=0.5 / Medium=1.0 / High=1.5
- Benefits_Score = среднее взвешенное (magnitude × confidence) по всем выгодам

**Costs:**
- magnitude: Low=1 / Medium=2 / High=3
- Cost_Score = среднее magnitude по всем cost_items всех компонентов

**Alignment:**
- Alignment_Score = доля бизнес-целей из 7.3, поддерживаемых improvement_opportunities варианта
- Диапазон: 0.0–1.0

**Risks:**
- risk_level: Low=0 / Medium=1 / High=2 / Critical=3
- Risk_Penalty = максимальный risk_level среди всех рисков варианта

### Пороги интерпретации (информационные, не блокирующие)

| Score | Интерпретация |
|-------|--------------|
| ≥ 8.0 | ✅ Сильная рекомендация |
| 5.0–7.9 | 🟡 Условная рекомендация |
| 2.0–4.9 | ⚠️ Требует пересмотра |
| < 2.0 | ❌ Не рекомендуется |

---

## Пайплайн 7.6

```
add_value_assessment(OPT-001) →
add_value_assessment(OPT-002) →
[add_value_assessment(OPT-003)] →
compare_value() →
[check_value_readiness()] →
save_recommendation()
```

### Шаг 1: add_value_assessment
Вызывается отдельно для каждого варианта. Идемпотентен по option_id.
Читает risks.json если существует (из задачи 6.3).

### Шаг 2: compare_value
Автоматическая Value Score матрица. Определяет winner по формуле.
Результат сохраняется в секцию `comparison` файла recommendation.json.

### Шаг 3: check_value_readiness (опционально)
Pre-flight проверка: все ли варианты оценены, есть ли сравнение, учтены ли critical gaps.
Только информирует — не блокирует.

### Шаг 4: save_recommendation
Финальный Recommendation Document. Обязательный параметр `recommendation_type`.
`success_metrics` становятся baseline для Главы 8.

---

## Интеграции (все опциональны, graceful degradation)

| Источник | Файл | Что читает |
|----------|------|-----------|
| 7.5 Design Options | `{project}_design_options.json` | Список вариантов, improvement_opportunities |
| 7.3 Business Context | `{project}_business_context.json` | business_goals для Alignment_Score |
| 7.4 Architecture | `{project}_architecture.json` | critical gaps для check_value_readiness |
| 5.1 Traceability | `{project}_traceability_repo.json` | Статистика req (опционально) |
| 6.3 Risk Assessment | `{project}_risks.json` | Риски (читается если существует) |

---

## Выходные артефакты

| Файл | Назначение |
|------|-----------|
| `{project}_recommendation.json` | Машиночитаемое хранилище: assessments + comparison + recommendation |
| `7_6_recommendation_*.md` | Финальный Recommendation Document для спонсора |

### Куда передаётся Recommendation Document

| Направление | Цель |
|------------|------|
| → **6.4** Define Change Strategy | Финальная рекомендация как входной артефакт стратегии |
| → **Глава 8** Solution Evaluation | `success_metrics` становятся baseline для оценки |
| → **4.4** Communicate | Коммуникация решения стейкхолдерам |

---

## Типичные ошибки BA

1. **Оценивать только финансовые выгоды** — операционные и стратегические выгоды часто важнее
2. **Игнорировать `no_action`** — иногда лучшее решение — не внедрять ничего
3. **Не документировать confidence** — "мы уверены на 50% в выгоде" важно передать спонсору
4. **Пропускать риски** — отсутствие рисков в оценке = неполный анализ, не нулевые риски
5. **Не указывать success_metrics** — без baseline невозможно оценить результат в Главе 8
