---
name: change_strategy
description: >
  BABOK 6.4 skill — Define Change Strategy. Use this skill when the BA has
  completed the current/future state analysis and risk assessment and is ready
  to define the strategy: choose a change option (big_bang/phased/pilot_first),
  assess organizational readiness, compare options against weighted criteria,
  and lock down the solution scope.
  Triggers: "change strategy", "solution options", "scope", "organizational readiness",
  "compare options", "change strategy", "define solution scope", "transition states".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: 6.4 — Define Change Strategy

**BABOK chapter:** 6 — Strategy Analysis
**Task:** 6.4 Define Change Strategy
**MCP server:** `skills/change_strategy_mcp.py`

---

## What this task is about

6.4 is the **culmination of Chapter 6**. It synthesizes everything done in 6.1–6.3:
- From 6.1: we know the current state and business needs (BN-xxx)
- From 6.2: we know the future state and business goals (BG-xxx), and the gap analysis
  is auto-imported as **context** — the platform cannot judge how big a gap is, so you
  still set each capability's `gap_severity` yourself in `define_solution_scope`. Name
  the element there as `gap_source = "6.2:technology"` (the 6.2 element this capability
  covers), and the platform reports which analysed gaps no capability addresses.
  A bare `"6.2:gap_analysis"` or `"manual"` names no element: coverage is then reported
  as uncheckable rather than as uncovered.
- From 6.3: we know the risks (RK-xxx) and the recommendation

The task: build a **substantiated transition strategy** — what we're doing, how, and in what order.

**Key outputs:**
- `{project}_change_strategy.json` — machine-readable contract for 7.x, 8.x
- Markdown report — strategic document for the sponsor

---

## When to read the references

| Situation | Read |
|----------|-------|
| Need to choose a strategy type (big_bang/phased/pilot_first) | `references/change_strategy_guide.md` §2, §9 |
| Unclear how to categorize capabilities | `references/change_strategy_guide.md` §3 |
| Need to determine gap_severity | `references/change_strategy_guide.md` §4 |
| Sponsor doesn't understand opportunity cost | `references/change_strategy_guide.md` §5 |
| Need help with comparison criteria | `references/change_strategy_guide.md` §6 |
| Unclear how to slice the phases | `references/change_strategy_guide.md` §7 |
| Need to assess a readiness dimension | `references/readiness_guide.md` §2 |
| Sponsor hasn't stated a position on readiness | `references/readiness_guide.md` §6 |
| Need industry readiness benchmarks | `references/readiness_guide.md` §5 |

---

## Pipeline — 7 steps

```
scope_change_strategy
      ↓
define_solution_scope
      ↓
assess_enterprise_readiness
      ↓
add_strategy_option × N    ← minimum 2: one real option + do_nothing (auto-added)
      ↓
compare_strategy_options
      ↓
define_transition_states × N phases
      ↓
save_change_strategy
```

---

## Step 1 — `scope_change_strategy`

**What it does:** Initializes 6.4 + auto-imports context from 6.1, 6.2 (goals **and**
the gap analysis), 6.3.

**Parameters:**
- `project_id` — the same one used in 6.1/6.2/6.3
- `change_type` — transformation / process_improvement / technology_implementation / regulatory_compliance / other
- `time_horizon_months` — target horizon in months
- `methodology` — agile / waterfall / hybrid
- `source_project_ids` — JSON list of project_id values from 6.1/6.2/6.3 (for auto-import)

**What it returns:** A summary of the imported context (BN, BG, RK, 6.2 gap elements)
+ confirmation of initialization.
Automatically adds OPT-000 (do_nothing) to the list of options.

**Questions to ask the BA before calling:**
> 1. What type of change is this — a deep transformation or a targeted improvement?
> 2. Is there a hard deadline (regulatory, contractual)?
> 3. Agile, waterfall, or a hybrid approach in the organization?

---

## Step 2 — `define_solution_scope`

**What it does:** Builds the list of capabilities with gap_severity and the explicit scope exclusions.

**Parameters:**
- `project_id`
- `capabilities_json` — JSON array of capability objects (see format below)
- `explicitly_excluded` — JSON list of what is explicitly NOT included
- `scope_summary` — 2–3 sentences: what we're doing and what we're not

**Capability format:**
```json
{
  "name": "CRM system (base module)",
  "category": "technology",
  "description": "Replacement of the current customer management system",
  "gap_severity": "high",
  "gap_source": "6.2:technology",
  "in_scope": true
}
```

**Categories:** process / technology / data / people / org_structure / knowledge / location

**Questions to ask the BA:**
> 1. What exactly should the organization be able to do after the project that it can't do now?
> 2. What exactly is NOT in scope? (important to capture to prevent scope creep)
> 3. Which 6.2 element does this capability close? (then gap_source = "6.2:<element>",
>    e.g. "6.2:technology" — the eight valid elements are listed in
>    `references/change_strategy_guide.md` §4). If none, `"manual"`.

---

## Step 3 — `assess_enterprise_readiness`

**What it does:** Assesses 6 dimensions of organizational readiness on a 1–5 scale.
Computes the final readiness_score and verdict (ready / proceed_with_caution / not_ready).

**Parameters:**
- `project_id`
- `leadership_commitment` — 1–5 + `leadership_rationale`
- `cultural_readiness` — 1–5 + `cultural_rationale`
- `resource_availability` — 1–5 + `resource_rationale`
- `operational_readiness` — 1–5 + `operational_rationale`
- `technical_readiness` — 1–5 + `technical_rationale`
- `change_history` — 1–5 + `change_history_rationale`

**Interpretation:**
- score ≥ 4.0 → `ready`
- 2.5–3.9 → `proceed_with_caution` (preparatory measures needed)
- < 2.5 → `not_ready` (readiness program first)

**If the BA doesn't know how to assess a dimension:** read `references/readiness_guide.md` §6 for questions.

---

## Step 4 — `add_strategy_option` (repeat N times)

**What it does:** Adds a strategy option to the options registry.

OPT-000 (do_nothing) is added automatically in step 1. Add the real options (min 1).

**Parameters:**
- `project_id`
- `name` — option name
- `strategy_type` — big_bang / phased / pilot_first (not do_nothing — it already exists)
- `investment_level` — high / medium / low
- `timeline_months` — implementation timeline
- `linked_risks` — JSON list of RK-xxx that the option mitigates or worsens
- `risk_impact` — mitigates / exacerbates / neutral (for each option)
- `pros` — JSON list of advantages
- `cons` — JSON list of disadvantages

**How many options are enough?** At least 2 real options + do_nothing. 3–4 is optimal.

---

## Step 5 — `compare_strategy_options`

**What it does:** Weighted comparison matrix → winner (recommended option) +
opportunity cost for the rejected ones + narrative.

**Parameters:**
- `project_id`
- `scores_json` — JSON scoring matrix: `{"OPT-001": {"alignment_to_goals": 4, "risk_mitigation": 3, ...}}`
- `weights_json` — optionally override the default weights (must sum to 100)
- `custom_criteria_json` — optional additional criteria
- `opportunity_cost` — text: what we give up by choosing the winner instead of the rest

**Default criteria and weights:**

| Criterion | Weight | What it assesses |
|----------|-----|---------|
| alignment_to_goals | 25% | Achievement of the BG from 6.2 |
| risk_mitigation | 20% | Mitigation of the top risks from 6.3 |
| cost | 20% | Inverse of cost |
| time_to_value | 15% | Speed to first value |
| org_readiness_fit | 10% | Fit with readiness_score |
| feasibility | 10% | Feasibility |

**Your job (Claude):** After the call — write a narrative explaining why the winner won,
referencing concrete data (risks, goals, readiness).

---

## Step 6 — `define_transition_states` (repeat for each phase)

**What it does:** Describes a transition phase — what's delivered, what's closed, what remains.

**Parameters:**
- `project_id`
- `phase_number` — phase number (1, 2, 3...)
- `phase_name` — phase name
- `duration_months` — duration
- `capabilities_delivered` — JSON list of capabilities delivered in this phase
- `gaps_closed` — JSON list of gap names closed after this phase
- `risks_remaining` — JSON list of RK-xxx risks that remain after this phase
- `value_realizable` — description of the value realized by the end of the phase

**Rule:** Each phase must deliver standalone value — otherwise rethink the slicing.

**Number of phases:** Depends on strategy_type:
- big_bang → 1 phase
- phased → 2–5 phases
- pilot_first → usually 2–3: pilot + rollout + (optionally) scale

---

## Step 7 — `save_change_strategy`

**What it does:**
- Saves `{project}_change_strategy.json` to DATA_DIR (contract for 7.x, 8.x)
- Generates a Markdown report via `save_artifact()`
- Optionally: registers the solution in the 5.1 repository as a `solution_scope`-type node

**Parameters:**
- `project_id`
- `push_to_traceability` — True if you're maintaining 5.1 traceability (default: False)
- `traceability_project_id` — if the 5.1 repository is under a different project_id

**When push_to_traceability=True:**
- Creates node SOL-001 of type `solution_scope` with status `defined`
  (NOT `solution`, which is the BABOK requirement class in the 5.1 vocabulary,
  and NOT status `approved`, which is 5.5's stakeholder-approval outcome)
- Links: SOL-001 satisfies BG-xxx (for each business goal from 6.2)

**After saving — tell the BA:**
1. The chosen strategy and the rationale
2. The path to the JSON (for 7.x)
3. What needs to be done about the lowest readiness dimensions before starting

---

## Quick answers to typical BA questions

**"Why consider do_nothing?"**
BABOK requires explicitly justifying why inaction is worse. This makes the decision defensible
before the board: "we considered the status quo — here's why it's unacceptable."

**"How many transition states do we need?"**
For phased — 2–5. More than 5 phases often signals an unclear scope or excessive
granularity. One transition state = big_bang.

**"If readiness_score is low — do we cancel the project?"**
No — it's a signal. Either change strategy_type to pilot_first/phased,
or add a preparatory phase 0 (organizational readiness).

**"Where's the line between 6.4 and 7.1?"**
6.4 defines WHAT (capabilities and scope) and WHEN (phases).
7.1 defines exactly HOW — detailed requirements for each capability.

---

## Relationship to other tasks

| Task | Relationship |
|--------|-------|
| ← 6.1 | Business needs BN-xxx → context for capabilities |
| ← 6.2 | BG-xxx and the gap_analysis both auto-imported (the gaps as context); the analyst names the element each capability closes in `gap_source` |
| ← 6.3 | RK-xxx → linked_risks in the options + risks_remaining in the phases |
| → 7.1 | solution_scope.capabilities → what to specify |
| → 7.4 | transition_states → requirements architecture by phase |
| → 7.5 | selected_option + rejected → design constraints |
| → 7.6 | value_realizable by phase → analysis of potential value |
| → 5.1 | push_to_traceability → solution_scope node + satisfies links |
| → 8.x | transition_states + risks_remaining → baseline for Solution Evaluation |
