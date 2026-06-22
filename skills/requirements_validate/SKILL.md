---
name: requirements_validate
description: >
  Skill BABOK 7.3 — Validate Requirements. Use this skill when the BA wants to
  check that the requirements are truly needed by the business: aligned with
  business goals, create value, do not contradict strategy, and are accepted
  by stakeholders.
  Triggers: "validate requirements", "does the business need this",
  "goal alignment", "business value", "are these the right requirements", "acceptance".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL.md — BABOK 7.3 Validate Requirements

## What this task is about

**Validation** answers the question: **"Did we write the right requirements?"**

Distinction from verification (7.2):
- **7.2 Verify** → "Are the requirements written correctly?" (quality of wording)
- **7.3 Validate** → "Do we need these requirements?" (value to the business)

A requirement can be perfectly worded — atomic, unambiguous, testable — but useless to the business. Validation is what catches that.

**Key principle:** 7.3 is an iterative task. It can be invoked multiple times at different stages of the project, unlike 7.2 (a one-time pass).

---

## Three axes of validation (BABOK)

### Axis 1: Value
Does the requirement bring benefit to stakeholders?
- Every req should trace back to a business goal (BG)
- An orphan req without traceability is a candidate for removal or decomposition

### Axis 2: Alignment with the future state
Does the req help achieve the Future State described in the business context?
- `check_business_alignment` checks this automatically (BFS + title-matching)
- The coverage matrix shows which BGs are not covered by any req

### Axis 3: Assumptions and risks
Have assumptions been identified, and are the related risks managed?
- Every contestable assumption must be logged via `log_assumption`
- High-risk assumptions block validation (warning in `mark_req_validated`)

---

## Pipeline (steps in order)

```
1. set_business_context        ← once, at the start of validation
2. check_business_alignment    ← check all verified req
3. set_success_criteria        ← [optional] for critical req
4. log_assumption               ← [as you go] when an assumption surfaces
5. resolve_assumption           ← [as you go] after confirming/refuting
6. mark_req_validated           ← move verified → validated
7. get_validation_report        ← summary report
```

---

## MCP tools

### 1. `set_business_context`

**When:** once, at the start of work on validating the project.

```
set_business_context(
  project_id = "crm_upgrade",
  business_goals_json = '[
    {"id":"BG-001","title":"Reduce request processing time","kpi":"from 24h to 4h"},
    {"id":"BG-002","title":"Increase NPS","kpi":"from 45 to 65"}
  ]',
  future_state = "Operators handle requests in a single window, prioritization is automated",
  solution_scope = "In scope: CRM module, integration with 1C. Out of scope: mobile app"
)
```

Data is stored in `{project}_business_context.json`. The business context is synced with tasks 6.1/6.2.

---

### 2. `check_business_alignment`

**When:** after creating the business context, before `mark_req_validated`.

```
check_business_alignment(project_id = "crm_upgrade")
# Checks all verified req

check_business_alignment(
  project_id = "crm_upgrade",
  req_ids = '["US-001", "FR-005", "UC-002"]'
)
# Checks specific req
```

**What it checks:**
- BFS traversal of the 5.1 graph: is a node of type `business` reachable from the req?
- Title-matching against the BGs from business_context
- Returns: aligned / orphan for each req
- Coverage matrix: which BGs are not covered

**Interpretation:**
- `aligned` (bfs) → traced through the 5.1 graph — the best outcome
- `aligned` (title-match) → keyword match — worth adding an explicit link in 5.1
- `orphan` → neither BFS nor title-match → requirement without a business justification

---

### 3. `set_success_criteria`

**When:** optional — for critical req where it matters to measure the outcome.

```
set_success_criteria(
  project_id = "crm_upgrade",
  req_id = "FR-001",
  criteria_json = '{
    "baseline": "Assignment time: 45 min manually",
    "target": "Assignment time: ≤ 30 sec automatically",
    "measurement_method": "Average time in the monitoring system over 1 week",
    "kpi_ref": "BG-001"
  }'
)
```

**Tip:** the tool automatically shows the KPI from the linked business goal as a reference point.

**Link to 8.1:** the success_criteria data from 7.3 becomes input for Measure Solution Performance.

---

### 4. `log_assumption`

**When:** whenever a contestable assumption is discovered while working on validation.

```
log_assumption(
  project_id = "crm_upgrade",
  description = "We assume operators are willing to switch to the new interface without extensive training",
  req_ids = '["US-005", "US-006"]',
  risk_level = "high",
  assigned_to = "A. Petrova"
)
```

**Risk levels:**
- `high` → warning at `mark_req_validated` while still open
- `medium` → logged, does not block
- `low` → low risk, informational record

---

### 5. `resolve_assumption`

**When:** after confirming or refuting an assumption (interview, test, research).

```
resolve_assumption(
  project_id = "crm_upgrade",
  assumption_id = "AS-001",
  resolution = "confirmed",
  resolution_note = "Ran a pilot with 3 operators — the switch went smoothly within 2 hours"
)

resolve_assumption(
  project_id = "crm_upgrade",
  assumption_id = "AS-002",
  resolution = "refuted",
  resolution_note = "Integration with the legacy system is not possible without a data migration"
)
```

**On `refuted`:** the tool produces a list of related req for re-examination. A new round of elicitation (4.1–4.3) may be needed.

---

### 6. `mark_req_validated`

**When:** a req is ready — verified, no high-risk assumptions, and traced to a BG.

```
mark_req_validated(
  project_id = "crm_upgrade",
  req_ids = '["US-001", "FR-001", "FR-002"]'
)

# Override when warnings are present:
mark_req_validated(
  project_id = "crm_upgrade",
  req_ids = '["US-007"]',
  force = True
)
```

**Three preconditions (ADR-033) — warnings, not blockers:**
1. Req status = `verified` (from 7.2)
2. No open high-risk assumptions for this req
3. Traced to a business goal

**Lifecycle:** `draft → verified (7.2) → validated (7.3)`

---

### 7. `get_validation_report`

**When:** at the end of validation work, to hand off to 7.5.

```
get_validation_report(project_id = "crm_upgrade")
```

**What it contains:**
- % validated out of total req
- Coverage matrix (BG → req)
- List of orphan req without traceability
- Open assumptions by risk_level
- % of req with success_criteria
- Readiness verdict for 7.5

---

## Typical workflow

### Start of the project
1. Verify the requirements (7.2)
2. Call `set_business_context` — enter the business goals from the customer

### Main body of work
3. `check_business_alignment` — find orphan req and gaps in BGs
4. For orphan req: add traceability via 5.1 (`add_trace_link`) or exclude the req
5. `log_assumption` — log contestable assumptions as they are discovered
6. Verify assumptions through work: interviews, pilots, analysis → `resolve_assumption`

### Finalization
7. `mark_req_validated` for ready req
8. `get_validation_report` → report to hand off to 7.5

---

## Files created by task 7.3

| File | Contains |
|------|----------|
| `{project}_business_context.json` | Business goals, Future State, scope |
| `{project}_assumptions.json` | Assumption registry AS-001/AS-002/... |
| `{project}_traceability_repo.json` | Updated validated statuses in 5.1 |
| `7_3_business_alignment_*.md` | Alignment report |
| `7_3_validation_report_*.md` | Final report → 7.5 |

---

## Links to other tasks

| From | What comes in |
|--------|-------------|
| 5.1 | Traceability graph — BFS traversal for check_business_alignment |
| 7.2 | `verified` status — precondition for mark_req_validated |

| To | What we hand off |
|------|-------------|
| 7.5 | Validation Report — basis for Design Options |
| 8.1 | success_criteria from 7.3 — for measuring outcomes |

---

## Detailed methodology and techniques

- Three axes of validation, BABOK techniques, error patterns →
  `references/validation_guide.md`

- Working with assumptions, risk classification, assumption patterns in IT →
  `references/assumptions_guide.md`
