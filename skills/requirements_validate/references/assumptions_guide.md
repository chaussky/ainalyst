# assumptions_guide.md — Working with Assumptions (BABOK 7.3)

## What an Assumption is

**Assumption** — a statement accepted as true without proof.

Assumptions are especially critical when:
- The organization is launching an **unprecedented product** (no historical data)
- A **cause-and-effect relationship** between the problem and the solution cannot be proven
- **Integrations** depend on the behavior of third-party systems
- **Users** must change their habits

An unidentified assumption is a hidden risk. When it's refuted, the project veers off in an unexpected direction. It's better to log it and verify it.

---

## Classification by risk_level

### 🔴 High risk

**When to assign:**
- Being refuted would change the solution architecture or eliminate a req
- Depends on actions of stakeholders outside the BA's sphere of influence
- Requires technical verification before development starts

**Examples:**
- "We assume the legacy system supports a REST API"
- "We expect 95% of users to switch from email notifications to push"
- "We believe the volume of data to migrate will not exceed 10 million records"

**Consequence:** `mark_req_validated` issues a warning while it remains open.

---

### 🟡 Medium risk

**When to assign:**
- Being refuted would require adjusting a req, but not revisiting the architecture
- Can be verified during development (not necessarily before kickoff)

**Examples:**
- "We assume operators are willing to undergo 2 hours of training"
- "We expect peak load not to exceed 1000 RPS"
- "We believe the company's design system covers all the needed components"

---

### 🟢 Low risk

**When to assign:**
- Being refuted would not require changes to the req
- Easy to verify or has a low probability of being refuted

**Examples:**
- "We assume the target audience's browsers support ES2020"
- "We expect a stable exchange rate over the development period"
- "We believe the team's technical stack allows the req to be implemented"

---

## When to identify assumptions

**Before development starts:**
- When analyzing each req: "What needs to be true for this to be implemented?"
- During check_business_alignment: an orphan req often hides an unverified assumption
- When dealing with legacy integrations: always

**During elicitation (4.1–4.3):**
- When stakeholders contradict each other: "One person made an assumption, another didn't"
- On phrases like "we thought that...", "usually we...", "they probably..."

**When requirements change (5.4 CR):**
- Every CR can refute previously accepted assumptions
- Check `{project}_assumptions.json` when processing a CR

---

## How to confirm / refute

### Confirmation methods

| Method | Best suited for |
|-------|-------------|
| Stakeholder interview | Behavioral assumptions |
| Technical spike | Technical and integration assumptions |
| Pilot / MVP | User-related assumptions |
| Documentation review | System, legacy integration assumptions |
| Prototype + UX test | Assumptions about UX |
| Data analysis | Quantitative assumptions (load, volume) |

### What to write in resolution_note

**Good:**
> "Ran a technical spike with the team. The legacy system's REST API supports version 2.1, the /orders/list method is available. Confirmed 2025-03-10."

**Bad:**
> "Checked it."

A good resolution_note is an audit trail. Three months from now, someone will ask "why did we decide it this way."

---

## Common assumptions in IT projects

### Technical

| Assumption | How to verify |
|-----------|--------------|
| "The legacy system has an API" | Technical spike, vendor documentation |
| "DB response time ≤ N ms" | Load testing, query plan |
| "The migration data volume is known" | SQL query against the prod database (if access is available) |
| "The SSO provider supports the required flow" | Documentation, test environment |

### User-related

| Assumption | How to verify |
|-----------|--------------|
| "Users will accept the new interface" | UX test with real users |
| "Operators are ready for training" | Interview with HR, survey of operators |
| "Mobile usage < 20%" | Analytics, if the product already exists |

### Business-related

| Assumption | How to verify |
|-----------|--------------|
| "The customer will allocate budget for phase 2" | Documented in the contract or an ROI justification |
| "The regulator will approve the change" | Legal review |
| "Competitors won't ship an equivalent before the release" | Market monitoring |

---

## How assumptions relate to project risk

An assumption is a passive risk. It becomes active when refuted.

**Mapping risk_level → project response:**

| risk_level | What to do when `refuted` |
|-----------|------------------------|
| high | Immediate pivot: revisit the req, notify the customer |
| medium | CR process (5.4): assess impact on scope/schedule |
| low | Minor adjustment to the req, no escalation |

**Pattern for the DEVLOG:** for every `refuted` case, log:
- Which req was affected
- What changed in the requirements
- Cost of the change (hours, sprint)

---

## Numbering and storage

Assumptions are stored in `governance_plans/{project}_assumptions.json`.

**Structure of a single assumption:**
```json
{
  "assumption_id": "AS-001",
  "description": "Text of the assumption",
  "req_ids": ["US-001", "FR-003"],
  "risk_level": "high",
  "status": "open",
  "assigned_to": "A. Petrova",
  "created_at": "2025-03-10",
  "resolved_at": null,
  "resolution_note": ""
}
```

**Statuses:**
- `open` → not yet verified
- `confirmed` → confirmed (req remain valid)
- `refuted` → refuted (req up for revision)
