# architecture_guide.md — Requirements Architecture (BABOK 7.4)

## What requirements architecture is

**Requirements architecture** is the organization of requirements into a connected structure, where each
requirement has its place and it's clear how it relates to the others.

It's the answer to the question: **"How do our requirements form a coherent picture?"**

BABOK defines two key concepts:

| Concept | Definition | Example |
|---------|------------|---------|
| **Viewpoint** | The perspective from which a stakeholder looks at the system | "Business Processes", "Data", "Users" |
| **View** | A specific subset of requirements for a given viewpoint | All BP artifacts, all FR artifacts |

**Key principle:** different stakeholders have different interests. A CFO looks at the
system through the lens of business processes and objectives, a developer through functionality,
a data architect through information objects. Requirements architecture ensures that
each stakeholder sees "their" part of the picture, while the BA sees the whole.

---

## Five viewpoints (automatic mapping)

The platform automatically organizes requirements into five standard viewpoints based on the
artifact type (ADR-034):

### 1. Business Processes
**Artifacts:** `business_process` (BP)
**Audience:** Business sponsor, process owners
**Question:** How will business processes change?
**Signs of completeness:** Every key business process is described. No Use Case lacks a corresponding BP.

### 2. Data and Information
**Artifacts:** `data_dictionary` (DD), `erd` (ERD)
**Audience:** Data architect, DBA
**Question:** What data is created, stored, transmitted?
**Signs of completeness:** All entities from the ERD are described in the DD. No entities with undefined attributes.

### 3. Users and Interaction
**Artifacts:** `user_story` (US), `use_case` (UC)
**Audience:** UX designer, developer, tester
**Question:** How do users interact with the system?
**Signs of completeness:** All user types are represented. Every US / UC traces to an FR.

### 4. Functionality
**Artifacts:** `functional` (FR), `non_functional` (NFR)
**Audience:** Developer, architect
**Question:** What must the system do, and how?
**Signs of completeness:** Every FR traces to a US or UC. Every NFR is linked to an FR.

### 5. Business Rules
**Artifacts:** `business_rule` (BR)
**Audience:** Business analyst, legal counsel, compliance officer
**Question:** What rules and constraints govern the system's behavior?
**Signs of completeness:** Business rules reference specific FRs or BPs.

---

## Custom viewpoints

The standard five viewpoints cover most projects. However, regulatory,
financial, and healthcare projects may require additional ones:

**Examples of custom viewpoints:**
- **Security and Access** — requirements for authentication, authorization, encryption
- **Audit and Compliance** — requirements for logging, SOX, GDPR, local data-protection law
- **Integrations** — requirements for APIs, integration scenarios
- **Data Migration** — requirements for migrating historical data

**Key distinction (ADR-036):** custom viewpoints are defined via specific req_ids,
not via artifact types. This is because "Security" is not a separate requirement type,
but a cross-cutting slice over existing FR/NFR/BR. Only the BA knows exactly which requirements relate to security.

---

## Architecture gaps

`check_architecture_gaps` checks the architecture at two levels:

### Level 1: Coverage matrix

**What's checked:**
- Is there a stakeholder from the 4.2 registry with no view at all?
- Is there a business objective from business_context (7.3) not covered by any viewpoint?
- Is there an empty viewpoint (a viewpoint with no requirements)?

| Problem | Severity | What to do |
|---------|----------|-----------|
| Stakeholder with no view | critical | Add requirements to the appropriate viewpoint |
| BG with no viewpoint coverage | warning | Check traceability in 5.1 or create the missing requirements |
| Empty viewpoint | info | Create artifacts of that type or remove the viewpoint |

### Level 2: Semantic gaps

Checks that go beyond the matrix — based on the links in the 5.1 repository:

| Gap | Severity | Explanation |
|-----|----------|--------------|
| UC with no BP | warning | A user interacts, but the business process isn't described |
| NFR with no FR | warning | A non-functional constraint is left "hanging" with no link to a function |
| FR with no UC or US | info | A function is described, but the usage scenario isn't documented |
| Stakeholder in the registry with no view | critical | The stakeholder is identified, but their interests aren't covered by any requirement |

**⚠️ Important about level 2:** semantic gap checks depend on how complete the 5.1 graph is.
If the BA has added few links in traceability, there will be many false positives (an FR with no UC, not
because the UC wasn't written, but because the link wasn't added). Interpret the results
with this context in mind.

---

## Requirements architecture frameworks

BABOK describes several conceptual frameworks. The platform uses a simplified
approach: automatic mapping + custom viewpoints. For reference — the main frameworks:

### Business Analysis Core Concept Model (BACCM)
Six interconnected concepts: Change, Need, Solution, Context, Stakeholder, Value.
Used as a philosophical foundation, not as an operational tool.

### Zachman Framework (simplified)
A matrix of "who, what, where, when, why, how" × "context, concept, logic, physics".
Useful for Enterprise Architecture, excessive for a typical IT project.

### Agile: Story Map
Horizontal axis — user activities (epics),
vertical axis — level of detail (US). Works well in Scrum/Kanban.

**In practice:** for most projects, the platform's five standard viewpoints
are enough. Frameworks are needed when working in a large enterprise context.

---

## Architecture snapshots

By analogy with the baseline in 5.5, task 7.4 supports snapshots (ADR-037):

**When to take a snapshot:**
- Before handing the architecture off to 7.5 (Design Options)
- After a substantial scope change (Change Request)
- At the end of each iteration in Agile projects

**What a snapshot captures:**
- The set of viewpoints (automatic + custom)
- Views — which requirements belong to each viewpoint
- Open gaps at the time of the snapshot
- Version (v1.0, v1.1) and notes

---

## Links to other tasks

| Task | Role in 7.4 |
|------|-------------|
| **5.1** (Traceability) | Link graph — basis for level-2 BFS gap analysis |
| **4.2** (Conduct Elicitation) | Stakeholder registry — coverage check at level 1 |
| **7.1** (Specification) | Artifact repository — source for automatic viewpoint mapping |
| **7.3** (Validate) | business_context — BG for the coverage matrix |
| **4.4** (Communicate) | Architecture Document is handed off as a communication artifact |
| **7.5** (Design Options) | Architecture Document — input artifact for solution design |

---

## Patterns of common architecture problems

### "Islands of requirements"
Several isolated clusters of requirements with no links between them. Sign: the 5.1 graph is disconnected.
What to do: check links via `run_impact_analysis` (5.1), add traceability.

### "Skewed toward functionality"
Lots of FR/NFR, little BP/US/UC. The developer sees what to do, but the business doesn't see the context.
What to do: create BP and US/UC for key functions.

### "Data without processes"
ERD + DD are well described, but there's no BP describing how the data is created and used.
What to do: create BP for key data flows.

### "Orphaned NFRs"
NFRs aren't linked to specific FRs. "The system must work fast" — relative to what exactly?
What to do: for each NFR, add a `satisfies` link to specific FRs in 5.1.
