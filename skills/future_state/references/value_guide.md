# Reference Guide: Potential Value in 6.2 (BABOK)

## Why assess value in 6.2

At the 6.2 stage, we don't yet have a specific solution — only a desired future state.
That's why the assessment is **qualitative**: a structured list of benefits with types and weights.

**Distinguishing 6.2 vs 7.6:**
- **6.2** — "is it worth moving toward this future state" → qualitative, no formula
- **7.6** — "which solution to choose and how beneficial it is" → quantitative, with a formula

Data from 6.2 becomes context for 7.6: the BA doesn't start from scratch, but refines
an already-structured vision of value.

---

## Benefit types

| Type | What belongs here | Examples |
|-----|----------------|---------|
| `financial` | Direct financial effect — savings, revenue | Lower operating costs, revenue growth, reduced losses |
| `operational` | Improved operational efficiency | Faster processes, fewer errors, higher productivity |
| `strategic` | Strategic positioning | New markets, competitive advantages, flexibility |
| `compliance` | Meeting requirements | Fulfilling regulatory requirements, reducing penalty risk |

---

## Magnitude (scale of the benefit)

| Value | When to use |
|----------|-------------------|
| `high` | Transformational effect — fundamentally changes metrics or positioning |
| `medium` | Substantial improvement — noticeable but not revolutionary effect |
| `low` | Minor improvement — "nice to have," not critical |

**Tip:** if the BA can't tell high from medium, ask for an order of magnitude.
Savings of $5K vs. $5M are different magnitudes, even without an exact calculation.

---

## Confidence (confidence the benefit will be realized)

| Value | When to use |
|----------|-------------------|
| `high` | The benefit is confirmed by data, experts, or precedent |
| `medium` | Logically justified, but no direct evidence |
| `low` | An assumption based on intuition or analogy |

**Important:** low confidence isn't a reason to ignore the benefit.
It's a signal to the BA that more elicitation/research is needed.

---

## Structure of a single benefit (benefits_json)

```json
{
  "benefit_title": "Reduced request processing time",
  "benefit_type": "operational",
  "magnitude": "high",
  "confidence": "medium",
  "description": "Reducing from 8 to 2 hours will free up ~40% of department resources and allow processing 3x more requests without new hires",
  "linked_business_needs": ["BN-001"],
  "linked_goals": ["BG-001"]
}
```

Minimum required fields: `benefit_title`, `benefit_type`, `magnitude`, `confidence`.
The rest are recommended — they make the benefit well-supported.

---

## Investment level (investment_level)

A qualitative assessment of the scale of investment — without exact figures.

| Value | Guideline |
|----------|---------|
| `low` | Minor configuration changes, training, process adaptation without development |
| `medium` | Moderate development or procurement, team changes, 3–12 months |
| `high` | Transformational project, major development or implementation, 12+ months |
| `unknown` | Cannot be assessed yet — more information needed |

---

## How to read the value assessment during the completeness check

`check_future_state_completeness` checks whether a value assessment exists.
What's enough for a "green" status:
- At least one benefit in the benefits list
- `investment_level` is specified (even `unknown`)

The quality of the assessment is up to the BA. The tool doesn't block, it only informs.

---

## How 6.2 data is used in 7.6

`add_value_assessment` in 7.6, when `{project}_future_state.json` exists, reads the
`potential_value.benefits` section as pre-fill context. The BA sees already-structured benefits
and refines them quantitatively.

If there's no 6.2 data, 7.6 works as usual (graceful degradation).

---

## Common BA mistakes when assessing value

### "Marked everything as high / high"
Symptom: overconfidence. If everything has high magnitude and confidence,
the assessment is likely overly optimistic and unsupported.
Help the BA ask themselves: "What's this backed up by?"

### "No link between benefits and BNs"
If a benefit isn't linked to a business need from 6.1, it's unclear why it matters at all.
Either it's a "fantasy," or the BN set from 6.1 is incomplete.

### "Only financial benefits"
Organizations often forget operational and strategic benefits.
Ask: "What will change in how the team works?", "What new opportunities will open up?"

### "No value_summary"
A summary assessment is important for communicating with the sponsor:
"High potential value at a medium investment level — an attractive profile."
