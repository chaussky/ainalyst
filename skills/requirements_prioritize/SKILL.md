---
name: requirements_prioritize
description: >
  BABOK 5.3 skill — Prioritize Requirements. Use this skill when the BA wants to
  rank requirements using MoSCoW, WSJF, or the Impact/Effort method, resolve
  conflicts between stakeholders, or justify the implementation order.
  Triggers: "prioritization", "prioritize requirements", "MoSCoW", "WSJF",
  "what to do first", "priority conflict", "requirement importance", "backlog".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: BABOK 5.3 — Prioritize Requirements
**Task:** prioritize requirements and designs — determine their relative importance to stakeholders.
**MCP server:** `requirements_prioritize_mcp.py`
**References:** `references/methods_guide.md`, `references/conflict_resolution.md`

---

## Essence of the task

5.3 is not a one-time event — it is a **continuous process**. Priorities live alongside the project.

**What the BA does in 5.3:**
- Selects a prioritization method suited to the project context
- Collects stakeholder scores (each stakeholder has their own view of value)
- Aggregates the scores, identifies conflicts and dependency violations
- Facilitates conflict resolution
- Records the final priorities in the repository

**What 5.3 does NOT do:**
- It does not create new requirements (that's 4.2/4.3)
- It does not formally approve requirements with stakeholders (that's 5.5)
- It does not assess changes/CRs (that's 5.4)
- It does not make decisions on behalf of stakeholders — it only helps the BA structure the process

**Output of 5.3:** prioritized requirements → flow into **6.3 (Risk Assessment)**.

---

## Inputs from other tasks

| Task | What it provides |
|--------|----------|
| **5.1** | Dependency graph → automatic dependency-violation checks |
| **5.2** | Requirement stability → unstable requirements are flagged as risky for high priority |
| **4.2** | Stakeholder registry → influence weights for aggregation, list of session participants |
| **4.3** | Confirmed requirements → list to prioritize |
| **3.2** | Governance rules → who makes the final decision on conflicts |

---

## When this skill is activated

- Before sprint/release planning — need to decide what goes in
- After elicitation wraps up (4.3) — initial prioritization
- After receiving estimates from developers — revisit priorities factoring in cost
- After a Change Request (5.4) — revisit the affected requirements
- When the business context changes — full reassessment
- Regularly (once per sprint/stage) — keep priorities current

---

## Three methods — quick cheat sheet

### MoSCoW
`Must` / `Should` / `Could` / `Won't` — categorical ranking.
Fast, easy for stakeholders to grasp. Does not account for cost or time criticality.
Details: `references/methods_guide.md` → "Method 1"

### WSJF (Weighted Shortest Job First)
`WSJF = (BV + TC + RR) ÷ Job Size` — numeric ranking.
Objective, accounts for time and risk. Requires estimates from developers.
Details: `references/methods_guide.md` → "Method 2"

### Impact/Effort Matrix
Two criteria: value vs. effort → 4 quadrants → configurable mapping to priority.
Visual, good for workshops. The BA configures the mapping for the project.
Details: `references/methods_guide.md` → "Method 3"

---

## Five operating modes

### Mode A — Open a prioritization session

**When:** start of a new session (initial or repeat prioritization).

Algorithm:
1. Determine the context: which iteration? which requirement scope?
2. Choose a method (if not already chosen):
   - No cost estimates → MoSCoW or Impact/Effort
   - Estimates available + Agile project → WSJF
3. For WSJF: choose a scale (Fibonacci or 1–10) and set a reference requirement
4. For Impact/Effort: configure the quadrant mapping
5. Call `start_prioritization_session`

Result: list of requirements ready for scoring.
⚠️ Unstable requirements (stability = Volatile) are flagged automatically.
⚠️ Must-candidate requirements with dependencies are flagged for review.

### Mode B — Collect stakeholder scores

**When:** after opening the session, for each stakeholder individually.

Algorithm:
1. Score with each stakeholder (from the 4.2 registry) individually
2. For MoSCoW: each requirement → Must/Should/Could/Won't
3. For WSJF: score BV, TC, RR for each requirement (JS — from developers)
4. For Impact/Effort: score Impact and Effort for each requirement
5. Call `add_stakeholder_scores` for each stakeholder

> 📌 Important: the BA calls `add_stakeholder_scores` exactly once per stakeholder.
> Scores accumulate in the session snapshot; aggregation happens only in Mode C.

### Mode C — Aggregate and identify conflicts

**When:** all scores are collected, ready to calculate.

Algorithm:
1. Call `run_aggregation`
2. Review the result:
   - Final priority for each requirement
   - 🔴 Stakeholder conflicts — need resolution
   - ⚠️ Dependency violations — logical contradictions
   - 🟡 Unstable requirements at high priority — rework risk
3. For each conflict — choose a tactic (Mode D)
4. If there are no conflicts — proceed to Mode E

Tactics reference: `references/conflict_resolution.md`

> 📌 If >60% of requirements are Must, that's a sign of Must Inflation.
> Recommendation: run a follow-up session using the "fixed budget" technique.

### Mode D — Resolve a conflict

**When:** a conflict was identified after aggregation.

Algorithm:
1. Determine the conflict type:
   - Cross-stakeholder (diverging scores)
   - Dependency violation (Must depends on Won't)
   - Priority inflation (>60% Must)
2. Apply a tactic (see `references/conflict_resolution.md`)
3. Call `resolve_conflict` — record the decision and rationale
4. Critical conflicts (Must vs. Won't, High/High influence) → link to the Decision Log (4.5)

### Mode E — Finalize the result

**When:** all conflicts are resolved, priorities are agreed.

Algorithm:
1. Verify that all conflicts are marked resolved
2. Call `save_prioritization_result`
3. The tool:
   - Writes the `priority` field into the 5.1 repository
   - WSJF sessions also write `wsjf_score` onto the node — 5.5 reads it to warn
     when a stakeholder rejects a high-value requirement
   - Saves a snapshot to `{project}_prioritization.json`
   - Generates a Markdown report for stakeholders

---

## MCP tools

| Tool | Mode | What it does |
|------------|-------|-----------|
| `start_prioritization_session` | A | Open a session, choose a method, get the requirement list |
| `add_stakeholder_scores` | B | Add scores from one stakeholder |
| `run_aggregation` | C | Aggregate scores, find conflicts and violations |
| `resolve_conflict` | D | Record the decision on a conflict |
| `save_prioritization_result` | E | Finalize, update the 5.1 repository |

---

## Mapping from 5.2 — stability as a factor

Before the session, the `start_prioritization_session` tool automatically checks requirement stability:

| Stability (from 5.2) | Version | Behavior in 5.3 |
|--------------------|--------|-----------------|
| `Stable` | < 1.3 | No restrictions |
| `Volatile` | 1.3–1.3 | 🟡 Warning if Must |
| `Volatile` (critical) | ≥ 1.4 | 🔴 Flag: "high rework risk if Must" |
| `Unknown` | — | 🟡 Recommendation: clarify stability before finalizing |

---

## Mapping from 5.1 — dependencies

`run_aggregation` automatically checks for dependency violations:

1. For each requirement with a final priority of Must/Should
2. Looks up all `depends`-type links in the 5.1 repository
3. Checks: do all upstream dependencies have priority ≥ the current one?
4. If not — flags it as a dependency violation

Link types that are checked: `depends` only.
`derives`, `satisfies`, `verifies` links are not dependency violations.

---

## Common BA questions

**"A stakeholder changed their mind after the first scoring round — how do I update it?"**
Call `add_stakeholder_scores` again for the same stakeholder.
The new scores replace the previous ones in the current session.

**"Do I need to run prioritization for designs too (not just requirements)?"**
Yes — BABOK includes Designs as input information for 5.3. In this platform the design and
model artifacts from 7.1 (use cases, business processes, data dictionaries, ERDs) are already
registered in the 5.1 repository under their own types and are prioritized with the same
scheme. There is no separate `design` node type.

**"How often should prioritization be repeated?"**
Rule: whenever any of the triggers above occurs (estimates received, CR accepted, context changed).
Each session is a separate snapshot with history.
