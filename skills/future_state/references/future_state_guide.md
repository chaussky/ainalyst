# Reference Guide: Define Future State (BABOK 6.2)

## The eight future state elements

The same 8 domains as in 6.1 — but now we describe "how it should be."
The BA's job isn't to invent the future, but to structure the stakeholders' vision.

| Element | Key | What we describe in the future state |
|---------|------|-----------------------------------|
| Business needs | `business_needs` | How needs will be satisfied, what outcome is achieved |
| Organizational structure | `org_structure` | Roles, responsibilities, culture after the change |
| Capabilities and processes | `capabilities` | New/improved processes, competencies that don't yet exist |
| Technology | `technology` | Target technology architecture, systems, tools |
| Policies | `policies` | New policies, regulations, rules |
| Business architecture | `architecture` | Target organizational model, business domains |
| Internal assets | `assets` | Data, knowledge, IP in the target state |
| External factors | `external` | Market position, relationships with partners, regulators |

---

## Questions for the BA on each element

### business_needs
- How will the business needs from 6.1 be satisfied?
- What concrete outcome will the organization achieve?
- How will the customer / employee experience change?
- What KPIs will be achieved?

### org_structure
- How will roles and responsibilities change?
- Will new positions / teams appear?
- How will the decision-making culture change?
- Who will own the new process?

### capabilities
- What new capabilities will appear?
- How will the key processes change?
- What competencies need to be developed / hired?
- What will the process look like in detail (as-should-be)?

### technology
- What systems / tools will appear?
- What will be replaced, what will be expanded?
- How will the integration landscape change?
- What level of automation will we achieve?

### policies
- What new regulations are needed?
- What will require approval / sign-off?
- How will the rules for employees change?

### architecture
- How will the business model / operating model change?
- Which business domains will be affected?
- How will system / team boundaries change?

### assets
- What data will we own?
- How will knowledge bases and documentation change?
- What IP is being created?

### external
- How will the market position change?
- What will change in relationships with partners / customers?
- How do we respond to regulatory requirements?

---

## SMART criteria for objectives and KPIs

Every business objective must meet SMART criteria:

| Criterion | What we check | Bad | Good |
|----------|--------------|-------|--------|
| **S**pecific | Is it clearly formulated? | "Improve the process" | "Reduce request approval time" |
| **M**easurable | Is there a metric? | "Get faster" | "Reduce from 8 to 2 hours" |
| **A**chievable | Realistic given current constraints? | "Eliminate all errors" | "Reduce errors from 12% to 2%" |
| **R**elevant | Linked to business needs? | An objective with no BN | An objective addresses BN-001, BN-002 |
| **T**ime-bound | Is there a deadline? | "As soon as possible" | "By Q4 2025" |

### How to help the BA make an objective SMART

If the BA says "we want to get better":
1. Ask "Better by what measure?" → Measurable
2. Ask "What's the current state? What do we want?" → specific numbers
3. Ask "By what date?" → Time-bound
4. Check "Does this address BN-xxx from 6.1?" → Relevant

### Structure of an objective (target metric)

```json
{
  "title": "Reduce request processing time",
  "metric": "Processing time per request (hours)",
  "baseline": "8 hours (Q1 2025)",
  "target": "2 hours",
  "deadline": "2025-12-31"
}
```

---

## Gap analysis: from current to future

The gap analysis is an explicit comparison for each element: "where we are now" vs. "where we're going."
The gap analysis result is a direct input for 6.4 (Define Change Strategy).

### Change types

| Type | Meaning | Example |
|-----|-------|--------|
| `new` | Building from scratch | No CRM → implementing a CRM |
| `improve` | Improving something that exists | Manual process → automating part of it |
| `eliminate` | Removing | Redundant approval levels → eliminating them |
| `replace` | Replacing one thing with another | Old system → new system |

### Change complexity assessment

| Complexity | Indicators |
|-----------|---------|
| `low` | Change within a single domain, no dependencies, well-understood technology |
| `medium` | 2–3 domains, has dependencies, requires training or new resources |
| `high` | Multiple domains, cultural change, uncertainty, external dependencies |

### Structure of a per-element gap analysis entry

```json
{
  "element": "capabilities",
  "current_description": "Manual approval process, 8 hours, 3 levels",
  "future_description": "Automated process, 2 hours, 1 level",
  "gap_summary": "Need to automate approval and reduce the number of levels",
  "change_type": "improve",
  "complexity": "medium"
}
```

---

## Constraints — types and impact

Constraints narrow the solution space. They need to be captured explicitly so that
7.5 doesn't end up developing design options that are clearly infeasible.

### Constraint types

| Category | What belongs here | Example |
|-----------|----------------|--------|
| `budget` | Financial limits | "Project budget — up to $500K" |
| `time` | Time frames, deadlines | "Mandatory launch by April 1, 2026" |
| `technology` | Technology standards, prohibited platforms | "On-premise only, no cloud" |
| `policy` | Internal policies, rules | "Data cannot be outsourced" |
| `resources` | Team, competencies, throughput | "No dedicated development team" |
| `compliance` | Regulatory and legal requirements | "GDPR, local data protection law" |
| `other` | Other constraints | "Stakeholder X opposes any changes" |

### Constraint status

- `confirmed` — confirmed in documentation or by an authorized person
- `assumed` — the BA assumes the constraint exists but hasn't verified it

Assumed constraints need to be validated — they may turn out to be myths.

---

## UX pattern: "past alongside future"

When filling in future state elements — if data from 6.1 exists,
show the BA the current state alongside it. This helps:
- Avoid describing what already exists (FS ≠ CS)
- See the gap between the states explicitly
- Formulate the gap analysis more precisely

---

## Linking FS elements to business needs

Each FS element should be traced to one or more BNs from 6.1.
If an element isn't linked to any BN, that's a sign of "scope creep":
the organization is describing a desired future that doesn't address real pain points.

The `linked_business_needs` parameter when calling `capture_future_state_element`:
```
'["BN-001", "BN-002"]'
```

If there are no BNs yet (6.1 wasn't conducted), the parameter can be left empty.
But it's better to create at least a minimal set of BNs before starting 6.2.
