# Reference Guide: Assess Requirements Changes (BABOK 5.4)

## When to read this file

Read this file when:
- The BA is opening a new CR and is unsure how to assess its formality
- You need to understand how the five-axis scoring is calculated
- A question arises about who makes the decision on a CR
- The CR involves regulatory or legislative requirements

---

## The nature of task 5.4

5.4 is the **change gatekeeper**. The output is not a decision but a *recommendation*.
The decision is made by the sponsor, the CCB (Change Control Board), or the authorized stakeholder.

The BA assesses: will the change increase the value of the solution, and if so, at what cost.

**Three mandatory questions for any CR:**
1. Does the CR trace back to a real business need?
2. Does the CR conflict with existing requirements?
3. Does the CR increase the level of risk?

---

## Assessment formality

The formality level is determined **before** the analysis begins. It depends on:

| Factor | Low formality | High formality |
|--------|--------------------|--------------------|
| Project methodology | Agile / Adaptive | Predictive / Waterfall |
| Scope of change | Clarification / minor CR | New functionality / architectural CR |
| Affected stakeholders | 1–2 | 3+ or the sponsor |
| Regulatory context | None | Present (compliance, audit) |
| Project stage | Early / Discovery | Close to release |

**Rule:** In Predictive projects, every CR is potentially disruptive — it means redoing completed work. In Agile, the change is folded into the next sprint, so formality is lower.

Many CRs get withdrawn from consideration **before** formal analysis — the initiator reformulates or withdraws the request after an initial conversation.

---

## Five impact analysis axes

### Axis 1 — Benefit
What the business or user gains if the CR is accepted.

| Rating | Description |
|--------|----------|
| High (3) | Direct business value: new revenue, reduced costs, compliance |
| Medium (2) | Improved UX, faster process, reduced operational load |
| Low (1) | Cosmetic changes, convenience with no measurable effect |

**Entered by:** the BA, based on business context.

### Axis 2 — Cost
**Full cost** consists of three components:
- Direct cost of implementing the CR
- Cost of reworking related requirements/components
- **Opportunity cost** — what gets postponed or dropped from the backlog

| Rating | Description |
|--------|----------|
| Low (3) | Minor edits, 1–2 affected requirements, no impact on the roadmap |
| Medium (2) | Moderate scope, 3–7 affected, small schedule shift |
| High (1) | Major rework, 8+ affected, serious schedule shift or cancellation of other features |

**Entered by:** the BA. Technical effort estimates are requested from developers.

### Axis 3 — Impact
The number of customers, users, or business processes affected by the CR.
**Calculated automatically** from the 5.1 traceability graph (BFS traversal from the changed requirement).

| Rating | Description |
|--------|----------|
| High (3) | 8+ requirements affected, or key business processes |
| Medium (2) | 3–7 requirements affected |
| Low (1) | 1–2 requirements affected, isolated change |

**Calculated by:** automatically, in `run_cr_impact`, based on `run_impact_analysis` from 5.1.

### Axis 4 — Schedule
Impact on existing delivery commitments.
**Calculated automatically** based on the number of affected nodes and relation types.

| Rating | Description |
|--------|----------|
| Low risk (3) | The change fits within the current sprint/iteration |
| Medium risk (2) | Requires rescheduling 1–2 tasks or a small milestone shift |
| High risk (1) | Threatens the release deadline or requires a roadmap revision |

**Calculated by:** automatically, in `run_cr_impact`.

### Axis 5 — Urgency
How critical it is to accept the CR right now.

| Rating | Description |
|--------|----------|
| Critical (3) | Regulatory requirement, security issue, business blocker |
| High (2) | Important for the upcoming release, external commitments exist |
| Normal (1) | Desirable, but can wait for the next iteration |

**Entered by:** the BA.

---

## Scoring formula

```
CR Score = (Benefit × 2) + (Urgency × 1.5) + (Impact × 1) - (Cost × 1.5) - (Schedule_Risk × 1)
```

**The weights reflect priorities:**
- Benefit × 2 — value matters most
- Cost × 1.5 — cost is the second most significant constraint
- Urgency × 1.5 — urgency can outweigh cost
- Impact and Schedule are contextual factors

**Range and thresholds:**

| Score | Preliminary verdict |
|-------|------------------------|
| ≥ 8.0 | ✅ Approve — high value, acceptable cost |
| 4.0–7.9 | 🟡 Modify — scope or timeline should be revisited |
| 1.0–3.9 | ⏳ Defer — postpone to the next iteration |
| < 1.0 | ❌ Reject — cost outweighs value |

**Important:** the formula produces a *preliminary* verdict. Claude analyzes the context and may adjust the recommendation with an explicit rationale.

---

## Automated checks during scoring

In addition to the numeric score, the system checks:

### Check 1 — Traceability to the need
The CR must trace back to a business requirement (BR) through the 5.1 graph.
If no path to a BR is found → ⚠️ warning: "CR does not trace to a business need."

### Check 2 — Conflicts with priorities
If the CR changes a requirement from 5.3:
- The requirement was Won't → becomes Must: 🔴 critical conflict
- The requirement was Must → gets downgraded: ⚠️ requires a re-prioritization review

### Check 3 — Volatility of affected requirements
If any affected requirement has version 1.3+ (from 5.2) → 🟡 risk flag:
unstable requirements + CR = double uncertainty.

### Check 4 — Dependency violations
If the CR turns a dependent (depends) Won't requirement into a Must →
the dependency chain from 5.1 is automatically checked.

---

## Types of CR decisions

| Decision | When | Who is authorized |
|---------|-------|----------------|
| **Approve** | The CR increases value, cost is acceptable | Sponsor / CCB / Product Owner |
| **Approve with Modification** | The CR is accepted with a reduced scope | BA + Sponsor |
| **Defer** | The CR is valuable, but not right now | BA / Product Owner |
| **Reject** | The CR provides no value or is unacceptably expensive | CCB / Sponsor |

Exactly who is authorized is determined in task 3.3 (Governance approach).
`resolve_cr` takes a `decided_by` parameter — it must always be specified.

---

## Requirement statuses after resolve_cr

| CR decision | Status of affected requirements | Next BA step |
|------------|------------------------------|-----------------|
| Approved | `under_change` | Update the content via 5.2 |
| Approved with Modification | `under_change` (partial) | Clarify the scope, update via 5.2 |
| Deferred | No change | The CR is kept in the repository with status `deferred` |
| Rejected | No change | The CR is kept with status `rejected` (audit) |

**Important:** requirements with status `under_change` are not deleted or automatically modified.
The BA makes the substantive changes manually, via `update_requirement` (5.2).

---

## Special cases

### Regulatory CR
If the CR is driven by a change in legislation or regulations:
- Urgency automatically → Critical
- Reject is not an option (compliance cannot be declined)
- The only open questions are timing and implementation scope
- It is recommended to involve the Regulator/Auditor from the 5.4.7 stakeholder list

### CR in a Predictive project close to release
- High likelihood that even a small CR means major rework
- Schedule Risk is automatically raised by one level
- The BA must explicitly set `project_phase = "pre_release"` in `open_cr`

### Multiple related CRs
Sometimes several CRs affect the same requirements.
Recommendation: assess them together, not one at a time — the combined impact can be non-linear.
You can specify `related_cr_ids` in `open_cr` to link them in the repository.

---

## Stakeholders and their role in 5.4

| Stakeholder | Role in 5.4 |
|-------------|-----------|
| Sponsor | Final decision on the CR, accountable for scope |
| Project manager | Assesses impact on the plan and resources |
| Developer/Architect | Assesses technical cost (Cost, Schedule) |
| Tester | Assesses impact on test coverage |
| Business expert | Assesses value (Benefit) and business context |
| Regulator/Auditor | Verifies compliance for regulatory CRs |
| End user | Provides feedback on impact to their work |

---

## Common BA mistakes when assessing a CR

**1. Assessing only direct cost**
Opportunity cost is often forgotten: what gets postponed if the CR is approved?
Always ask: "What will we NOT do if we take on this CR?"

**2. CR with no traceability to a need**
"I want to add a feature" ≠ a business need. Every CR must answer the question:
"What business or user problem does this solve?"

**3. Ignoring scope creep**
A single CR looks small but pulls in 10+ related requirements.
Always run `run_cr_impact` — the graph will reveal the real scope.

**4. Letting CRs pile up without decisions**
A CR sitting in `open` status for more than 2 sprints is a governance problem.
The platform has no dedicated monitor: open CRs are visible in the 5.1 repository —
`export_traceability_matrix` lists `change_request` nodes with their statuses.

**5. Missing rationale on Reject**
Six months later, nobody remembers why it was rejected. Always fill in `rationale` in `resolve_cr`.
