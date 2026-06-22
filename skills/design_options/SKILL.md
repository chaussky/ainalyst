---
name: design_options
description: >
  BABOK 7.5 skill — Define Design Options. Use this skill when the BA moves
  from requirements to implementation options: choosing a build/buy/hybrid approach,
  evaluating technical alternatives, describing trade-offs, and preparing a recommendation.
  Triggers: "design options", "build vs buy", "implementation options",
  "how to implement", "technical alternatives", "solution options".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL.md — BABOK 7.5 Define Design Options

## What this task is about

7.5 is the moment when the BA stops being a "needs recorder" and becomes a
**solution architect**. The task synthesizes everything accumulated in the project
and translates requirements into concrete implementation options.

Under BABOK v3 this task merged three tasks from v2:
- Determine Solution Approach (BA chooses Build/Buy/Hybrid)
- Assess Proposed Solution (BA evaluates options)
- Allocation Requirements (BA allocates requirements across releases)

**Task output → 7.6 Analyze Potential Value and Recommend Solution**

---

## Inputs (all optional — graceful degradation)

| File | Source | What we take from it |
|------|----------|-----------|
| `{project}_traceability_repo.json` | 5.1 | Graph of `depends` links for allocation |
| `{project}_prioritization.json` | 5.3 | Priorities (Must/Should/Could/Won't) for auto_suggest |
| `{project}_business_context.json` | 7.3 | Business objectives, Future State, constraints |
| `{project}_architecture.json` | 7.4 | Viewpoints, gaps, coverage matrix |
| `{project}_change_strategy.json` | 6.4 | Change type, scope, constraints |

---

## Pipeline

```
1. set_change_strategy          ← [optional] record the change strategy
2. create_design_option × N     ← create 2-3 options (Build / Buy / Hybrid)
3. allocate_requirements        ← allocate requirements to releases for each option
4. compare_design_options       ← compare options against criteria
5. save_design_options_report   ← final document → 7.6
```

---

## MCP tools

### 1. `set_change_strategy`
**When:** at the start of work on 7.5, if the Change Strategy hasn't been recorded yet.
**Fields:** `change_type` (technology/process/organizational/hybrid), `scope`, `constraints`, `timeline`
**Result:** `{project}_change_strategy.json`

---

### 2. `create_design_option`
**When:** for each solution option (usually 2-3 options).
**Idempotent:** calling again with the same `option_id` updates the option.

**Approaches:**
- `build` — develop from scratch
- `buy` — off-the-shelf solution / SaaS
- `hybrid` — combination

**Key fields:**
- `components_json` — list of solution components: `'["Backend API", "Web UI", "Database"]'`
- `improvement_opportunities_json` — array of improvement opportunities:
  `'[{"type": "efficiency", "description": "Automatic report generation"}]'`
  Types: `efficiency` / `information_access` / `new_capability`
- `effectiveness_measures_json` — success metrics: `'["Reduce processing time by 40%"]'`
- `vendor_notes` — for buy/hybrid approaches: vendor assessment, cost, constraints

**Reference:** `references/design_options_guide.md` — more on approaches and opportunity types

---

### 3. `allocate_requirements`
**When:** after creating the design options, for each option.
**What it does:** allocates requirements to releases v1 / v2 / out_of_scope.

**auto_suggest=True mode (recommended):**
- Reads priorities from the 5.1 repository (the `priority` field on each requirement)
- Must → v1, Should → v1/v2, Could → v2, Won't → out_of_scope
- Produces a suggestion — the BA confirms or overrides it

**Manual override via assignments_json:**
```json
[
  {"req_id": "FR-001", "version": "v1", "rationale": "Critical for MVP"},
  {"req_id": "FR-010", "version": "out_of_scope", "rationale": "Out of project scope"}
]
```

**Depends-conflict check:**
After confirmation — automatically checks the 5.1 graph.
If requirement A (v1) depends on requirement B (v2) → a warning is raised with a suggested fix.

---

### 4. `compare_design_options`
**When:** after creating and allocating all options.
**What it does:** builds a comparison matrix against criteria.

Default criteria: cost, speed, risk, requirements coverage, flexibility.
Custom criteria are passed via `criteria_json`.

**Result:** Comparison Document for stakeholders → 4.4

---

### 5. `save_design_options_report`
**When:** final step — all options have been described and compared.
**What it includes:** all options + allocation map + improvement opportunities + BA recommendation.

The `recommended_option_id` parameter is optional: the BA can give a preliminary view,
but the final solution recommendation belongs to task 7.6.

**Result:** the Design Options Report is saved via `save_artifact` (prefix `7_5_design_options`) → 7.6

---

## Typical workflow

**Context:** project "CRM system", 45 requirements in the 5.1 repository, prioritization completed in 5.3.

1. Record the change strategy:
   - `set_change_strategy(project_id="crm", change_type="technology", scope="Replace legacy CRM", constraints="Budget $200k, 12-month timeline")`

2. Create 3 options:
   - OPT-001 Build: in-house development
   - OPT-002 Buy: Salesforce
   - OPT-003 Hybrid: open-source CRM + custom modules

3. Run allocation for each option:
   - `allocate_requirements(project_id="crm", option_id="OPT-001", auto_suggest=True)`
   - Review the suggestion, supply overrides if needed

4. Compare the options:
   - `compare_design_options(project_id="crm")`

5. Save the final report:
   - `save_design_options_report(project_id="crm", recommended_option_id="OPT-003", notes="Hybrid offers the best cost/coverage ratio")`

---

## Task artifacts

| File | Format | Purpose |
|------|--------|-----------|
| `{project}_design_options.json` | JSON | Options + allocation (main file) |
| `{project}_change_strategy.json` | JSON | 6.4 surrogate |
| `7_5_design_options_*.md` | Markdown | Design Options Report → 7.6 |

---

## Reference materials

> Read `references/design_options_guide.md` when you need:
> - More detail on the Build/Buy/Hybrid approaches
> - BABOK Improvement Opportunity types
> - Comparison criteria and their weights
> - Allocation patterns
> - Vendor Assessment
