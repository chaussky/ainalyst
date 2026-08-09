# Value Assessment Guide — BABOK 7.6

## What this task is about

Task 7.6 (Analyze Potential Value and Recommend Solution) is the final synthesizing
task of Chapter 7. The BA assesses the potential value of each design option (from 7.5)
and gives a formal recommendation to the sponsor.

**Core formula:** Value = Benefits − Costs − Risks

---

## Four legitimate outcomes per BABOK

| Type | When to apply |
|-----|----------------|
| `recommend_option` | One option clearly outperforms the others on Value Score and aligns with strategy |
| `recommend_parallel` | Two options are implemented in parallel (pilot + main development, A/B) |
| `recommend_reanalyze` | No option satisfies the requirements — a new round of analysis is needed |
| `no_action` | Benefits do not exceed costs and risks; the change is not justified |

> ⚠️ A mature BA always considers all four outcomes, including "do nothing."
> `no_action` is not a failure — it's honest analysis.

---

## Benefit types

| Type | Description | Examples |
|-----|----------|---------|
| `financial` | Direct monetary effect | Cost reduction, revenue growth |
| `operational` | Process efficiency | Faster processing, fewer errors |
| `strategic` | Strategic positioning | Entering a new market, competitive advantage |
| `regulatory` | Compliance | Reduced regulatory risk, GDPR compliance |
| `user_experience` | User experience | Satisfaction, Net Promoter Score |

---

## Cost types

| Category | Description |
|-----------|----------|
| `development` | Development and rollout |
| `acquisition` | Purchasing licenses, equipment |
| `maintenance` | Support and upkeep |
| `operations` | Operating expenses |
| `resources` | Hiring, staff training |
| `opportunity` | Opportunity costs |

---

## Value Score — formula

```
Value Score = (Benefits_Score × 2.0) + (Alignment_Score × 1.5)
            - (Cost_Score × 1.5) - (Risk_Penalty × 1.0)
```

### Mapping qualitative ratings

**Benefits (magnitude × confidence):**
- magnitude: Low=1 / Medium=2 / High=3
- confidence: Low=0.5 / Medium=1.0 / High=1.5
- Benefits_Score = weighted average (magnitude × confidence) across all benefits

**Costs:**
- magnitude: Low=1 / Medium=2 / High=3
- Cost_Score = average magnitude across all cost_items of all components

**Alignment:**
- Alignment_Score = share of business goals from 7.3 supported by the option's improvement_opportunities
- Range: 0.0–1.0

**Risks:**
- risk_level: Low=0 / Medium=1 / High=2 / Critical=3
- Risk_Penalty = maximum risk_level among all risks of the option

### Interpretation thresholds (informational, non-blocking)

| Score | Interpretation |
|-------|--------------|
| ≥ 8.0 | ✅ Strong recommendation |
| 5.0–7.9 | 🟡 Conditional recommendation |
| 2.0–4.9 | ⚠️ Needs reconsideration |
| < 2.0 | ❌ Not recommended |

---

## 7.6 Pipeline

```
add_value_assessment(OPT-001) →
add_value_assessment(OPT-002) →
[add_value_assessment(OPT-003)] →
compare_value() →
[check_value_readiness()] →
save_recommendation()
```

### Step 1: add_value_assessment
Called separately for each option. Idempotent on option_id.
Reads risks.json if it exists (from task 6.3).

### Step 2: compare_value
Automatic Value Score matrix. Determines the winner by formula.
The result is saved into the `comparison` section of the recommendation.json file.

### Step 3: check_value_readiness (optional)
Pre-flight check: are all options assessed, is there a comparison, are critical gaps accounted for.
Informational only — does not block.

### Step 4: save_recommendation
Final Recommendation Document. Required parameter `recommendation_type`.
`success_metrics` become the baseline for Chapter 8.

---

## Integrations (all optional, graceful degradation)

| Source | File | What it reads |
|----------|------|-----------|
| 7.5 Design Options | `{project}_design_options.json` | List of options, improvement_opportunities |
| 7.3 Business Context | `{project}_business_context.json` | business_goals for Alignment_Score |
| 7.4 Architecture | `{project}_architecture.json` | critical gaps for check_value_readiness |
| 5.1 Traceability | `{project}_traceability_repo.json` | Requirement statistics (optional) |
| 6.3 Risk Assessment | `{project}_risks.json` | Risks (read if it exists) |

---

## Output artifacts

| File | Purpose |
|------|-----------|
| `{project}_recommendation.json` | Machine-readable store: assessments + comparison + recommendation |
| `7_6_recommendation_*.md` | Final Recommendation Document for the sponsor |

### Where the Recommendation Document goes next

| Direction | Purpose |
|------------|------|
| → **6.4** Define Change Strategy | Final recommendation as an input artifact for the strategy |
| → **Chapter 8** Solution Evaluation | `success_metrics` become the baseline for evaluation |
| → **4.4** Communicate | Communicating the decision to stakeholders |

---

## Common BA mistakes

1. **Assessing only financial benefits** — operational and strategic benefits are often more important
2. **Ignoring `no_action`** — sometimes the best decision is to implement nothing
3. **Not documenting confidence** — "we're 50% confident in this benefit" is important to convey to the sponsor
4. **Skipping risks** — absence of risks in the assessment means an incomplete analysis, not zero risk
5. **Not specifying success_metrics** — without a baseline, it's impossible to evaluate the outcome in Chapter 8
