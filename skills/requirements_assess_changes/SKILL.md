---
name: requirements_assess_changes
description: >
  BABOK 5.4 skill — Assess Requirements Changes (Change Request). Use this skill
  when a request to change requirements comes in: you need to assess impact, run a
  consequence analysis, score the CR, and produce a recommendation (Approve/Defer/Reject).
  Triggers: "change request", "CR", "request for change", "impact analysis",
  "assess requirements changes", "assess change", "change to requirements", "new CR".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: BABOK 5.4 — Assess Requirements Changes
**Task:** assess the consequences of a proposed change to requirements and designs (Change Request).
**MCP server:** `requirements_assess_changes_mcp.py`
**Reference:** `references/cr_assessment_guide.md`

---

## What this task is about

5.4 is the **change gatekeeper**. Every CR goes through four steps:
`open_cr` → `run_cr_impact` → `score_cr` → `resolve_cr`

**What the BA does in 5.4:**
- Registers the CR and determines the formality level
- Analyzes impact via the 5.1 traceability graph
- Scores the CR along five axes (Benefit / Cost / Impact / Schedule / Urgency)
- Receives a recommendation and hands it off for a decision to the authorized stakeholder
- Records the decision with rationale, updates requirement statuses

**What 5.4 does NOT do:**
- It does not make the final decision — it only provides a recommendation
- It does not change the content of requirements (that's the BA via 5.2, after Approved)
- It does not re-prioritize requirements (that's 5.3 — run it after resolve_cr)
- It does not formally approve requirements (that's 5.5)

**Output of 5.4:** a CR Decision Record → feeds into **4.4 (communication)** and **5.5 (approval/audit)**.

---

## Inputs from other tasks

| Task | What it provides |
|--------|----------|
| **5.1** | Traceability graph → BFS traversal for impact analysis |
| **5.2** | Requirements stability → risk flags for volatile requirements |
| **5.3** | Priorities → check for CR conflicts with Must/Won't |
| **3.3** | Governance approach → who is authorized to decide on CRs |
| **4.5** | Decision Log → where the final decision is recorded |

---

## When this skill activates

- A stakeholder requests a new piece of functionality
- A change in business strategy or scope is identified
- Legislative/regulatory requirements have changed
- A developer has identified a technical constraint requiring a requirements review
- New data has emerged that changes the understanding of the business need
- Testing has revealed a mismatch between requirements and reality

---

## Four pipeline steps

### Step 1 — Open the CR (`open_cr`)

**When:** a change request has been received and needs to be registered.

Algorithm:
1. Determine the type of change: new requirement / change to an existing one / removal / architectural
2. Identify the initiator and the affected areas
3. Determine the formality level (read `references/cr_assessment_guide.md` → "Assessment formality"):
   - Predictive + close to release → high formality
   - Agile + start of iteration → standard
   - Regulatory CR → always high, Urgency = Critical automatically
4. Call `open_cr`

Result: the CR is registered as a node in the 5.1 repository, status `open`.

> 📌 A CR is a new node type in the 5.1 repository. It is linked to affected requirements
> via a `modifies` relation (added in `run_cr_impact`).

---

### Step 2 — Impact analysis (`run_cr_impact`)

**When:** the CR is open and you need to understand the scope of the change.

Algorithm:
1. Call `run_cr_impact` with the CR ID and the list of target requirements
2. The tool performs a BFS traversal of the 5.1 graph starting from each target requirement
3. Review the result:
   - List of affected requirements by relation type
   - `depends` → what will lose meaning
   - `verifies` → which tests need to be rewritten
   - `satisfies` → which code needs to be reworked
   - `derives` → which child requirements are affected
4. Check: are there any affected requirements with no traceability to a BR?
5. Check: are there any volatile requirements among those affected (from 5.2)?

> 📌 If the scope turns out unexpectedly large, notify the initiator before score_cr.
> Many CRs get withdrawn from consideration at exactly this step.

---

### Step 3 — Score the CR (`score_cr`)

**When:** impact analysis is complete and the real scope is known.

Algorithm:
1. The technical axes are filled in automatically (Impact + Schedule from step 2)
2. Enter the business axes manually:
   - **Benefit**: High / Medium / Low — what does the business gain?
   - **Cost**: Low / Medium / High — full cost including opportunity cost
   - **Urgency**: Critical / High / Normal — how urgent is it?
3. Call `score_cr`
4. Receive:
   - A numeric CR Score and a preliminary verdict (Approve/Modify/Defer/Reject)
   - A narrative rationale from Claude that accounts for context
   - Automated checks (traceability to the need, conflicts with priorities)

**Scoring scale:**
- ≥ 8.0 → ✅ Approve
- 4.0–7.9 → 🟡 Modify
- 1.0–3.9 → ⏳ Defer
- < 1.0 → ❌ Reject

> 📌 The formula yields a preliminary verdict. Claude can adjust it
> with an explicit reason. The BA makes the final decision on what gets submitted for approval.

For details on the axes: `references/cr_assessment_guide.md` → "Five impact analysis axes"

---

### Step 4 — Record the decision (`resolve_cr`)

**When:** the authorized stakeholder has made a decision.

Algorithm:
1. Obtain the decision from the authorized party (per governance 3.3 — `score_cr`
   names the planned decision makers in its Step 4 block when 3.3 has been planned,
   and `resolve_cr` cross-checks `decided_by` against them and flags a mismatch in
   the CR Decision Record; it never blocks and never rewrites the name)
2. Call `resolve_cr` with parameters:
   - `decision`: Approved / Approved_with_Modification / Deferred / Rejected
   - `decided_by`: who made the decision
   - `rationale`: justification (required — for audit purposes)
3. The tool automatically:
   - On Approved: changes the status of affected requirements to `under_change`
   - Generates a CR Decision Record (Markdown) → `save_artifact`
   - Updates the status of the CR node in the 5.1 repository
4. After Approved: update the content of requirements via `update_requirement` (5.2)
5. After Approved: run `start_prioritization_session` (5.3) if priorities are affected
6. Send the CR Decision Record via `prepare_communication_package` (4.4)

> 📌 Rejected and Deferred CRs are not deleted from the repository.
> CR history is part of the project's audit trail.

---

## MCP tools

| Tool | Step | What it does |
|------------|-----|-----------|
| `open_cr` | 1 | Register the CR in the 5.1 repository |
| `run_cr_impact` | 2 | BFS traversal of the graph, build the list of affected items, create `modifies` relations |
| `score_cr` | 3 | Calculate the CR Score, get a recommendation + automated checks |
| `resolve_cr` | 4 | Record the decision, update statuses, generate the Decision Record |

---

## Mapping from 5.1 — relation types during impact analysis

| Relation type | What it means for a CR |
|-----------|---------------------|
| `depends` | The dependent requirement may lose its meaning |
| `verifies` | Test cases need to be reviewed/rewritten |
| `satisfies` | The code component needs to be reworked |
| `derives` | Child requirements may inherit the change |
| `modifies` | Direct CR → changed-requirement link (created in step 2) |

---

## Mapping from 5.2 — stability as a risk factor

| Stability (from 5.2) | Behavior in 5.4 |
|--------------------|----------------|
| `Stable` (version < 1.3) | No additional flags |
| `Volatile` (version 1.3) | 🟡 Warning: unstable requirement + CR = double uncertainty |
| `Volatile` (version ≥ 1.4) | 🔴 High risk: recommend stabilizing the requirement before the CR |

---

## Common BA questions

**"The CR is small — do I still need to go through all four steps?"**
Yes — all four steps. For a small CR, the pipeline moves through quickly.
Impact often turns out larger than expected — the graph will show it.

**"Who can be `decided_by`?"**
Determined in task 3.3 (Governance). Usually: the sponsor, the Product Owner, or the CCB.
If unclear, check with the Project Manager.

**"What if several CRs affect the same requirements?"**
Assess them together: pass `related_cr_ids` to `open_cr`.
The combined impact can be non-linear — it's better to see the whole picture.

**"After a CR is Approved, when should I update the requirements in 5.2?"**
Right after `resolve_cr`. The `under_change` status means "the requirement is in the process of being changed."
Don't leave requirements in `under_change` for longer than one iteration.

**"Do I need to re-prioritize after a CR?"**
If the CR changes Must/Won't items or adds new requirements — yes, run 5.3.
`resolve_cr` will explicitly flag it if conflicts with priorities are detected.
