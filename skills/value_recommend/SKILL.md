---
name: value_recommend
description: >
  BABOK 7.6 skill — Analyze Potential Value and Recommend Solution. Use this
  skill when the BA wants to assess the ROI of design options from 7.5, compare
  them by value, and produce a formal recommendation for the sponsor.
  Triggers: "value assessment", "analyze value", "solution recommendation", "ROI",
  "which option to choose", "potential value", "recommend a solution", "net value".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: Analyze Potential Value and Recommend Solution (BABOK 7.6)

## What this task is about

You help the BA assess the potential value of each design option from 7.5
and produce a formal recommendation for the sponsor.

**Value = Benefits − Costs − Risks**

This is the final task of Chapter 7. The output is a Recommendation Document, which
is handed to the sponsor for decision-making and to Chapter 8 (Solution Evaluation) as a baseline.

---

## Four legitimate outcomes

| Type | When |
|-----|-------|
| `recommend_option` | One option is clearly better |
| `recommend_parallel` | Two options are implemented in parallel |
| `recommend_reanalyze` | No option fits — a new analysis is needed |
| `no_action` | The change is not justified — benefits < costs + risks |

---

## Pipeline (standard)

```
1. add_value_assessment(OPT-001)   — assess each option
2. add_value_assessment(OPT-002)   — repeat for each
3. compare_value()                 — automatic scoring
4. [check_value_readiness()]       — optional pre-flight check
5. save_recommendation()           — final Recommendation Document
```

---

## When to read references/

Read `references/value_assessment_guide.md` when:
- The BA asks how to classify a benefit or cost type
- You need to explain the Value Score formula (ADR-043)
- The BA is unsure which `recommendation_type` to choose
- You need examples of success_metrics

---

## MCP tools

### `add_value_assessment`
Assess one design option: benefits, costs, risks.
- Idempotent on `option_id` — calling it again updates the assessment
- Reads `{project}_risks.json` if it exists (from 6.3)
- Called once for each option from 7.5

### `compare_value`
Automatic Value Score matrix across all options.
- Formula: Benefits×2.0 + Alignment×1.5 − Cost×1.5 − Risk_Penalty×1.0
- Reads business_context for Alignment_Score (optional)
- Outputs ranking and winner

### `check_value_readiness`
Optional pre-flight check before `save_recommendation`.
- Checks completeness of assessments and data correctness
- Informational only — does not block
- Useful for complex projects with 3+ options

### `save_recommendation`
Final Recommendation Document.
- Required parameter `recommendation_type` (Literal — 4 outcomes)
- `success_metrics_json` is required for `recommend_option` and `recommend_parallel`
- Generates `7_6_recommendation_*.md` via save_artifact

---

## Tips for the BA

- Start with `add_value_assessment` for each option before drawing conclusions
- `no_action` and `recommend_reanalyze` don't need `recommended_option_id`
- Success metrics must be measurable — "improve NPS" doesn't qualify, "NPS > 8" does
- Risks can be passed manually if the 6.3 file doesn't exist

---

## Task files

- Reads: `{project}_design_options.json` (7.5), `{project}_business_context.json` (7.3),
  `{project}_architecture.json` (7.4), `{project}_risks.json` (6.3, optional)
- Writes: `{project}_recommendation.json`, `7_6_recommendation_*.md`
