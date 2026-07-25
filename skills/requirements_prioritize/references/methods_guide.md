# Reference: Requirement Prioritization Methods (BABOK 5.3)

## Four methods — when to choose which

| Method | Best fit | Requires from the team | Not suitable when |
|-------|---------------------|--------------------|-------------------|
| **MoSCoW** | Agile, fixed deadline, well-understood scope | Stakeholder opinions only | Many dependencies, precise quantitative scoring needed |
| **WSJF** | SAFe, product teams, competing backlogs | Cost estimates from developers | No effort estimates, team unfamiliar with the method |
| **Impact/Effort** | Initial ranking, limited resources, visualization | Relative impact and effort estimates | Precise numeric calculation required |
| **Time Boxing / Budgeting** | Fixed deadline or fixed budget; second pass after Must Inflation | A cost/size estimate per requirement + the capacity | Capacity genuinely unknown; scope cannot be cut |

**Selection rule:**
- No cost estimates → **MoSCoW** or **Impact/Effort**
- Cost estimates available + Agile project → **WSJF**
- Need to quickly rank 30+ requirements → **Impact/Effort** first, then MoSCoW for Must candidates
- Complex Enterprise project with dependencies → **WSJF** + automatic dependency-violation check from 5.1
- Fixed deadline or fixed budget → **Time Boxing/Budgeting**
- Over 60% Must after a MoSCoW pass → **Time Boxing/Budgeting** as a second pass: the
  capacity, not the stakeholders, does the cutting

---

## Method 1 — MoSCoW

### Four categories

| Category | Meaning | Typical share of the project |
|-----------|-------|------------------------|
| **Must** | Without this, the project has no point. Failure if missing. | ≤ 60% |
| **Should** | High value, but can be shipped without it in the first version | 20–30% |
| **Could** | Desirable, implemented if time and budget remain | 10–20% |
| **Won't** | Deliberately excluded from the current iteration (not "never") | any amount |

### Scoring scale
The BA enters one of: `Must` / `Should` / `Could` / `Won't` — per requirement, per stakeholder.

### Aggregation across multiple stakeholders

**Default rule (weighted voting by influence):**

```
Weighted score = Σ (stakeholder_score × influence_weight)
Weight: High = 3, Medium = 2, Low = 1
```

Numeric mapping of scores: Must=4, Should=3, Could=2, Won't=1

Final threshold:
- ≥ 3.5 → **Must**
- ≥ 2.5 → **Should**
- ≥ 1.5 → **Could**
- < 1.5 → **Won't**

### Common mistakes

- 🔴 **Must inflation** — more than 60% of requirements are Must → the session isn't working, needs re-facilitation
- 🔴 **Must depends on Won't** → logical contradiction, detected automatically via 5.1
- 🟡 **"Won't" interpreted as "never"** → it's important to explain to stakeholders: Won't = "not in this iteration"
- 🟡 **Empty Could category** → suspicious, usually means Should and Won't haven't been properly separated

---

## Method 2 — WSJF (Weighted Shortest Job First)

### Formula

```
WSJF = Cost of Delay ÷ Job Size

Cost of Delay (CoD) = Business Value + Time Criticality + Risk Reduction / Opportunity Enablement
```

**Principle:** do first whatever delivers the most value in the least time.

### Four components

| Component | What is scored | Typical question for the stakeholder |
|-----------|----------------|------------------------------|
| **Business Value (BV)** | Value to the business once implemented | "How valuable is this to your goals?" |
| **Time Criticality (TC)** | How much value decays over time | "What happens if we do this a quarter later?" |
| **Risk Reduction / OE** | Reduces risk or enables opportunities | "Does this block other initiatives?" |
| **Job Size (JS)** | Effort to implement (from developers) | Provided by the delivery team |

### Scales (two options — chosen before the session)

**Fibonacci (recommended for experienced teams — as in SAFe):**
`1, 2, 3, 5, 8, 13` — relative estimates, not absolute.
Key step: first pick a reference requirement = 3 (average), then score the rest relative to it.

**Linear (1–10) — simpler for new teams:**
`1` = minimal, `10` = maximal.
Drawback: people gravitate toward mid-range scores (5–7), losing differentiation.

### Interpreting the result

```
WSJF > 5.0  → 🔴 High priority — do immediately
WSJF 2.0–5.0 → 🟡 Medium priority
WSJF < 2.0  → 🟢 Low priority — do when resources free up
```

*The thresholds are approximate — the relative ranking within the requirement set matters more.*

### Example calculation

| Requirement | BV | TC | RR/OE | CoD | JS | WSJF |
|------------|----|----|-------|-----|----|------|
| FR-001 | 8 | 5 | 3 | 16 | 3 | **5.3** |
| FR-002 | 5 | 2 | 1 | 8 | 5 | **1.6** |
| FR-003 | 13 | 8 | 5 | 26 | 8 | **3.3** |

Order: FR-001 → FR-003 → FR-002

### Common mistakes

- 🔴 **Small Job Size automatically means high WSJF** — must verify: a "small" requirement may actually be large
- 🟡 **Job Size set by the BA, not by developers** — effort estimates should come from the delivery team
- 🟡 **All CoD scores are identical** — stakeholders didn't differentiate, a follow-up session is needed

---

## Method 3 — Impact/Effort Matrix

### Four quadrants (default names)

```
HIGH IMPACT
    │
    │  Big Bets          Quick Wins
    │  (high impact,     (high impact,
    │   high effort)      low effort)
    │
    ├───────────────────────────────── EFFORT
    │
    │  Thankless Tasks   Fill-ins
    │  (low impact,      (low impact,
    │   high effort)      low effort)
    │
LOW IMPACT
         HIGH EFFORT      LOW EFFORT
```

### Scoring scale

**Impact** (value/influence): `Low` / `Medium` / `High`
**Effort** (effort/complexity): `Low` / `Medium` / `High`

### Quadrant → priority mapping (configured by the BA before the session)

**Default mapping (recommended as a starting point):**

| Quadrant | Impact | Effort | Default MoSCoW priority |
|----------|--------|--------|---------------------------|
| Quick Wins | High | Low | Must |
| Big Bets | High | High | Should |
| Fill-ins | Low | Low | Could |
| Thankless Tasks | Low | High | Won't |

**Configurable mapping:** the BA can change any mapping before the session.
For example, on a regulatory project, Big Bets → Must (despite the high effort).

### Interpreting Medium values

If impact = Medium or effort = Medium, the requirement falls into a "gray zone."

Default rule:
- Medium/Low → treated as High/Low for prioritization
- Medium/High → treated as Low/High
- Medium/Medium → Must/Should at the BA's discretion (flagged separately)

### When to use it as the primary method

- The team isn't used to numeric scoring
- Need to quickly rank 30+ requirements in a workshop
- Visualization for stakeholders (the matrix is intuitive)
- As an initial filter before a more precise MoSCoW/WSJF pass

---

## Method 4 — Time Boxing / Budgeting

BABOK 10.33.3 .3: prioritization "based on the allocation of a fixed resource".
Time boxing uses the amount of work the team can deliver in a period; budgeting uses
a fixed amount of money. The arithmetic is the same — only the unit differs.

### What it needs

| Input | Where it comes from |
|---|---|
| `capacity` + `capacity_unit` | The BA, when opening the session |
| `cost` per requirement | The team's estimate, supplied like any other score (e.g. as `stakeholder_id="DEV-TEAM"`) |
| `value` per requirement | Optional. Given → used; omitted → the requirement's current priority in the 5.1 graph |

`cost` is averaged across whoever supplied it **without** influence weighting — a size
estimate is a fact about the work, not an opinion. Where estimates disagree, the report
prints the spread instead of hiding it inside the average.

### How the box is filled

1. Requirements are ordered by value (Must → Should → Could → Won't), then cheapest
   first, then by id.
2. They are added while `cumulative + cost <= capacity`.
3. A requirement that does not fit is skipped, and **cheaper ones below it are still
   considered** — the report names every requirement that was skipped over, so the
   trade-off is visible rather than silent.

The box covers the **whole backlog**, not only what was scored: a requirement nobody
estimated is named explicitly rather than quietly missing from the document.

### What the result means

- **In the box** — the requirement keeps its own value label (a `Could` in the box
  stays `Could`: it was committed, but it is the bottom of the value order).
- **Cut** — `Won't`, in the literal MoSCoW sense of "won't have **this time**".
- **Not estimated** — no priority is written at all. A requirement with no cost
  cannot be placed in a capacity box, and calling it `Won't` would be a conclusion
  drawn from missing data.

### Dependencies

A requirement in the box that depends on a cut one makes the box infeasible. The
platform flags it as a dependency violation and leaves the decision to the BA — raise
the prerequisite's value, drop the dependent requirement, or decompose it. It does
**not** quietly pull prerequisites in: that would rewrite the value order the
stakeholders agreed, and the signed artefact would not show it.

### Common mistakes

- **Capacity taken from a plan instead of from history.** Use what the team actually
  delivered, not what was promised.
- **Costs from one optimistic voice.** Where estimates differ, the report prints the
  spread — a 3-vs-13 disagreement is a conversation, not an average.
- **Treating the box as a commitment for all time.** It is one period. Re-run it.

---

## Eight BABOK factors — mapping to the methods

| BABOK factor | MoSCoW | WSJF | Impact/Effort | Time Boxing |
|-------------|--------|------|---------------|-------------|
| Benefit | ✅ Business Value | ✅ BV component | ✅ Impact | ✅ the value ranking |
| Penalty | ✅ Must if the penalty is critical | ✅ RR/OE component | ✅ Impact | ⬜ via the value ranking only |
| Cost | ⬜ not accounted for | ✅ Job Size | ✅ Effort | ✅ **the fixed resource itself** |
| Risk | ⬜ partially | ✅ RR/OE component | ⬜ partially via Impact | ⬜ |
| Dependencies | ⚠️ needs manual check | ⚠️ needs manual check | ⚠️ needs manual check | ⚠️ needs manual check |
| Time sensitivity | ⬜ not accounted for | ✅ TC component | ⬜ not accounted for | ✅ the period is the constraint |
| Stability | ⬜ | ⬜ | ⬜ | ⬜ |
| Regulatory compliance | ✅ Must by default | ✅ high CoD | ✅ Must via mapping | ✅ Must by default |

**Conclusion:** dependencies and stability are not automatically accounted for by any of the methods.
That is exactly why the platform integrates 5.3 with the 5.1 repository and the 5.2 attributes:
dependencies and stability are checked **before** and **after** the priority calculation.

---

## Combined approach

For large projects, a two-stage prioritization is recommended:

**Stage 1 (fast):** Impact/Effort → filter out Thankless Tasks, surface Quick Wins

**Stage 2 (precise):** MoSCoW or WSJF → prioritize the remainder in detail (excluding Stage 1's Won't items)

This reduces the number of requirements needing detailed analysis by 20–30%.
