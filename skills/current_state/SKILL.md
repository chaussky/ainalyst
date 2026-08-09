---
name: current_state
description: >
  BABOK 6.1 skill — Analyze Current State (as-is). Use this skill when the BA
  wants to understand the current state of the business, formulate business
  needs, conduct RCA (Root Cause Analysis), or describe organizational problems.
  Triggers: "current state", "as-is", "problem", "business need",
  "root cause", "analyze current state", "why is this happening".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: Analyze Current State (BABOK 6.1)

## When to read this skill

Read this file when:
- The BA says "I need to understand the current state," "run an as-is analysis," "describe the problem"
- The BA wants to formulate business needs
- The BA is conducting RCA (Root Cause Analysis)
- The request contains: "current state", "as-is", "problem", "business need",
  "root cause", "analysis", "current state"

## What this task is about

BABOK 6.1 — Analyze Current State — the starting point for the entire change project.

**Two key outputs:**
1. **Current state description** — structured analysis of 8 elements (what exists now)
2. **Business needs (BN-xxx)** — formalized reasons for change (input for 6.2)

**Why this matters:**
- Without a current state analysis, there's no understanding of what exactly we're changing and why
- Business needs are the upstream nodes of the entire traceability chain (BN → BR → FR → TC)
- RCA distinguishes symptoms from causes: the solution is precise, not "treating symptoms"

---

## MCP tools (6)

| Tool | When to call |
|------|----------------|
| `scope_current_state` | First step — scope and contract for the analysis |
| `capture_current_state_element` | For each element in scope (iteratively) |
| `run_root_cause_analysis` | After data collection, before formulating BN |
| `define_business_needs` | After RCA — formulate and register BN |
| `check_current_state_completeness` | Before finalization — coverage check |
| `save_current_state` | Final step — Markdown report + handoff to 7.3 |

---

## Workflow algorithm

### Step 1 — Scope (mandatory first step)

Call `scope_current_state`. Fixes an explicit contract for the analysis.

**Questions for the BA:**
- What initiated this project? (process_improvement / new_system / regulatory / cost_reduction / market_opportunity)
- How much time is available for the analysis? → choice of depth (light / standard / deep)
- Are there ready elicitation results from 4.3? → session_ids

**Default recommendations for elements_in_scope:**
- `process_improvement` → business_needs, capabilities, technology, policies
- `new_system` → business_needs, capabilities, technology, architecture
- `regulatory` → business_needs, policies, technology, external
- `cost_reduction` → business_needs, capabilities, assets, external
- `market_opportunity` → all 8 elements (deep)

For more on the 8 elements: read `references/current_state_guide.md`

---

### Step 2 — Collect data by element (iteratively)

Call `capture_current_state_element` for each element in scope.

**Order of work:**
1. Start with `business_needs` — this is the foundation
2. Then `capabilities` and `technology` — where the problem occurs
3. Then `policies` — what's blocking it or what's required
4. As needed: `org_structure`, `architecture`, `assets`, `external`

**How to help the BA fill in elements:**

For each element, ask the questions (from `references/current_state_guide.md`),
and help structure the answers. The result should be concrete, measurable descriptions.

**Signs of a good description:**
- Contains numbers (metrics): time, money, frequency, error rate
- Contains pain_points — symptoms, complaints, observations
- The information source is clear (sources)

**Signs of a poor description:**
- "The process is inefficient" — too generic
- "No automation" — a symptom, not a description of the state
- No metrics and no sources

---

### Step 3 — Root Cause Analysis

Call `run_root_cause_analysis` for each key problem.

**Choosing a technique (details: `references/rca_guide.md`):**
- `five_whys` — one problem, a linear chain, fast
- `fishbone` — several categories of causes (People / Process / Technology / Data)
- `problem_tree` — strategic analysis with consequences

**Key principles:**
- `problem_statement` — measurable: "Time increased from 2 to 8 hours" rather than "the process is slow"
- `root_cause` — one main cause (not a symptom, not a consequence)
- `contributing_factors` — factors that reinforce the root cause
- `evidence` — data confirming the chain of causes
- `affected_elements` — which of the 8 elements are affected (link to step 2)

**Normalized output:** regardless of the technique used — a single unified format.
The technique is a thinking tool. The MCP saves the normalized result.

---

### Step 4 — Formulating business needs

Call `define_business_needs` for each business need.

**The difference between a business need and a requirement:**
- Business need: WHAT needs to change and WHY
- Requirement: HOW exactly to do it

**Structure of a good business need:**
- `need_title` — a short, clear title
- `description` — a concrete, measurable statement of the problem/opportunity
- `cost_of_inaction` — what will happen if nothing changes (a compelling argument)
- `expected_benefits` — expected benefits from the change
- `root_cause_ids` — link to RCA (mandatory!)

**Registering in traceability:**
- `register_in_traceability: true` (default) — BN-xxx will appear in the 5.1 repository
- This is an upstream node: BN → BR → FR → TC — full end-to-end traceability
- If the 5.1 repository hasn't been created yet — create it via `init_traceability_repo` (5.1)

---

### Step 5 — Completeness check

Call `check_current_state_completeness` before finalization.

What it checks:
- Are all the scoped elements filled in?
- Is there at least one RCA?
- Are there business needs?
- Are the BNs linked to the RCA?

**These are warnings, not blockers.** The analyst decides whether to proceed.

---

### Step 6 — Finalization

Call `save_current_state`.

**The `push_to_business_context` parameter:**
- `false` (default) — only saves the 6.1 report
- `true` — prepares the data for handoff to 7.3. The BA then calls:
  `set_business_context(from_current_state_project_id="project_id", ...)`
  and the data from the BN automatically pre-fills the business objectives

---

## Integration with other tasks

### Input: 4.3 → 6.1 (import from elicitation)

If the BA has already conducted elicitation and confirmed results exist (4.3),
they can be imported during scoping via `session_ids`.

Mapping of 4.3 data → 8 elements of 6.1:
- `confirmed_needs` → the `business_needs` element
- `confirmed_constraints` → the `policies` element, partially `technology`
- `raw_notes` and interview context → `capabilities`, `org_structure`, `technology`
- Mentions of external factors → `external`

Imported data is marked as a draft — the BA refines it via
`capture_current_state_element`.

### Output: 6.1 → 5.1 (traceability)

BN-xxx nodes are registered in the 5.1 repository with the type `business_need`.
Full chain: `BN-001 → BR-001 → FR-001 → TC-001`
`run_impact_analysis` (5.4) sees business needs as upstream nodes.

### Output: 6.1 → 7.3 (business context)

`set_business_context` in 7.3 accepts the `from_current_state_project_id` parameter.
When passed — it pre-fills business objectives from the 6.1 business needs.
Without the parameter — it works as before (backward compatible).

### Output: 6.1 → 6.2 (Future State)

Task 6.2 builds on the `root_cause` from the RCA:
"What exactly are we changing" = "eliminating the root cause from RCA-001"

---

## Common BA mistakes — how to help

### "Describes symptoms instead of causes"
- Help by asking "Why?" three to five times
- Remind them: a customer complaint is a symptom; the cause lies in the process/technology/policy

### "Wants to analyze everything"
- Remind them about scope — scope_current_state defines what we analyze
- It's better to go deep on 4 elements than shallow on all 8

### "Business need is formulated as a solution"
- "We need a CRM system" — that's a solution, not a need
- The need: "We're losing 30% of customers due to slow request handling"

### "No numbers or metrics"
- Without numbers, it's impossible to assess the value of the solution in 7.6
- Help the BA find or estimate metrics: time, money, error rate

---

## 6.1 artifacts

| File | Purpose |
|------|------------|
| `{project}_current_state_scope.json` | Contract: what we're analyzing |
| `{project}_current_state.json` | Data for the 8 elements + RCA |
| `{project}_business_needs.json` | Business needs registry |
| `6_1_current_state_{project}.md` | Human-readable report (REPORTS_DIR) |

---

## Reference files

Read when you need details:

- **`references/current_state_guide.md`** — detailed description of each of the 8 elements:
  what to analyze, questions for the BA, examples of good/poor descriptions

- **`references/rca_guide.md`** — three RCA techniques with step-by-step instructions
  and a mapping to the normalized format
