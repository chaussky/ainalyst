# Design Options Guide — BABOK 7.5

Reference for the Define Design Options task.
Read by Claude Code on demand from SKILL.md.

---

## 1. Solution approaches: Build / Buy / Hybrid

### Build (develop from scratch)
**When it's chosen:**
- Unique business processes that are hard to automate with an off-the-shelf solution
- High integration requirements with existing systems
- Sensitive data / security requirements rule out SaaS
- Long-term strategy: a core competency of the company

**Pros:** full control, exact fit to requirements, no licensing risk
**Cons:** high development cost, long time-to-market, support resources required

**Typical components:** backend service, database, UI, integration layer

---

### Buy (purchase / off-the-shelf solution)
**When it's chosen:**
- Standard processes (ERP, CRM, HRM) — no point reinventing the wheel
- Limited development budget
- Need to launch quickly (time-to-market < 6 months)
- Vendor provides updates and support

**Pros:** fast start, proven solution, vendor support
**Cons:** vendor dependency, limited customization, licensing costs

**What to include in Vendor Notes:** vendor name, version, license cost, TCO, customization constraints, references

---

### Hybrid (combined)
**When it's chosen:**
- Part of the process is standard (Buy), part is unique (Build)
- Gradual migration: Buy as the platform, Build for extensions
- Integration of multiple systems

**Pros:** balance of speed-to-market and flexibility
**Cons:** integration complexity, two risk types at once

---

## 2. Improvement Opportunities (BABOK)

Under BABOK v3, task 7.5 explicitly requires describing improvement opportunities.
Three types per the standard:

### efficiency
Automating or simplifying work that a person currently does manually.
Examples:
- "Automatic report generation instead of manual Excel work"
- "Automatic document validation on upload"
- "Notifications instead of manual status monitoring"

### information_access
Improving access to information for decision-making.
Examples:
- "A single dashboard instead of data from 5 different systems"
- "Real-time order status instead of calling the call center"
- "Customer analytics built on historical data"

### new_capability
New capabilities that don't currently exist.
Examples:
- "A mobile app for field staff"
- "Integration with external suppliers via API"
- "Personalized recommendations based on ML"

---

## 3. Criteria for comparing design options

### Default criteria (used if the BA hasn't set custom ones)

| Criterion | Description | Weight (default) |
|----------|----------|--------------|
| cost | Implementation cost (CAPEX + OPEX over 3 years) | high |
| speed | Time-to-market (how quickly it can launch) | high |
| risk | Aggregate risk (technical + organizational) | medium |
| req_coverage | Percentage of Must-requirement coverage | high |
| flexibility | Ability to change after launch | medium |

### How to interpret the matrix
- **req_coverage** is calculated automatically: Must-requirements allocated to v1 / total Must-requirements
- The other criteria are a qualitative BA assessment (Low / Medium / High)
- When comparing: high-weight criteria take priority on a tie

### Custom criteria
The BA can pass `criteria_json` — a list of additional criteria:
```json
[
  {"id": "vendor_support", "label": "Vendor support", "weight": "medium"},
  {"id": "integration_complexity", "label": "Integration complexity", "weight": "high"}
]
```

---

## 4. Allocation — patterns for allocating requirements to releases

### Simple option (implemented in v1)
Releases: `v1` / `v2` / `out_of_scope`

**auto_suggest algorithm:**
- Must (MoSCoW) / High (WSJF) → `v1`
- Should / Medium → `v1` or `v2` (BA decides on confirmation)
- Could / Low → `v2`
- Won't → `out_of_scope`
- No priority → a warning is raised, the BA decides manually

**Depends-conflict check:**
After the allocation is confirmed, the tool checks the 5.1 graph.
If requirement A (v1) depends on requirement B (v2) via a `depends` link — that's a conflict.
The tool suggests moving B to v1. The decision belongs to the BA.

### v2 fork (planned)
Advanced allocation:
- Multiple components (not just v1/v2): "Component A", "Component B", "MVP"
- Components × releases matrix
- Allocation across teams
For v2: add `assignment_mode` and `components_json` to `allocate_requirements`.

---

## 5. Vendor Assessment (for Buy / Hybrid)

BABOK mentions this as a vendor assessment technique.
In v1 a minimal version is implemented: a `vendor_notes` field inside an option using the `buy` / `hybrid` approach.

**What's recommended for vendor_notes:**
- Vendor and product name
- Cost (license / SaaS subscription / 3-year TCO)
- Customization constraints
- References (who uses it in the industry)
- SLA and support terms
- Vendor lock-in risk

**v2 fork:** a separate `run_vendor_assessment` tool with a formalized assessment
against criteria (Financial stability, Product roadmap, Implementation support, Exit strategy).

---

## 6. Change Strategy — relationship to task 7.5

### What Change Strategy is (BABOK 6.4)
Defines the **strategic level** of the change:
- Change type: technology / process / organizational / hybrid
- Scope: what changes, what stays the same
- Constraints: budget, timeline, technology stacks
- Timeframes and phases

### How it affects Design Options
- **change_type = technology** → design options focus on architectural decisions
- **change_type = process** → emphasis on BP artifacts and Improvement Opportunities
- **change_type = organizational** → allocation accounts for organizational constraints
- **constraints** → automatically flow into the Design Options Report as constraints

---

## 7. Relationship to other BABOK tasks

| Input | Task | What we use |
|------|--------|----------------|
| 5.1 | Traceability | Graph of `depends` links to validate allocation |
| 5.3 | Prioritization | The `priority` field on requirements for auto_suggest |
| 7.3 | Business Context | Business objectives, Future State, constraints |
| 7.4 | Architecture | Viewpoints, gaps — context for the options |
| 6.4 | Change Strategy | Change type and constraints |

| Output | Task | What we pass along |
|-------|--------|--------------|
| 7.6 | Analyze Value | Design Options Report (all options + allocation) |
| 4.4 | Communicate | Comparison Document for stakeholders |
