---
name: future_state
description: >
  BABOK 6.2 skill — Define Future State (to-be). Use this skill when the BA wants
  to describe the target business state, set SMART objectives with KPIs, run a
  gap analysis, or capture constraints and potential value of the change.
  Triggers: "future state", "to-be", "objectives", "gap analysis",
  "constraints", "potential value", "SMART objectives", "define future state".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: Define Future State (BABOK 6.2)

## When to read this skill

Read this file when:
- The BA says "we need to describe the target state," "how it should be," "future state"
- The BA wants to set business objectives with KPIs
- The BA is running a gap analysis or describing the gap between as-is and to-be
- The request contains: "future state," "to-be," "objectives," "gap analysis,"
  "constraints," "potential value," "SMART objectives"

## What this task is about

BABOK 6.2 — Define Future State — describes where the organization is heading.

**Two key outputs:**
1. **Future state description** — 8 "how it should be" elements + SMART objectives with KPIs
2. **Gap analysis** — a structured comparison of the current and future states (input for 6.4)

**Why this matters:**
- Without a future state, there's no basis for evaluating design options in 7.5
- SMART objectives with KPIs give a baseline for measuring success in Chapter 8
- The gap analysis is a direct input for 6.4: the change strategy is built on an explicit gap
- Potential value in 6.2 is context for the detailed calculation in 7.6

---

## MCP tools (7)

| Tool | When to call |
|------------|----------------|
| `scope_future_state` | First step — analysis contract, what we're describing |
| `capture_future_state_element` | For each element in scope (iteratively) |
| `define_goals_and_objectives` | For each business objective with KPIs (SMART validation) |
| `capture_constraints` | For each constraint, by category |
| `run_gap_analysis` | After filling in all elements — an explicit artifact |
| `assess_potential_value` | Structured benefit assessment (input data for 7.6) |
| `check_future_state_completeness` | Before finalizing — coverage check |
| `save_future_state` | Final step — Markdown report + handoff to 7.3 |

> Note: `save_future_state` is the 8th call in the pipeline, but it's counted as
> part of the task's 7 core tools in the platform's tool listing.

---

## Workflow

### Step 1 — Scope (mandatory first)

Call `scope_future_state`. An explicit contract: what we're analyzing, at what depth.

**Questions for the BA:**
- Same elements as in 6.1, or expanding the scope? → elements_in_scope
- Level of detail: a strategic-level pass or deep elaboration? → analysis_depth
- Are there already known objectives from the sponsor? → known_goals

If 6.1 exists — the system automatically reads the current state scope as context.
This is the recommended starting point: the same elements, but now looking at "how it should be."

---

### Step 2 — Capturing data by element (iterative)

Call `capture_future_state_element` for each element.

**Order of work:**
1. Start with `business_needs` — which needs will be satisfied
2. Then `capabilities` — new / improved processes
3. Then `technology` — the target technology stack
4. As needed: `org_structure`, `policies`, `architecture`, `assets`, `external`

**UX pattern "past alongside future":**
If 6.1 data exists, the tool automatically shows the element's current state alongside.
Use this: the BA describes not "what to add" but "how it should ultimately be."

**Sign of a quality description:**
- Outcome-focused, not focused on the implementation process
- Has target metrics (`target_metrics`)
- Traced to a BN from 6.1 (`linked_business_needs`)
- Doesn't duplicate the current state

**Sign of a poor description:**
- "There will be a CRM system" — that's a solution, not a future state
- "Everything will be better" — no specifics
- Describes the implementation process rather than the target state

For more on the 8 elements, read `references/future_state_guide.md`

---

### Step 3 — Business objectives and KPIs

Call `define_goals_and_objectives` for each business objective.

**SMART validation (more detail: `references/future_state_guide.md`):**
- The tool checks the criteria and suggests improvements
- Each objective is linked to a BN from 6.1 → traceability `BN → BG → FR`
- The objective is registered as a `business_goal` node in the 5.1 repository

**Structure of `objectives_json`:**
```json
[
  {
    "title": "Reduce request processing time",
    "metric": "Processing time (hours)",
    "baseline": "8 hours",
    "target": "2 hours",
    "deadline": "2025-12-31"
  }
]
```

An objective without a measurable KPI isn't an objective. Help the BA find a metric.

---

### Step 4 — Constraints

Call `capture_constraints` for each constraint.

**Types:** `budget | time | technology | policy | resources | compliance | other`

**Why capture them explicitly:**
- In 7.5, design options are developed within the constraints
- Assumed constraints (`assumed`) need to be validated — they may turn out to be myths
- Unknown constraints = project risks

---

### Step 5 — Gap analysis (a separate, explicit tool)

Call `run_gap_analysis`.

**Important:** the gap analysis is a thinking tool, not a mechanical step.
The BA should run it deliberately after filling in all the elements.

Without 6.1 data: `current_description = null` — the gap is formulated based on future only.
With 6.1 data: the current and future states are automatically compared element by element.

The result (`{project}_gap_analysis.json`) is a **mandatory input for 6.4**.

Change types: `new | improve | eliminate | replace`
Complexity assessment: `low | medium | high`

For more detail: `references/future_state_guide.md` → "Gap analysis" section

---

### Step 6 — Potential value

Call `assess_potential_value`.

A qualitative assessment, without a formula. A structured list of benefits.
This is **context for 7.6**, not a replacement for it.

**Parameters:**
- `benefits_json` — a JSON list of benefits (type + magnitude + confidence + linkage)
- `investment_level` — a qualitative assessment of the investment level
- `value_summary` — a summary statement for communicating with the sponsor

For more on benefit types, magnitude, confidence: read `references/value_guide.md`

---

### Step 7 — Completeness check

Call `check_future_state_completeness` before finalizing.

What it checks:
- Are all in-scope elements filled in?
- Is there at least one objective with a KPI?
- Are BNs linked to objectives (if 6.1 exists)?
- Is there at least one constraint?
- Has the gap analysis been run?
- Is there a potential value assessment?

These are warnings, not blockers. The analyst decides whether to proceed.

---

### Step 8 — Finalization

Call `save_future_state`.

**Parameter `push_to_business_context`:**
- `false` (default) — only saves the 6.2 report
- `true` — prepares data for handoff to 7.3. The BA then calls:
  `set_business_context(from_strategy_project_id="project_id", ...)`
  and the data from the 6.2 objectives will pre-fill the business context for requirements validation

---

## Integration with other tasks

### Input: 6.1 → 6.2 (optional)

6.1 is **not required** for 6.2 to work — graceful degradation.
If 6.1 exists, the following is read automatically:
- `{project}_current_state_scope.json` → context for the 6.2 scope
- `{project}_business_needs.json` → BNs for tracing objectives
- `{project}_current_state.json` → current state for the gap analysis

### Output: 6.2 → 5.1 (objective traceability)

BG-xxx nodes are registered in the 5.1 repository with type `business_goal`.
End-to-end chain: `BN-001 → derives → BG-001 → satisfies → FR-001 → verifies → TC-001`

### Output: 6.2 → 6.4 (change strategy)

`{project}_gap_analysis.json` is a mandatory input for 6.4.
The change strategy is built on the explicit list of gaps and their types.

### Output: 6.2 → 7.3 (business context)

`set_business_context` in 7.3 accepts `from_strategy_project_id`.
When passed, it pre-fills business objectives and future_state from 6.1 + 6.2 data.
The older parameter `from_current_state_project_id` is deprecated but still works.

### Output: 6.2 → 7.6 (potential value)

`add_value_assessment` in 7.6, when 6.2 exists, reads benefits as pre-fill context.
The BA refines the qualitative assessments quantitatively — not starting from scratch.

---

## 6.2 artifacts

| File | Purpose |
|------|------------|
| `{project}_future_state_scope.json` | Contract: what we're analyzing |
| `{project}_future_state.json` | Elements, objectives, constraints, value, status |
| `{project}_future_state_goals.json` | Objectives and KPIs (+ registration in 5.1) |
| `{project}_gap_analysis.json` | Gap analysis — input for 6.4 |
| `6_2_future_state_{project}.md` | Human-readable report (REPORTS_DIR) |

---

## Reference files

Read when you need detail:

- **`references/future_state_guide.md`** — detailed description of the 8 elements, SMART criteria,
  gap analysis change types, constraint types and statuses, UX patterns

- **`references/value_guide.md`** — benefit types, magnitude/confidence, investment_level,
  benefits_json structure, common BA mistakes when assessing value
