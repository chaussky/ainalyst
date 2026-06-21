# Risk Assessment Guide — BABOK Chapter 6.3

A reference guide for identifying, assessing, and planning response measures for risks.
Read it when you need details on a specific assessment step.

---

## 1. Risk categories (BABOK 6.3)

| Category | Description | Examples |
|-----------|----------|---------|
| `strategic` | Risks to achieving strategic objectives | Competitors launched a similar offering first; strategy changed mid-project |
| `operational` | Risks of disrupting operational processes | Key staff leave the project; changes to business processes cause disruptions |
| `financial` | Financial risks: budget, ROI, cost | Budget cut by 30%; OPEX grows more than planned |
| `technical` | Technical implementation risks | Integration with the legacy system is harder than expected; tech stack is outdated |
| `regulatory` | Regulatory and compliance risks | Legal requirements changed; new GDPR regulation; industry standard |
| `people` | People: skills, change, culture | Low user adoption; BA team is understaffed; hidden resistance |
| `external` | External factors: market, environment, force majeure | Vendor goes bankrupt; exchange rate shifts; pandemic |

**Classification rule:** if a risk fits multiple categories — choose the one its **root cause** originates from.

---

## 2. Likelihood rating scale

| Score | Level | Probability | Indicators |
|------|---------|-------------|----------|
| 1 | Very Low | < 10% | Theoretically possible, no historical precedent |
| 2 | Low | 10–30% | Rarely occurred in similar projects |
| 3 | Medium | 30–60% | Occurs in roughly half of similar projects |
| 4 | High | 60–80% | Common outcome without special measures |
| 5 | Very High | > 80% | Almost inevitable under current conditions |

**How to calibrate:**
- Use historical data from similar projects in the organization
- Rely on stakeholder estimates (especially risk owners)
- Consider context from 6.1 (root causes) and 6.2 (gaps, constraints)

---

## 3. Impact rating scale

| Score | Level | Description | Impact examples |
|------|---------|----------|---------------------|
| 1 | Negligible | Minimal, virtually no effect | Minor delay of a single step |
| 2 | Minor | Small, locally resolvable | Sprint delay; extra budget < 5% |
| 3 | Moderate | Noticeable, requires plan adjustment | Milestone delay of 2–4 weeks; budget +10–20% |
| 4 | Major | Substantial, threatens project objectives | Failure of a key business objective; budget +30–50% |
| 5 | Critical | Catastrophic, project/program is at risk | Complete shutdown; loss of license; legal liability |

**Impact dimensions (choose the most critical one):**
- **Time:** delivery delay
- **Cost:** budget overrun
- **Scope:** degradation of capabilities/features
- **Quality:** technical debt, defects
- **Reputation:** stakeholder trust, brand

---

## 4. Risk Matrix

```
Impact →
  5  |  5  | 10  | 15  | 20  | 25
  4  |  4  |  8  | 12  | 16  | 20
  3  |  3  |  6  |  9  | 12  | 15
  2  |  2  |  4  |  6  |  8  | 10
  1  |  1  |  2  |  3  |  4  |  5
     |  1  |  2  |  3  |  4  |  5  ← Likelihood
```

### Risk zones

| Zone | Score | Color | Default action |
|------|-------|------|----------------------|
| Low | 1–5 | 🟢 Green | Accept or monitor |
| Medium | 6–14 | 🟡 Yellow | Develop a mitigation plan |
| High | 15–25 | 🔴 Red | Urgent response, escalation |

**Default High boundary = 15** (score ≥ 15 = High risk).
The BA can override the threshold via `set_risk_tolerance`.

---

## 5. Risk sources for identification

When working with `import_risks_from_context`, the platform automatically scans:

| Source | Artifact | What is extracted |
|----------|----------|---------------|
| 6.2 — constraints | `{project}_future_state.json` → `constraints[]` | Constraints with category+description → risk drafts |
| 6.2 — gap analysis | `{project}_gap_analysis.json` → `gaps[]` | Gaps with complexity=high → highly complex transitions |
| 6.1 — root causes | `{project}_current_state.json` → `rca` | root_causes with severity → unresolved causes |
| 6.1 — business needs | `{project}_business_needs.json` | Needs with priority=high → risks of non-fulfillment |
| 4.2 — interviews | `{project}_elicitation_results.json` → `risks_mentioned[]` | Risks mentioned by stakeholders |

**Graceful degradation:** if an artifact is missing — the source is skipped with a warning, not an error.

---

## 6. Response Strategies

### Accept
**When:** the risk is Low, or mitigating it costs more than the potential damage.
**Action:** record it, monitor it. No active measures.
**Example:** "If a key team member is out sick for 1 day — we'll accept the delay."

### Mitigate
**When:** the risk is Medium or High, and there are concrete mitigation measures available.
**Action:** develop a plan: what to do, who's responsible, by when.
**Goal:** reduce likelihood OR impact (ideally both).
**Example:** "We'll run an integration prototype in Sprint 0 to reduce the chance of surprises."

### Transfer
**When:** the risk can be shifted to a third party (vendor, insurer, partner).
**Action:** contract with a penalty clause; insurance; SLA; outsourcing the risky module.
**Example:** "We transfer the compliance risk to the vendor through a contractual guarantee."

### Avoid
**When:** the risk is Critical, and mitigation is impossible or too costly.
**Action:** change the scope, technology, approach, or drop the component.
**Example:** "We're removing the legacy system integration from v1.0 — it'll move to v2."

---

## 7. Common risk patterns by initiative type

### Process Improvement
- Staff resistance to change (people, likelihood 3–4)
- Underestimating training time (people/financial)
- Performance degradation during the transition period (operational)

### New System / Digital Transformation
- Integration complexity with legacy systems (technical, likelihood 3–4)
- Data migration: loss or corruption (technical/operational)
- Low adoption among end users (people)
- Budget overrun due to hidden requirements (financial)

### Regulatory / Compliance
- Regulator changes requirements after kickoff (regulatory, likelihood 2–3)
- Lack of expertise in the new standard (people)
- Fines for delayed implementation (regulatory/financial)

### Cost Reduction
- Service quality decline during optimization (operational)
- Loss of key staff during restructuring (people)
- Hidden dependencies in the optimized process (technical/operational)

---

## 8. Wording a risk

**Standard:** "If [condition/trigger], then [consequence]"

**Good wording:**
- ✅ "If the ERP system integration turns out harder than the prototype showed, then the delivery date will slip by 4–6 weeks"
- ✅ "If key business users don't complete training before go-live, then the adoption rate will be below 50% in the first 3 months"

**Bad wording:**
- ❌ "Integration risk" (no condition or consequence)
- ❌ "Delays are possible" (no specifics)
- ❌ "Users won't use the system" (no trigger)

---

## 9. Risk card structure (`add_risk` fields)

| Field | Type | Required | Description |
|------|-----|----------------|----------|
| `category` | Literal | ✅ | strategic/operational/financial/technical/regulatory/people/external |
| `source` | Literal | ✅ | change/current_state/future_state/requirement/stakeholder/assumption/constraint |
| `description` | str | ✅ | Format: "If X, then Y" |
| `likelihood` | int 1–5 | ✅ | Per the scale in section 2 |
| `likelihood_rationale` | str | 📋 | Rationale for the estimate |
| `impact` | int 1–5 | ✅ | Per the scale in section 3 |
| `impact_rationale` | str | 📋 | Rationale for the estimate |
| `time_horizon` | Literal | 📋 | immediate/short_term/medium_term/long_term |
| `response_strategy` | Literal | ✅ | accept/mitigate/transfer/avoid |
| `mitigation_plan` | str | if mitigate | Concrete action plan |
| `owner` | str | 📋 | stakeholder_id from the 3.2 registry |
| `linked_bn` | str | 📋 | Business need ID (BN-xxx) |
| `linked_bg` | str | 📋 | Business goal ID (BG-xxx) |
| `linked_req` | str | 📋 | Requirement ID (FR-xxx, BR-xxx...) |

`risk_id` and `risk_score` are computed automatically.

---

## 10. Interpreting `run_risk_matrix` results

After calling `run_risk_matrix`, look at:

**`cumulative_profile`:**
- `high_risks_count` — risks with score ≥ max_acceptable_score
- `above_threshold` — same as high_risks_count (for compatibility)
- `total_score` — sum of all scores (the overall "weight" of the risk profile)
- `avg_score` — average score

**Signals for the BA:**
- `high_risks_count = 0` → clean profile, can proceed
- `high_risks_count ≥ 1 and ≤ 2` → proceed_with_mitigation
- `high_risks_count ≥ 3` → serious conversation with the sponsor needed
- `total_score > 100` → high cumulative load even with few high risks

---

## 11. Pipeline for task 6.3

```
scope_risk_assessment          # fix the scope: type, depth, sources
        ↓
import_risks_from_context      # auto-import drafts from 6.1, 6.2, 4.2
        ↓
add_risk × N                   # add risks (drafts + new ones)
        ↓
set_risk_tolerance             # tolerance level + max_acceptable_score
        ↓
run_risk_matrix                # matrix with zones, cumulative profile
        ↓
generate_recommendation        # recommendation type + narrative (Claude writes it)
        ↓
save_risk_assessment           # Markdown report + JSON + opt. push to 5.1
```
