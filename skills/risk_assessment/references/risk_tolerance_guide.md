# Risk Tolerance Guide — BABOK Chapter 6.3

A reference guide on risk tolerance levels and threshold calibration.
Read it before calling `set_risk_tolerance`.

---

## 1. What Risk Tolerance is

**Risk Tolerance** is the maximum level of risk the organization/sponsor
is willing to accept without escalation or a change to the plan.

It is defined by two parameters:

| Parameter | Description | Default value |
|----------|----------|-----------------------|
| `tolerance_level` | Strategic position (qualitative) | `neutral` |
| `max_acceptable_score` | Numeric threshold: risks ≥ this value = High | `15` |

These two parameters are related but not rigidly tied: the BA can set `risk_averse`
with a threshold of 12, or `neutral` with a threshold of 18 — depending on context.

---

## 2. Tolerance levels

### `risk_averse` — Conservative organization

**Characteristics:**
- Any risk Medium or above requires an active mitigation plan
- High bar for accepting uncertainty
- Strong emphasis on compliance and predictability
- A mistake costs more than a missed opportunity

**Typical indicators:**
- Regulated industry (banking, insurance, pharma, public sector)
- History of major project failures
- Sponsor with low risk appetite
- Critical infrastructure / operations

**Recommended threshold:** `max_acceptable_score = 10–12`

**How it affects the recommendation:**
With `risk_averse`, the `proceed_with_mitigation` recommendation requires
a clear plan for ALL risks ≥ the threshold, including a mandatory owner.

---

### `neutral` — Balanced position (default)

**Characteristics:**
- Risks are evaluated on a cost/benefit basis
- Willingness to accept Medium risks without an active plan when impact is low
- Standard corporate approach to risk management

**Typical indicators:**
- Commercial company in a competitive environment
- Projects with moderate stakes
- Sponsor with a balanced risk appetite

**Recommended threshold:** `max_acceptable_score = 15` (the High-zone boundary)

---

### `risk_seeking` — Aggressive position

**Characteristics:**
- Willingness to accept High risks for potential upside
- Speed to market matters more than predictability
- A missed opportunity = a bigger risk than a mistake

**Typical indicators:**
- Startups and scale-up companies
- Digital transformation with a first-mover scope
- Time constraints (market window)
- Innovation / R&D projects

**Recommended threshold:** `max_acceptable_score = 18–20`

---

## 3. Threshold calibration matrix

| Tolerance Level | Conservative threshold | Standard | Aggressive |
|-----------------|---------------------|-------------|-------------|
| `risk_averse` | 8–10 | **10–12** | 12–14 |
| `neutral` | 12–14 | **15** | 16–18 |
| `risk_seeking` | 15–16 | **18** | 20–22 |

**Bold** marks the recommended default value for the level.

---

## 4. Industry examples

### Banking / Financial Services
- **Tolerance:** `risk_averse`
- **Threshold:** 10–12
- **Typical High risks:** compliance/regulatory (score 15–25), data breach (20–25)
- **Note:** regulatory risks often carry a mandatory `avoid` status regardless of score

### Retail / E-commerce
- **Tolerance:** `neutral`
- **Threshold:** 15
- **Typical High risks:** seasonal load spikes (technical), competitors (strategic)
- **Note:** for seasonal projects — tight deadlines raise operational risks

### Manufacturing / Industrial
- **Tolerance:** `neutral` → `risk_averse` for health & safety risks
- **Threshold:** 12–15
- **Typical High risks:** equipment downtime (operational), safety (regulatory)

### IT / SaaS / Digital
- **Tolerance:** `neutral` → `risk_seeking`
- **Threshold:** 15–20
- **Typical High risks:** technical implementation (4–5), adoption (people, 3–4)

### Public Sector / Government Projects
- **Tolerance:** `risk_averse`
- **Threshold:** 8–12
- **Typical High risks:** political changes (external), procurement (regulatory)
- **Note:** compliance risks = almost always `avoid`

### Pharmaceutical / MedTech
- **Tolerance:** `risk_averse` (always)
- **Threshold:** 8–10
- **Typical High risks:** regulatory approval, clinical data quality, patient safety
- **Note:** any risk with impact=5 (Critical) → mandatory escalation

---

## 5. Dialogue with the BA to determine tolerance

If the sponsor hasn't set tolerance explicitly — help the BA determine it through questions:

**Question 1 — about history:**
> "How does your organization typically react when a project hits
> an unexpected problem midway through — does it stop to analyze
> or adapt and keep moving?"

Answer "stops" → `risk_averse`
Answer "adapts" → `neutral` or `risk_seeking`

**Question 2 — about the cost of a mistake:**
> "What's worse for the sponsor: spending an extra 20% of the budget on
> preventive measures, or facing a 30% chance of a 2-month delay?"

Prefers to spend upfront → `risk_averse`
Willing to risk the delay → `neutral` or `risk_seeking`

**Question 3 — about regulation:**
> "Does the project involve regulatory requirements whose violation carries
> legal liability or fines?"

Yes → `risk_averse` is mandatory, at least for the regulatory category

---

## 6. Risk Context — additional `set_risk_tolerance` fields

Besides `tolerance_level` and `max_acceptable_score`, the tool accepts:

| Field | Description |
|------|----------|
| `organization_context` | Brief description of the context (industry, project type) |
| `sponsor_risk_appetite` | Direct quote or interpretation of the sponsor's position |
| `mandatory_avoid_categories` | Risk categories that always → avoid (e.g.: `["regulatory"]`) |
| `escalation_threshold` | Score at which escalation to the sponsor is required (usually = max_acceptable_score) |

---

## 7. How tolerance affects `generate_recommendation`

| Condition | Tolerance | Recommendation |
|---------|-----------|--------------|
| No risks ≥ threshold | any | `proceed_despite_risk` |
| Risks ≥ threshold exist | `risk_seeking` | `proceed_with_mitigation` |
| Risks ≥ threshold exist | `neutral` | `proceed_with_mitigation` |
| Risks ≥ threshold exist | `risk_averse` + mitigation possible | `proceed_with_mitigation` |
| Potential value < exposure | any | `seek_higher_value` |
| Risks are critical, mitigation impossible | any | `do_not_proceed` |

**`do_not_proceed`** — a rare but important decision. Indicators:
- A risk with impact=5 (Critical) and likelihood ≥ 4 with no mitigation plan
- ≥ 3 risks with score ≥ 20 under `risk_averse`
- mandatory_avoid_categories are violated

---

## 8. Revisiting tolerance during the project

Tolerance isn't a constant. Revisit it when:
- Sponsor or key stakeholders change
- New regulatory requirements appear
- Significant change to scope or budget
- After key mitigation plans are executed (risks reduced → worth revisiting)

When revisiting — call `set_risk_tolerance` again with new parameters,
then `run_risk_matrix` to recompute zones and `generate_recommendation` for an updated recommendation.
