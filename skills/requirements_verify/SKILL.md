---
name: requirements_verify
description: >
  BABOK 7.2 skill — Verify Requirements. Use this skill when the BA wants to
  check the quality of written requirements: atomicity, unambiguity, testability,
  completeness, consistency. Difference from validation: verification is about the quality
  of the wording, not about business value. Triggers: "verify requirements", "requirements verification",
  "requirements quality", "check requirements", "checklist".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL.md — BABOK 7.2 Verify Requirements

## What this task is about

Verifying requirements answers the question: **"Are the requirements written correctly?"**

Difference from task 7.3 (Validate):
- 7.2 Verify: is the requirement *written* correctly? (quality of the wording)
- 7.3 Validate: is *this* the right requirement? (alignment with the business need)

Input: requirements from the 5.1 repository (created in 7.1).
Output: `verified` status in 5.1, Verification Report → 5.5 (Approve) and 7.3 (Validate).

---

## BABOK's 9 quality characteristics

| Characteristic | Group | How we check it |
|---------------|--------|---------------|
| Atomic | A | MCP: stop words |
| Unambiguous | A | MCP: signal words |
| Testable | A | MCP: structure + AC |
| Prioritized | A | MCP: priority field in 5.1 |
| Concise | A | MCP: length + signals |
| Consistent | B | MCP: statuses + 5.1 graph |
| Complete | B | MCP: source_artifact + links |
| Feasible | C | BA checklist (see references/) |
| Understandable | C | BA checklist (see references/) |

Rule details — in `references/quality_rules.md`.
Checklists by type — in `references/checklist_templates.md`.

---

## Task 7.2 pipeline

```
check_req_quality           → automated checks for Group A+B
  ↓ (if issues are found)
open_verification_issue     → record each issue
  ↓ (BA fixes the requirements)
check_model_consistency     → cross-model check of files from 7.1
  ↓ (if there is a mismatch)
open_verification_issue     → record the model inconsistency
  ↓ (BA fixed it)
resolve_verification_issue  → close the issue
  ↓
mark_req_verified           → status draft → verified in 5.1
  ↓
get_verification_report     → summary report → 5.5 + 7.3
```

---

## MCP tools

### check_req_quality(project_id, req_ids?, req_type?)

Checks one requirement, a list, or all reqs in the project against the 9 characteristics.

**Smart batch:** if `req_ids` is not set — it takes all `draft` reqs from the 5.1 repository.
If `req_type` is set — it filters by type (user_story / functional / non_functional, etc.).

**Returns:**
- Check results for each req (Groups A+B)
- List of blockers and majors for each
- Hints for Claude Code: what exactly is violated and how to fix it
- A reminder to go through the Group C checklists (Feasibility + Understandability)

**Usage pattern:**
```
# Check everything
check_req_quality(project_id="my_project")

# Check specific reqs
check_req_quality(project_id="my_project", req_ids='["US-001", "FR-001"]')

# Check only User Stories
check_req_quality(project_id="my_project", req_type="user_story")
```

---

### check_model_consistency(project_id)

Compares artifacts from 7.1: .md and .puml files in `governance_plans/{project}_specs/`.

**What it checks:**
- Entities in DD vs ERD (name mismatches)
- Use Cases vs UC Diagram (UC without an actor in the diagram)
- Business process participants vs actors in the UC Diagram

**Important:** Parsing is regex-based, following the templates from 7.1. Works for standard formatting. For non-standard formats — Claude Code interprets the warnings manually.

---

### open_verification_issue(project_id, req_id, issue_type, description, severity, assigned_to?)

Records an issue found during verification.

**issue_type:** ambiguity / not_testable / not_atomic / missing_ac / model_inconsistency / other
**severity:** blocker / major / minor

**When to open one:**
- After `check_req_quality` — for each automatically detected issue
- After manually going through the Group C checklists
- After `check_model_consistency` — for model mismatches

**Setting assigned_to:** typically the BA who created the requirement (the owner).

---

### resolve_verification_issue(project_id, issue_id, resolution_note)

Closes an issue after the BA has fixed the requirement.

**resolution_note** — what exactly was fixed (for audit purposes).

**Important:** Once all blocker issues for a req are closed — `mark_req_verified` can be called.

---

### mark_req_verified(project_id, req_ids)

Changes the status `draft → verified` in the 5.1 repository.

**Precondition:** MCP will check for any open blocker issues on each req.
If a blocker exists — a warning is shown, but it does not block (the BA makes the call).

```
# Verify a list
mark_req_verified(project_id="my_project", req_ids='["US-001", "US-002", "FR-001"]')
```

---

### get_verification_report(project_id)

Summary verification report for the project.

**Contains:**
- % verified out of all reqs (readiness indicator for 5.5)
- Top issues by characteristic type
- List of reqs with open blocker issues
- Open issues with details
- Verdict: is it ready for Approve (5.5)

Saves Markdown via `save_artifact` — pass it on to 5.5 and 7.3.

---

## Typical workflow

**Step 1.** Run a check on all requirements:
```
check_req_quality(project_id="crm_2024")
```
Claude Code reads the result and explains each issue in plain language.

**Step 2.** For critical issues, open issues:
```
open_verification_issue(
  project_id="crm_2024",
  req_id="US-003",
  issue_type="missing_ac",
  description="The User Story has no Acceptance Criteria — no acceptance criteria defined",
  severity="blocker"
)
```

**Step 3.** Fix the requirement (in the file or via the 7.1 tool). Then close the issue:
```
resolve_verification_issue(
  project_id="crm_2024",
  issue_id="VI-001",
  resolution_note="Added 3 Acceptance Criteria: successful login, wrong password, account lockout"
)
```

**Step 4.** Check model consistency:
```
check_model_consistency(project_id="crm_2024")
```

**Step 5.** Go through the Group C checklists from `references/checklist_templates.md` — Feasibility and Understandability for each requirement type.

**Step 6.** Verify the requirements that have no blockers:
```
mark_req_verified(project_id="crm_2024", req_ids='["US-001", "US-002", "FR-001"]')
```

**Step 7.** Generate the report to hand off to 5.5:
```
get_verification_report(project_id="crm_2024")
```

---

## Relationship to other BABOK tasks

**Incoming links:**
- 5.1 repository — list of reqs with statuses
- Files from 7.1 — specifications in `governance_plans/{project}_specs/`

**Outgoing links:**
- → 5.5 (Approve Requirements): Verification Report as an input artifact
- → 7.3 (Validate Requirements): verified reqs as input data

**Important:** 7.2 and 7.3 can run iteratively and in parallel. If validation (7.3) reveals that a requirement is poorly worded — go back to 7.2.

---

## Data storage

| What | Where | Format |
|-----|-----|--------|
| Verification issues | `governance_plans/{project}_verification_issues.json` | JSON |
| Req statuses | 5.1 repository (`{project}_traceability_repo.json`) | JSON (status field) |
| Verification Report | `governance_plans/` via save_artifact | Markdown |

---

## Hints for Claude Code when interpreting results

**For `ambiguity` (signal word):**
Explain to the BA exactly what is vague and suggest a rewording with a metric.
Example: "fast" → "within 2 seconds under a load of up to 1000 users".

**For `missing_ac`:**
Suggest 2-3 example ACs in Given/When/Then format, or simply as numbered conditions.

**For `not_atomic`:**
Point out exactly where a conjunction splits the requirement into two. Suggest splitting it into req_id_a and req_id_b.

**For `not_testable` (FR without a metric):**
Ask the BA what the measurable outcome is. Example: "the system saves" → "the system saves within X seconds with a probability of Y%".

**For `model_inconsistency`:**
Show specifically: in which file what is written, and what diverges. The BA fixes it in the relevant file.
