# Reference Guide: Approve Requirements (BABOK 5.5)

## When to read this file

Read this file when:
- The BA is preparing a requirements package for stakeholder approval
- You need to understand who has sign-off authority versus who is only consulted
- A stakeholder has rejected a requirement or issued a conditional approval
- An official baseline needs to be recorded before handoff to development
- A conflict has arisen between stakeholders during approval

---

## The nature of task 5.5

5.5 is the **final point in the requirements life cycle** before handoff to development.
Goal: obtain formal agreement from authorized stakeholders that the requirements
describe a solution that justifies the investment.

**Key difference from verification (4.3):**
- 4.3 checks the *quality* of requirements (completeness, consistency, testability)
- 5.5 obtains stakeholders' *agreement* on the *content* of the requirements

Requirements that passed 4.3 are verified. After 5.5, they are approved.

**Approval can be formal or informal:**
- Predictive: formal, at the end of the phase, with a signature or explicit confirmation
- Agile: informal, before each sprint, the Product Owner approves the backlog

---

## Stakeholder roles in the approval process

### RACI model in the context of 5.5

| Role | RACI | What this means |
|------|------|---------------|
| Sponsor | **A** (Accountable) | Bears responsibility for the decision, has veto power |
| Product Owner / Customer | **A** or **R** | Approves product requirements |
| Business expert | **R** (Responsible) | Actively participates in the review |
| End user | **C** (Consulted) | Opinion is taken into account but does not block |
| Developer / Architect | **C** | Confirms feasibility |
| Tester | **C** | Confirms testability |
| Regulator | **C** or **A** | A only for regulatory requirements |
| Project manager | **I** (Informed) | Receives information for planning |
| Operational support | **C** | Confirms supportability |

**Rule:** Rejected from C (Consulted) is input for risk assessment, not a blocker.
Rejected from A (Accountable) blocks the baseline.

### Where role information comes from
Stakeholder roles are defined in task 3.2 (Governance).
The stakeholder registry from 4.2 contains the current list of participants.

---

## Unit of approval: package with exceptions

### How a package is formed
A package is a group of logically related requirements: a feature, a component, an epic, or
all requirements for a phase (in Predictive).

### Exceptions for individual requirements
If a stakeholder agrees with the package as a whole but disagrees with specific req_ids,
they vote for the package with exceptions. Exceptions are recorded in `record_approval_decision`.

**Example:** A package of 20 requirements. The stakeholder approves 18, marks
REQ-05 as Conditional (wording needs clarification), and REQ-17 as Rejected (out of scope).

### Package status
A package is considered **approved** when all requirements in it have a status of `approved`
or `conditional_approved` with closed conditions.

---

## Stakeholder decision statuses

### Approved
The stakeholder agrees with the requirement without reservations.
The requirement is updated in the 5.1 repository: status `approved`.

### Conditional
The stakeholder approves subject to a condition being met. Required fields:
- `condition_text` — exactly what needs to be done
- `condition_deadline` — by when
- `condition_owner` — who is responsible for fulfilling it

The requirement stays in `pending_approval` status until the condition is closed.
When the condition is closed (via `close_approval_condition`) → it moves to `approved`.

**Typical conditions:**
- "Clarify the wording of the acceptance criterion"
- "Get sign-off from the legal department"
- "Get confirmation of feasibility from the tech lead"
- "Add an NFR for performance"

### Rejected
The stakeholder disagrees. The `rejection_reason` field is required.
The requirement does NOT move to `approved`.

**Important:** Rejected from a Consulted stakeholder is not a baseline blocker.
The BA documents the disagreement as a managed risk.

### Abstained
The stakeholder abstains. The reason is recorded.
Abstained does not block approval, but it is recorded in the audit trail.

---

## Managing conflicts during 5.5

### Types of conflicts
1. **Interpretation disagreement** — stakeholders read the requirement differently
2. **Priority conflict** — a stakeholder wants to change the priority (from 5.3)
3. **Scope conflict** — a stakeholder considers the requirement unnecessary or insufficient
4. **CR conflict** — the requirement is already affected by an open CR from 5.4

### How the system analyzes a conflict
When `record_approval_decision` is called with `rejected`, the system automatically checks:
- The requirement's priority from 5.3 (Must / Should / Could / Won't + WSJF score)
- Open or recent CRs from 5.4 affecting this requirement
- Other decisions on the same requirement (are there other rejections?)
- Status from 5.2 (version, change history, stability)

**Output:** "Smith rejected REQ-12. This requirement has Must priority (5.3),
is affected by CR-003 (under_change). It is recommended to clarify the CR scope before
re-submitting for approval."

The BA receives the facts — the decision remains with the BA.

---

## Predictive vs Agile: process differences

### Predictive (approach: predictive)
- A large package is approved at the end of the phase (Requirements Baseline)
- Formal confirmation: signature, email record, meeting minutes
- After the Baseline, changes go only through CR (5.4)
- `create_requirements_baseline` creates an official snapshot with the full list

### Agile (approach: agile)
- A subset of requirements is approved before each sprint
- The Product Owner approving the Sprint Backlog is itself the approval
- Less formal, but an audit trail is still needed
- Baseline = Sprint Goal + the sprint's approved backlog
- Changes happen without a CR process — they just become the next sprint

### What changes in the tools
- `prepare_approval_package`: different package format and recommendations
- `create_requirements_baseline`: Predictive — full snapshot, Agile — sprint snapshot
- Number of participants: Predictive — broad group, Agile — Product Owner + team

---

## Baseline: history and versioning

### What a Requirements Baseline is
A baseline is the official, agreed-upon version of a set of requirements at a point in time.
Once created, the baseline becomes a reference point. Changes are tracked relative to it.

### Baseline history
Multiple baselines per project is normal practice:
- `v1.0` — baseline after the Requirements phase
- `v1.1` — baseline after the first CR package
- `v2.0` — baseline for the second version of the product

Stored in `{project}_approval_history.json` — analogous to ADR-012.

### What goes into the baseline snapshot
- List of all approved requirements with versions (from 5.1)
- List of stakeholders who made decisions, with dates
- Conditional approvals with their conditions (closed and open)
- References to CR Decision Records (from 5.4) included in the baseline

### When to create a baseline
- Predictive: end of the Requirements phase, before Design/Development begins
- Agile: before each sprint (Sprint Backlog Baseline)
- After a large CR package (if many requirements changed)

---

## Tracking approval status

### What `check_approval_status` shows

**Baseline readiness dashboard:**

| Metric | Good | Needs attention |
|---------|--------|-----------------|
| % approved | > 90% | < 70% |
| Open conditionals | 0 | > 0 (overdue) |
| Rejected without risk assessment | 0 | > 0 |
| Stakeholders without a response | 0 | > 0 (overdue) |

**System verdict:**
- ✅ "Baseline can be created" — everything approved, conditions closed
- 🟡 "Open conditions exist" — baseline is possible with explicit risk assessment
- 🔴 "Blockers exist" — rejection from an Accountable stakeholder

---

## Artifacts of task 5.5

### Approval Package (input for stakeholders)
Generated by `prepare_approval_package`. Contains:
- The list of requirements with descriptions and acceptance criteria
- The traceability matrix (links between requirements)
- Priorities from 5.3
- Changes since the last baseline (CR Decision Records from 5.4)

Tailored to the audience:
- Business sponsor: business requirements and acceptance criteria in business language
- Developer: functional + non-functional requirements
- Regulator: compliance requirements with traceability to regulations

### Approval Record
Generated by `create_requirements_baseline`. The official document:
- Baseline ID and version
- Creation date and approval method (approach)
- List of approved requirements
- Each stakeholder's decision (with date)
- Open conditionals and risk assessment for rejected requirements

Passed on to 4.4 (communicate results) and Chapter 6 (input for development).

---

## Common BA mistakes during approval

**1. Requesting approval without prior consultation**
A stakeholder learns about a requirement for the first time at the approval session → risk of rejection.
Rule: first 4.4 (communicate and prepare), then 5.5 (formal approval).

**2. Ignoring Conditional status**
The BA records a Conditional and forgets to close the condition.
`check_approval_status` warns about overdue conditions.

**3. Approval without an audit trail**
"Smith said it was OK at the meeting" — three months later, nobody remembers.
`record_approval_decision` is mandatory even for verbal approvals.

**4. Baseline with pending requirements**
The BA creates a baseline while some requirements are still pending.
`create_requirements_baseline` warns and lists the unresolved items.

**5. Mixing up A and C roles**
The BA grants blocking power to Consulted stakeholders.
Rejected from C = input for risk assessment, not a blocker.
