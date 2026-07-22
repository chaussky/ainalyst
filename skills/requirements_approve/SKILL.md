---
name: requirements_approve
description: >
  BABOK 5.5 skill — Approve Requirements. Use this skill when requirements have been
  verified and are ready for formal sign-off by stakeholders, when a Requirements Baseline
  needs to be created, when a signature/approval needs to be obtained, or when a conditional
  approval needs to be closed.
  Triggers: "approve requirements", "baseline", "sign-off", "stakeholder approval",
  "sign off on requirements", "requirements sign-off".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: BABOK 5.5 — Approve Requirements

## When to use this skill

Use this skill when:
- Requirements have been verified (passed 7.2 `mark_req_verified`) and are ready for formal
  sign-off. This is reported, not enforced: `prepare_approval_package` warns about unverified
  requirements and `create_requirements_baseline` records them in the Approval Record, but
  neither blocks — the decision stays with the BA
- Stakeholder approval is needed before handoff to development
- An official Requirements Baseline needs to be created
- A stakeholder issued a conditional approval and the condition needs to be closed
- The readiness of a requirements package for baseline needs to be checked

---

## Input information

| Source | What we take |
|----------|-----------|
| 7.2 (Verify Requirements) | Verification evidence (`req_verified` in the repository history) |
| 4.3 (Confirm Elicitation) | Confirmed elicitation results (context) |
| 5.1 (Trace Requirements) | Traceability matrix, requirement statuses |
| 5.2 (Maintain Requirements) | Versions, change history, stability |
| 5.3 (Prioritize Requirements) | Priorities: Must/Should/Could/Won't, WSJF |
| 5.4 (Assess Changes) | CR Decision Records, under_change requirements |
| 3.2 / 4.2 | Stakeholder registry: roles, authority, influence |

---

## Task pipeline

```
prepare_approval_package → record_approval_decision (×N stakeholders)
  → [close_approval_condition (for Conditional)]
  → check_approval_status
  → create_requirements_baseline
```

---

## MCP tools

### 1. `prepare_approval_package`
**When:** Before starting an approval session. Assembles a requirements package for stakeholders.

**What it does:**
- Pulls requirements from the 5.1 repository by req_ids or package
- Reads each requirement's statement and acceptance criteria from its 7.1 spec
  file (the graph node holds only metadata) — the stakeholder signs readable text
- Adds the traceability matrix, priorities (5.3), CR Decision Records (5.4)
- Generates a Markdown document tailored to the audience

**Parameters:**
- `project_name` — project name
- `package_id` — unique package ID (APKG-001)
- `req_ids_json` — JSON list of requirement IDs for the package
- `approach` — `predictive` or `agile`
- `audience` — `business` / `developer` / `regulator` / `all`
- `package_title` — package title (e.g., "Feature: User Onboarding")
- `sprint_number` — sprint number (agile only)

---

### 2. `record_approval_decision`
**When:** After receiving a response from each stakeholder.
Called once per stakeholder (analogous to add_stakeholder_scores in 5.3).

**What it does:**
- Records the decision: `approved` / `conditional` / `rejected` / `abstained`
- For `conditional` — records the condition, deadline, and owner
- For `rejected` — analyzes context from 5.3/5.4 and flags conflicts
- Updates requirement status in the 5.1 repository

**Parameters:**
- `project_name`, `package_id`
- `stakeholder_name` — stakeholder name
- `stakeholder_raci` — `accountable` / `responsible` / `consulted`
- `decision` — `approved` / `conditional` / `rejected` / `abstained`
- `req_decisions_json` — JSON: decisions for individual requirements in the package.
  Format: `[{"req_id": "FR-001", "decision": "approved"}, {"req_id": "FR-002", "decision": "conditional", "condition_text": "...", "condition_deadline": "2026-04-01", "condition_owner": "Smith"}]`
  If empty (`[]`) — the decision applies to all requirements in the package as a whole.
- `rejection_reason` — required when decision=rejected
- `comment` — any comment from the stakeholder

---

### 3. `close_approval_condition`
**When:** After a condition on a Conditional approval has been satisfied.

**What it does:**
- Finds the open condition by package, requirement, and stakeholder
- Records that the condition has been satisfied (with date and description)
- Updates the requirement status to `approved`

**Parameters:**
- `project_name`, `package_id`
- `req_id` — requirement with the condition
- `stakeholder_name` — who set the condition
- `resolution_notes` — how the condition was closed

---

### 4. `check_approval_status`
**When:** At any point, to check whether the package is ready for baseline.

**What it does:**
- Computes statistics: approved / conditional / rejected / pending / abstained
- Identifies overdue conditionals and stakeholders without a response
- Flags rejections from Accountable stakeholders (blockers)
- Gives a verdict: ready / not ready for baseline, with reasons

**Parameters:**
- `project_name`, `package_id`

---

### 5. `create_requirements_baseline`
**When:** Once the package is ready for baseline (check_approval_status = ✅).

**What it does:**
- Creates a package snapshot in `{project}_approval_history.json`
- Updates the status of approved requirements in the 5.1 repository
- Generates an Approval Record (Markdown) via save_artifact
- This artifact feeds → 4.4 (communication) and Chapter 6 (input for development)

**Parameters:**
- `project_name`, `package_id`
- `baseline_version` — baseline version (e.g., `v1.0`, `v1.1`, `sprint-5`)
- `decided_by` — who confirms creation of the baseline (sponsor / PO)
- `force` — `true` to create the baseline even with warnings present
  (rejected from Consulted, open conditions). Defaults to `false`.

---

## BA workflow

### Scenario 1: Predictive — baseline at the end of the phase

1. Get the list of requirements verified in 7.2 (`get_verification_report`)
2. **`prepare_approval_package`** — assemble the package, `approach=predictive`, `audience=all`
3. Send the package to stakeholders (via 4.4 `prepare_communication_package`)
4. After each response: **`record_approval_decision`**
5. If Conditional: agree on the changes, then **`close_approval_condition`**
6. **`check_approval_status`** — check readiness
7. **`create_requirements_baseline`** — record baseline v1.0

### Scenario 2: Agile — Sprint Backlog Baseline

1. Select requirements for the next sprint
2. **`prepare_approval_package`** — `approach=agile`, `sprint_number=N`
3. Sprint Planning: Product Owner reviews the package
4. **`record_approval_decision`** — record the PO's decision
5. **`create_requirements_baseline`** — baseline `sprint-N`

### Scenario 3: Conflict during the approval stage

1. **`record_approval_decision`** — a stakeholder rejected a requirement
2. The system automatically surfaces a conflict with 5.3 / 5.4
3. The BA analyzes: is this an Accountable or a Consulted stakeholder?
   - Consulted: document the risk, baseline is still possible
   - Accountable: the conflict must be resolved before baseline
4. If the requirement needs to change → 5.2 `update_requirement`, then repeat from step 2
5. If a new CR is needed → 5.4 `open_cr`, then repeat the approval process

---

## Requirement statuses in the 5.1 repository

| Status | Meaning |
|--------|----------|
| `verified` | Passed quality checks (7.2), ready for approval |
| `pending_approval` | Sent for approval, awaiting response |
| `approved` | Officially approved, ready for development |
| `conditional_approved` | Approved with a condition (condition open) |
| `rejected` | Rejected, requires rework or risk assessment |
| `under_change` | Affected by a CR from 5.4, change assessment in progress |

---

## Relationship to other tasks

**Depends on:**
- 7.2 → verification evidence (`req_verified` in the repository history) — reported, not mandatory
- 4.3 → confirmed elicitation results (context)
- 5.1 → traceability repository
- 5.2 → requirement statuses and versions
- 5.3 → priorities (context for conflict analysis)
- 5.4 → CR Decision Records (context on changes)

**Provides:**
- 4.4 → Approval Record for communication
- Chapter 6 → approved requirements as input for solution development

---

## Reference materials

Read as needed:
- `references/approval_guide.md` — full reference: roles, statuses, baseline,
  Predictive vs Agile, common mistakes
