# Reference Guide: Analyze Current State (BABOK 6.1)

## Purpose

Analyzing the current state is the starting point for the entire change project.
Goal: understand **why** change is needed and **what** exactly it will affect.

BABOK identifies two key outputs of task 6.1:
1. **Current state description** — a structured analysis of 8 elements
2. **Business needs** — formalized reasons for change (input for 6.2)

---

## 8 elements of current state analysis

### 1. Business needs (`business_needs`)

**What we describe:**
- Problems, opportunities, or external environment requirements that initiated the change
- Strategic importance — why this matters right now
- Cost of Inaction — what will happen if nothing changes

**Typical symptoms (which the BA confuses with needs):**
- "Customer complaints are increasing" — a symptom, not a need
- "There's no unified registry" — a symptom of a missing system
- "The process is slow" — a symptom, RCA is needed

**A correctly formulated need:**
- A clear, measurable problem or opportunity
- Tied to a business outcome
- Example: "Request processing time increased from 2 to 8 hours, customer churn +18% year over year"

**Questions for the BA:**
- What exactly isn't working, or what are we missing?
- What is the cost of the current situation in money/time?
- What changed in the external environment that made this critical?
- What's the deadline — when does this need to be resolved?

---

### 2. Organizational structure and culture (`org_structure`)

**What we describe:**
- The structure of the organization (departments, roles, hierarchy)
- Decision-making culture: centralized / decentralized
- Informal centers of influence (who actually makes decisions)
- Change Readiness

**What's important to capture:**
- Who benefits from the current state (they will resist change)
- Where "silos" exist (communication gaps between departments)
- Cultural patterns: "that's how it's always been done," resistance to tools

**Questions for the BA:**
- How are decisions made on our topic?
- Are there conflicts between departments on this topic?
- How do teams feel about change?

---

### 3. Capabilities and processes (`capabilities`)

**What we describe:**
- Key business processes (as-is) related to the area of change
- Organizational capabilities: what's done well, what isn't
- Capability Gaps: what the organization is unable to do

**Metrics to collect:**
- Process step execution time
- Number of errors / reworks
- Number of manual steps vs. automated steps
- Handoff points between departments

**Questions for the BA:**
- What does the process look like step by step (swim-lane)?
- Where do delays or errors occur?
- What's done manually that could be automated?
- Where is work duplicated?

---

### 4. Technology and infrastructure (`technology`)

**What we describe:**
- The current technology stack (systems, databases, integrations)
- State: up to date / legacy / end-of-life
- Integration map: how systems interact
- Technical debt, constraints, bottlenecks

**Metrics to collect:**
- System response time
- Incident frequency / downtime
- Support cost
- System age

**Questions for the BA:**
- Which systems are involved in the current process?
- Are there systems planned for replacement/decommissioning?
- Where do technical failures occur most often?
- Which integrations are unstable?

---

### 5. Policies (`policies`)

**What we describe:**
- Internal regulatory documents (procedures, processes, standards)
- External regulation (laws, industry standards, regulator requirements)
- Policies that constrain or define the current process

**A common mistake:** not accounting for outdated policies as a source of problems.
A process is often "broken" precisely because it was written for a 2012-era regulation.

**Questions for the BA:**
- What policies/procedures govern the current process?
- Are there regulatory requirements we must comply with?
- Are there policies that conflict with each other?
- Are the existing policies current, or are they outdated?

---

### 6. Business architecture (`architecture`)

**What we describe:**
- How all the elements (processes, systems, data, roles) are connected and work together
- Value Streams: how value is created from start to finish
- Operating model: how the organization carries out its mission

**This is the "how the system works as a whole" level**, not the details of each element.
Useful for understanding systemic effects: a change to one element affects everything.

**Questions for the BA:**
- How is the process connected to other processes in the organization?
- Where is value created for the customer in the current setup?
- Which dependencies between systems are critical?

---

### 7. Internal assets (`assets`)

**What we describe:**
- Financial assets (budgets, investments in current systems)
- Intellectual assets (knowledge, documentation, know-how)
- Physical assets (equipment, offices)
- Human capital (expertise, key personnel)

**Why this matters:** assets determine constraints and opportunities.
If a key expert leaves, the process breaks. If a system is fully depreciated,
there's grounds for replacement without additional justification.

**Questions for the BA:**
- Which assets are critical to the current process?
- Are there assets at risk (outdated, unreliable)?
- What's the real total cost of ownership of the current solution?

---

### 8. External influences (`external`)

**What we describe:**
- Competitors: what are they doing differently?
- Market trends: where is the industry headed?
- Regulatory changes: what's coming into effect?
- Technology trends: what's changing the rules of the game?
- Customer expectations: what's changed in customer behavior?

**PEST analysis as a structure:** Political / Economic / Social / Technological

**Questions for the BA:**
- What are competitors doing that we aren't?
- What regulatory changes are expected in the near term?
- How have customer expectations changed?

---

## Recommended element set by initiative type

| Initiative type | Mandatory | Additional |
|----------------|-------------|----------------|
| `process_improvement` | business_needs, capabilities, technology, policies | org_structure, architecture |
| `new_system` | business_needs, capabilities, technology, architecture | policies, assets |
| `regulatory` | business_needs, policies, technology, external | org_structure, capabilities |
| `cost_reduction` | business_needs, capabilities, assets, external | technology, policies |
| `market_opportunity` | All 8 elements | — |

---

## Depth of analysis

### `light` (3–4 elements)
- Focus on business needs and key processes
- Used for smaller initiatives with a clear scope
- Timeframe: 1–2 business days

### `standard` (5–6 elements)
- Adds technology and policies
- Most projects
- Timeframe: 3–5 business days

### `deep` (all 8 elements)
- A full cross-section of the organization
- Strategic change, market opportunities, compliance
- Timeframe: 1–2 weeks

---

## Data sources for each element

| Source | What it provides |
|----------|----------|
| `elicitation` | Results from 4.2/4.3 — structured data from interviews and sessions |
| `document` | Procedures, reports, analytics, BPM diagrams |
| `observation` | Observing the process on-site |
| `interview` | Targeted interviews (if not done via 4.2) |
| `other` | External sources: industry reports, regulator data |

---

## Relationship to other BABOK tasks

| Task | How it uses 6.1 results |
|--------|-------------------------------|
| **6.2** Define Future State | Current state is the foundation for identifying gaps (gap analysis) |
| **6.4** Assess Risks | Current state elements are a source of risks |
| **7.3** Validate Requirements | `set_business_context` is pre-filled from 6.1 (ADR-055) |
| **7.6** Recommend Solution | RCA and business needs influence the value assessment |
| **5.1** Trace Requirements | Business needs (BN-xxx) are upstream nodes of the traceability graph |
