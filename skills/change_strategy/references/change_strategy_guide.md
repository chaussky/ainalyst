# change_strategy_guide.md — Guide to Defining the Change Strategy

## 1. What is a change strategy (BABOK 6.4)

A change strategy is a **substantiated choice** of how the organization will transition
from the current state (6.1) to the future state (6.2), taking into account risks (6.3)
and organizational readiness.

The output of 6.4 isn't just "we'll do it this way" — it's a structured document:
- **Solution Scope** — exactly what is in the scope of the solution (capabilities)
- **Change Strategy** — which options were chosen from, and why
- **Transition States** — the transition phases and what's delivered in each

---

## 2. Types of change strategies

### big_bang
**Essence:** A one-time cutover — the new solution launches in full, the old one is switched off.

**When it fits:**
- Small-scale systems
- High interdependency between components (can't be implemented partially)
- Hard regulatory deadlines
- Experienced team, manageable risks

**Advantages:** Speed, a single wave of change, no long co-existence period
**Risks:** High operational risk, no rollback path

---

### phased
**Essence:** A step-by-step transition — functionality and capability blocks are rolled out sequentially.

**When it fits:**
- Large systems with independent functional blocks
- An organization with a low change_history
- Value needs to be delivered incrementally
- Funding arrives in tranches

**Advantages:** Manageable risk, early value, feedback after each phase
**Risks:** Long co-existence period, more complex transition-state architecture

---

### pilot_first
**Essence:** Pilot first on a limited audience → validation → scale-up.

**When it fits:**
- High uncertainty in the solution
- Need to validate hypotheses before full investment
- A suitable "safe" pilot group is available
- An innovative or unproven solution

**Advantages:** Minimal risk, real data before scaling
**Risks:** Longer path to full implementation, risk of a "perpetual pilot"

---

### do_nothing
**Essence:** Change nothing — leave the current state as is.

**When it fits:** Never (as the chosen option). Used as the **baseline**
for comparison: what happens if we do nothing?

**Mandatory to consider per BABOK** — so the BA explicitly justifies:
"The current state is unacceptable because..."

---

## 3. Capability Categories

A capability is an **ability** that the organization will gain as a result of the change.

| Category | What it includes |
|-----------|-------------|
| `process` | Business processes, workflows, regulations |
| `technology` | Software systems, infrastructure, integrations |
| `data` | Data, analytics, storage, data quality |
| `people` | Knowledge, skills, staff competencies |
| `org_structure` | Organizational structure, roles, accountability |
| `knowledge` | Documentation, knowledge base, standards |
| `location` | Physical offices, points of presence, logistics |

---

## 4. Gap Severity — from 6.2 to 6.4

In `define_solution_scope`, each capability receives a `gap_severity`:

| Level | Meaning | How it affects the strategy |
|---------|----------|-----------------------------|
| `none` | The capability already exists | May be outside the active scope |
| `low` | Small gap, easy to close | Usually in the early phases of a phased rollout |
| `medium` | Significant gap, requires effort | Planned in the main phases |
| `high` | Critical gap, hard to close | Often determines the phase structure |

**`gap_severity` is yours, not the platform's.** The 6.2 gap analysis is auto-imported
into 6.4, but it stores `complexity` — how hard the change is — and that is a different
question from how big the gap is. The two share the words low/medium/high and mean
different things, so the import never writes `gap_severity`. It shows 6.2's `complexity`
beside your value, labelled, and leaves the judgement to you.

`gap_source` names **which 6.2 element** this capability covers, and that declaration is
the only link between the two chapters — the platform never infers it from the category
(6.2's eight elements and 6.4's seven categories overlap on just two values):

- `6.2:technology`, `6.2:policies`, `6.2:capabilities`, … — the 6.2 element covered.
  Valid elements: `business_needs`, `org_structure`, `capabilities`, `technology`,
  `policies`, `architecture`, `assets`, `external`.
- `manual` — the BA determined it independently, without reference to a 6.2 element.
- `6.2:gap_analysis` — the legacy form. It names a source, not an element, and is still
  accepted; coverage for that capability is then reported as **uncheckable**, not as
  uncovered.

With the element named, `define_solution_scope` and the final Change Strategy document
both report: which analysed gaps are covered, which no in-scope capability declares,
which are deliberately left out of scope, and how many capabilities could not be checked.
Where no gap analysis was imported, the platform says it did not check — it never
reports a count it cannot support.

---

## 5. Opportunity Cost — why it matters

**Definition:** The Opportunity Cost of option A = the best of what we give up by choosing A instead of the other options.

**BABOK requires:** When choosing a strategy — explicitly capture exactly what we lose
by rejecting the alternatives. This makes the decision defensible to the sponsor.

**Format:**
> "By choosing `phased` over `pilot_first`, we give up the ability
> to validate the solution with real users before full rollout.
> Assumption made: the requirements are clear enough and a pilot isn't needed."

**Typical BA mistakes:**
- "We chose option A because it's better" — no comparison
- Comparing only on cost, without accounting for time-to-value and risk
- Rejected options are mentioned in passing without justification

---

## 6. Weighted comparison criteria (ADR-081)

The default criteria and their meaning:

| Criterion | What it assesses | Default weight |
|----------|--------------|---------------|
| `alignment_to_goals` | How well the option achieves the business goals from 6.2 | 25% |
| `risk_mitigation` | How much the option reduces the top risks from 6.3 | 20% |
| `cost` | Inverse of the investment level (low cost = high score) | 20% |
| `time_to_value` | Speed of obtaining first value | 15% |
| `org_readiness_fit` | Fit with the readiness_score from the readiness assessment | 10% |
| `feasibility` | Technical and operational feasibility | 10% |

**Scoring scale:** 1–5 (1=poor, 5=excellent) for each criterion.
**Weighted Score** = Σ(score × weight / 100).

**Custom criteria:** can be added via `custom_criteria_json`.
The sum of weights (default + custom) must equal 100%.

---

## 7. Transition States — a structured phase plan

A Transition State is an intermediate state on the way to the future state.

Each phase must answer the questions:
1. **What capabilities are delivered** in this phase?
2. **What gaps are closed** by the end of the phase?
3. **What risks remain** after the phase (from 6.3)?
4. **What value is realizable** by the end of the phase (from 6.2)?

**The "each phase = standalone value" rule:**
If Phase 1 doesn't deliver standalone value, that's a sign of incorrect phase slicing.
The sponsor should see ROI already after the first phase.

**Example for a phased strategy (CRM upgrade):**

| Phase | Capabilities | Gaps closed | Value |
|------|-------------|-------------|-------|
| 1 (3 mo) | Base CRM + call center integration | gap_crm_data | Agents see customer history |
| 2 (5 mo) | Analytics module + automation | gap_reporting | 60% reduction in manual reporting |
| 3 (4 mo) | Self-service + mobile | gap_self_service | NPS +15 points |

---

## 8. Solution Scope — what to include and what to explicitly exclude

`explicitly_excluded` is not "what we forgot" — it's **deliberate decisions**.

**Why capture exclusions:**
- Prevents scope creep in Chapter 7
- Sets stakeholder expectations
- Creates a basis for future phases or separate initiatives

**Examples of good exclusion statements:**
- "Migration of historical data from Archive_2015–2018 — out of scope: data is no longer needed"
- "Customer-facing mobile app — out of scope: carved out into a separate Q3 initiative"
- "Integration with partner APIs — out of scope until phase 2 is complete"

---

## 9. When to choose each strategy — decision matrix

| Factor | big_bang | phased | pilot_first |
|--------|----------|--------|-------------|
| Scale | Small / medium | Any | Any |
| org_readiness maturity | High | Medium | Any |
| Solution uncertainty | Low | Medium | High |
| Component dependency | High | Low | Medium |
| Funding | Lump sum | Incremental | Incremental |
| Priority on time-to-value | Not critical | Important | Important |
| Availability of a pilot group | Not needed | Not needed | Required |

---

## 10. Downstream contract (what tasks 7.x and 8.x use)

| Field in JSON | Who uses it | Why |
|-------------|---------------|-------|
| `solution_scope.capabilities` | 7.1 | What to specify |
| `change_strategy.transition_states` | 7.4 | Architecture by phase |
| `change_strategy.selected_option_id` | 7.5 | Design constraints |
| `change_strategy.options[].pros/cons` | 7.5 | Context on the rejected alternatives |
| `transition_states[].value_realizable` | 7.6 | Value by phase |
| `transition_states[].risks_remaining` | 8.x | Risk baseline for monitoring |
