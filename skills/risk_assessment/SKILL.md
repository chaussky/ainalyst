---
name: risk_assessment
description: >
  BABOK 6.3 skill — Assess Risks. Use this skill when the BA wants to collect,
  structure, and assess project risks: run a risk matrix, determine tolerance,
  define response strategies, and produce a recommendation for the sponsor.
  Triggers: "assess risks", "risk assessment", "risk matrix", "project risks",
  "likelihood and impact", "risk register", "risk tolerance".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: 6.3 — Assess Risks

**BABOK chapter:** 6 — Strategy Analysis  
**Task:** 6.3 Assess Risks  
**MCP server:** `skills/risk_assessment_mcp.py`

---

## What this task is about

Risks are uncertainty that **threatens business objectives**.
The goal of 6.3: identify risks, assess them semi-quantitatively (likelihood × impact),
plan response measures, and give the sponsor a justified recommendation:
proceed / proceed with mitigation / do not proceed.

**Key inputs:**
- 6.1 `{project}_current_state.json` — root causes, business needs
- 6.2 `{project}_future_state.json` — constraints, gap analysis
- 4.2 elicitation results — risks mentioned by stakeholders
- Stakeholder registry 3.2 — for owner assignment

**Key outputs:**
- `{project}_risk_assessment.json` — full risk register (→ 6.4)
- `{project}_risk_assessment_report.md` — report for the sponsor

---

## When to read references

| Situation | Read |
|----------|-------|
| Need help categorizing or wording a risk | `references/risk_assessment_guide.md` |
| Unsure how to assess likelihood/impact | `references/risk_assessment_guide.md` §2–3 |
| Sponsor didn't set tolerance explicitly | `references/risk_tolerance_guide.md` §5 |
| Need industry benchmarks | `references/risk_tolerance_guide.md` §4 |
| Unsure what the `run_risk_matrix` result means | `references/risk_assessment_guide.md` §10 |

---

## Pipeline — 7 steps

```
scope_risk_assessment
      ↓
import_risks_from_context      ← optional, but recommended
      ↓
add_risk × N                   ← main loop, repeat as many times as you have risks
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

## Step 1 — `scope_risk_assessment`

**What it does:** fixes the scope: initiative type, analysis depth,
risk sources, link to projects 6.1/6.2.

**Parameters:**
- `project_id` — same as in 6.1/6.2
- `initiative_type` — process_improvement / new_system / regulatory / cost_reduction / market_opportunity / other
- `analysis_depth` — quick (High only) / standard (H+M) / comprehensive (all)
- `source_project_ids` — list of project_id from 6.1/6.2 for auto-import (optional)
- `ba_notes` — additional context

**Questions for the BA before calling:**
> 1. What type of initiative (see initiative_type)?
> 2. How deep should the analysis be? (quick = an hour of work, comprehensive = half a day)
> 3. Are there already completed 6.1 or 6.2 artifacts for this project?

---

## Step 2 — `import_risks_from_context` (recommended)

**What it does:** scans the 6.1, 6.2, 4.2 artifacts and proposes risk drafts.
Drafts have status `draft` — the BA decides which to confirm via `add_risk`.

**Parameters:**
- `project_id`
- `source_project_ids` — list of project_id to scan

**What to do with the result:**
The tool returns a list of drafts. For each draft:
- Want to add it → call `add_risk` with the draft's data (adjusting as needed)
- Not relevant → just skip it

**Graceful degradation:** if the 6.1/6.2 artifacts aren't found — continue without them.

---

## Step 3 — `add_risk` (repeat for each risk)

**What it does:** adds a risk to the register. Automatically:
- Assigns `risk_id` (RK-001, RK-002...)
- Computes `risk_score = likelihood × impact`
- Sets `status = identified`

**Required parameters:**
- `project_id`
- `category` — strategic / operational / financial / technical / regulatory / people / external
- `source` — change / current_state / future_state / requirement / stakeholder / assumption / constraint
- `description` — format "If X, then Y"
- `likelihood` — 1–5 (see references/risk_assessment_guide.md §2)
- `impact` — 1–5 (see references/risk_assessment_guide.md §3)
- `response_strategy` — accept / mitigate / transfer / avoid

**Recommended parameters:**
- `likelihood_rationale` — rationale for the likelihood estimate
- `impact_rationale` — rationale for the impact estimate
- `mitigation_plan` — required if strategy=mitigate
- `owner` — stakeholder_id from the 3.2 registry

**Wording rule:** "If [trigger/condition], then [consequence]"
Bad: "Integration risk". Good: "If the legacy system's API doesn't support the required methods, then integration will take 6 weeks longer".

**How many risks are enough?**

| Depth | Minimum risks |
|---------|---------------|
| quick | 3–5 |
| standard | 7–15 |
| comprehensive | 15–30 |

Quality matters more than quantity — 7 well-defined risks beat 25 vague ones.

---

## Step 4 — `set_risk_tolerance`

**What it does:** sets the tolerance level and the numeric threshold for High risks.

**Parameters:**
- `project_id`
- `tolerance_level` — risk_averse / neutral / risk_seeking
- `max_acceptable_score` — score ≥ this = High risk (default: 15)
- `organization_context` — context (industry, type)
- `sponsor_risk_appetite` — sponsor's position (text)

**If the sponsor didn't set tolerance explicitly:** use the questions from
`references/risk_tolerance_guide.md` §5 to determine it.

**Quick guideline:**
- Bank / public sector / pharma → `risk_averse`, threshold 10–12
- Commercial company, standard project → `neutral`, threshold 15
- Startup / digital transformation → `risk_seeking`, threshold 18–20

---

## Step 5 — `run_risk_matrix`

**What it does:** classifies risks into zones (Low/Medium/High),
builds the cumulative profile, prepares data for the recommendation.

**Parameters:** only `project_id`

**Reading the result:**
- `high_risks_count` — number of risks above the threshold
- `total_score` — total "severity"
- `zones` — list of risks with zones 🟢🟡🔴

**After calling:** be sure to discuss the top 3 High risks with the BA before the next step.

---

## Step 6 — `generate_recommendation`

**What it does:** deterministic logic determines the recommendation type,
Claude writes the narrative rationale (2–4 sentences with concrete data).

**Parameters:**
- `project_id`
- `potential_value_summary` — brief description of the expected value from 6.2
  (if 6.2 is filled in, it's pulled automatically)

**Recommendation types:**

| Type | When |
|-----|-------|
| `proceed_despite_risk` | No risks above the threshold |
| `proceed_with_mitigation` | High risks exist, mitigation is possible |
| `seek_higher_value` | Risk profile doesn't match the expected value |
| `do_not_proceed` | Critical risks with no possible mitigation |

**Your job (Claude):** write 2–4 sentences of rationale with concrete numbers.
For example: "Of 12 identified risks, 3 are in the High zone (score 15–20).
The most critical is the integration risk (RK-007, score 20): a Sprint 0 prototyping
effort is recommended before development starts. If the mitigation plans are executed,
the cumulative profile drops from 94 to ~55 — the project can proceed."

---

## Step 7 — `save_risk_assessment`

**What it does:**
- Saves `{project}_risk_assessment.json` to DATA_DIR (input for 6.4)
- Generates a Markdown report via `save_artifact()`
- Optionally: registers risks in the 5.1 repository as `risk`-type nodes

**Parameters:**
- `project_id`
- `push_to_traceability` — True if you're maintaining 5.1 traceability (default: False)
- `traceability_project_id` — project_id of the 5.1 repository (if different)

**When push_to_traceability=True:**
- Each RK-xxx is registered as a `risk` node in the 5.1 repository
- `threatens`-type links are created: RK-001 threatens BN-001, etc.

**After saving — tell the BA:**
1. Path to the JSON (for 6.4 Define Change Strategy)
2. Path to the Markdown report (for the sponsor)
3. Top 3 priority risks for immediate action

---

## Quick answers to common BA questions

**"How many risks do I need to find?"**
Enough to cover the main threats to the project's objectives. Quick = 3–5,
standard = 7–15. Fewer risks with clear mitigation plans beat more vague ones.

**"How do I choose between mitigate and avoid?"**
Avoid — if the risk is Critical (impact=5) and mitigation is technically impossible or
costs more than the potential benefit. Otherwise — mitigate with a concrete plan.

**"Do I need to fill in 6.1 and 6.2 before 6.3?"**
No, 6.3 works independently. But if 6.1/6.2 are filled in — `import_risks_from_context`
saves time and helps avoid missing obvious risks.

**"What do I do if the sponsor says 'we have no risks'?"**
Use `import_risks_from_context` — the 6.1/6.2 artifacts almost always contain
hidden risks in the constraints and gap analysis. Show them the concrete drafts.

---

## Relationship to other tasks

| Task | Relationship |
|--------|-------|
| ← 6.1 | RCA and business needs → risk sources |
| ← 6.2 | Constraints and gaps → risk drafts |
| ← 4.2 | stakeholders' risks_mentioned → drafts |
| → 6.4 | `{project}_risk_assessment.json` → input for Define Change Strategy |
| → 7.6 | Risk profile is factored into the value assessment of options |
| → 5.1 | push_to_traceability=True → risk nodes + threatens links |
