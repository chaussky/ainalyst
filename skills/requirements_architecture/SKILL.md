---
name: requirements_architecture
description: >
  Skill for BABOK 7.4 — Define Requirements Architecture. Use this skill when
  the BA wants to build a coherent picture out of scattered requirements: define
  architecture layers, set up views (viewpoints), and link requirements to system components.
  Triggers: "requirements architecture", "requirements layers",
  "requirements structure", "views", "how to organize requirements".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL.md — BABOK 7.4 Define Requirements Architecture

## What this task is about

**Requirements architecture** answers the question: **"How do our requirements form a coherent picture?"**

Place in the chain:
- **7.1 Specify** → Create requirements (artifacts: BP, US, FR, BR, DD, ERD)
- **7.2 Verify** → Check the quality of the wording
- **7.3 Validate** → Check the business value
- **7.4 Architecture** → **Organize requirements into a connected structure** ← we are here
- **7.5 Design Options** → Define solution options

**Key concepts:**
- **Viewpoint** — the perspective from which a stakeholder looks at the system
- **View** — a subset of requirements for a specific viewpoint

Different stakeholders see the system differently: the business sponsor sees it through processes, the developer through functions,
the data architect through data models. 7.4 organizes requirements so each stakeholder sees "their own" part.

---

## Automatic mapping by artifact type

The platform automatically distributes requirements across viewpoints:

| Artifact type | Viewpoint |
|---------------|-----------|
| `business_process` (BP) | Business Processes |
| `data_dictionary` (DD), `erd` (ERD) | Data and Information |
| `user_story` (US), `use_case` (UC) | Users and Interaction |
| `functional` (FR), `non_functional` (NFR) | Functionality |
| `business_rule` (BR) | Business Rules |
| `business` (BG nodes) | Not included in viewpoints |

---

## Pipeline (steps in order)

```
1. analyze_requirements_architecture  ← automatically builds viewpoints from the 5.1 repository
2. add_custom_viewpoint               ← [optional] add a project-specific viewpoint
3. declare_stakeholder_interest       ← state whose interests each requirement touches
4. check_architecture_gaps            ← find gaps: coverage matrix + semantics
5. save_architecture_snapshot         ← lock in the architecture → hand off to 4.4 and 7.5
```

---

## MCP tools

### 1. `analyze_requirements_architecture`

**When:** at the start of work on the architecture — builds the full picture from the repository.

```
analyze_requirements_architecture(project_id = "crm_upgrade")
```

**What it does:**
- Reads all requirements from the 5.1 repository (`{project}_traceability_repo.json`)
- Distributes them across viewpoints according to VIEWPOINT_MAP (ADR-034)
- Builds a coverage matrix: BG × viewpoints
- Shows custom viewpoints if already added
- Takes into account business_context from 7.3 (BG list)

**What it returns:**
- Summary table: viewpoint → requirement count → list of IDs
- Coverage matrix: which BGs are covered by which viewpoints
- Custom viewpoints (if any)
- A hint on which gaps are worth checking

---

### 2. `add_custom_viewpoint`

**When:** the project needs an additional viewpoint (regulatory requirements, security, migration).

```
add_custom_viewpoint(
  project_id = "crm_upgrade",
  viewpoint_id = "security",
  label = "Security and Access",
  description = "Requirements for authentication, authorization, data encryption",
  req_ids_json = '["NFR-003", "NFR-007", "FR-015", "BR-002"]',
  stakeholder_roles = "Security architect, CISO"
)
```

**Important (ADR-036):** custom viewpoints are defined via `req_ids`, not via types.
"Security" is a cross-cutting slice over FR/NFR/BR — only the BA knows exactly which requirements belong to it.

**Validation:** the tool checks that all passed req_ids exist in the 5.1 repository.

---

### 3. `declare_stakeholder_interest`

**When:** once you know which requirements touch which people — usually right after
`analyze_requirements_architecture`, and again whenever elicitation turns up someone new.

```
declare_stakeholder_interest(
  project_id    = "crm_upgrade",
  stakeholder   = "Ivan Petrov",              # a NAME or a ROLE — both resolve
  req_ids_json  = '["FR-001", "FR-002"]',
  note          = "owns the revenue report these feed"
)
```

**This is the one stakeholder relation you state by hand.** It is deliberately not the
same as two facts the platform already holds:

| Relation | Who writes it | What it means |
|----------|---------------|---------------|
| declared interest | **7.4 — you, with this tool** | this requirement touches their interests |
| `owner` | 7.1 | who is answerable for the WORDING of the requirement |
| RACI | 5.5 | their role in a DECISION on an approval package |

**You do not re-enter the last two.** `check_architecture_gaps` and the Architecture
Document read them directly and say where each tie came from, so a person who owns a
requirement or voted on it in 5.5 already counts as covered.

⚠️ **Ownership is computed on the fly, so handing it over can silently uncover
somebody.** Because 7.4 reads `owner` at check time instead of storing a copy (nothing
here can go stale), a single `update_requirement(new_owner = ...)` in 5.2 can turn the
previous owner into a **new critical gap**: their one recorded tie was the owner field,
and it now points at somebody else. 5.2 warns when it happens. If the previous owner's
interests are still touched, record that here with `declare_stakeholder_interest` — a
declared interest is the one tie the platform keeps.

**Repeat calls MERGE** — a second call never erases what an earlier one recorded. To
withdraw a declaration, call again with `remove = True`. The reply always prints counts
("declared on 2 requirement(s)", "already declared on 1"), so a no-op is visible.

**A stakeholder the registry does not know is still recorded, with a warning** — the
registry is a living document and you may be entering someone you met an hour ago. An
unknown *requirement ID*, by contrast, is refused outright: that vocabulary is the
project's own graph, and a typo there is cheapest to fix at the call.

**A TYPE is refused, a STATUS is not.** The 5.1 graph also holds risks (6.3), business
goals (6.2), change requests (5.4), the 6.4 solution scope and test cases. Those are
**not requirements**, so declaring an interest in one is refused by name — the tool
would otherwise report "declared on 1 requirement(s)" about a risk, count it as
coverage, and print its id in a document whose header says the project has no such
requirement. An **archived** requirement (deprecated / superseded / retired) is a
different matter: it is still a requirement, so the declaration is recorded, with a
warning that the coverage check will not count it as live representation.

**The `note` reaches the reader.** Whatever you write there is printed under the
requirement it belongs to in the Architecture Document — it is the one place a sponsor
can see *why* the interests are touched, in your own words.

---

### 4. `check_architecture_gaps`

**When:** after `analyze_requirements_architecture` — to find weak spots.

```
check_architecture_gaps(project_id = "crm_upgrade")
```

**Two levels of checking (ADR-038):**

**Level 1 — Coverage matrix:**
- Stakeholder with no recorded tie to any requirement → `critical`
- Stakeholder reachable only by a word shared with a requirement title → `warning`
- Stakeholder whose every recorded tie points at an **archived** requirement
  (deprecated / superseded / retired in 5.2) → `warning`
- Archived requirements leave level 2 entirely: nobody is advised to write a use case
  for a retired requirement, and a live UC whose only BP was deprecated is reported as
  hanging rather than as covered. In the Architecture Document they stay in the
  viewpoint tables, tagged `_(archived)_`, and `Total req` still counts them.
- BG with no viewpoint coverage → `warning`
- Empty viewpoint → `info`
- Registry read but holding nobody identifiable → `info` (nobody was checked, and
  the report says so rather than reporting a clean sheet)

**Level 2 — Semantic gaps (uses the 5.1 graph):**
- UC with no corresponding BP → `warning`
- NFR not linked to an FR → `warning`
- FR with no UC/US → `info`

**How the stakeholder verdict is reached (ADR-098).** Three sources count as evidence:
a declared interest (7.4), being a requirement's `owner` (7.1), and an approval decision
on that requirement (5.5). A shared word with a requirement title is a fourth source,
kept because it is how this check used to work — but it is a coincidence, not a fact, so
it now yields a warning that names its own weakness instead of a critical verdict.

⚠️ **Interpretation:** level 2 depends on how complete the links in 5.1 are.
If the BA hasn't added traceability via 5.1, there will be many false positives. Keep this in mind.

---

### 5. `save_architecture_snapshot`

**When:** the architecture is ready — before handing it off to 4.4 (communication) and 7.5 (design).

```
save_architecture_snapshot(
  project_id = "crm_upgrade",
  version = "v1.0",
  notes = "First version of the requirements architecture. 5 viewpoints covered, 2 critical gaps resolved.",
  author = "A. Ivanov"
)
```

**What it creates:**
- A snapshot in `{project}_architecture.json` (history is not overwritten, ADR-037)
- A Markdown document via `save_artifact` → handed off to 4.4 and 7.5

**The gap block is recomputed at save time, not read back.** The workflow below puts
`declare_stakeholder_interest` between the gap check and the snapshot on purpose, so a
stored block would report gaps you had just resolved — right underneath a concerns
section, computed live, saying the opposite about the same person. That also means a
project which never calls `check_architecture_gaps` still gets a real gap table rather
than a row of zeros.

---

## Typical workflow

### Getting started
1. Make sure 7.1 has created artifacts of various types (BP, US, FR, etc.)
2. Call `analyze_requirements_architecture` — get the full picture

### If the project is standard
3. `declare_stakeholder_interest` — record whose interests each requirement touches
4. `check_architecture_gaps` — find gaps
5. Resolve critical gaps: declare the interests you know (7.4), create missing requirements (7.1), or add traceability (5.1)
6. `save_architecture_snapshot(version="v1.0")` — lock it in

### If the project is regulated (banking, healthcare, government)
3. `add_custom_viewpoint` — add viewpoints "Security", "Audit and Compliance"
4. `declare_stakeholder_interest` — regulators and compliance officers rarely own or approve individual requirements, so their interest usually has to be stated explicitly
5. `check_architecture_gaps` — check, accounting for custom viewpoints
6. `save_architecture_snapshot` — lock it in

### Agile project (iterative work)
- Call `analyze_requirements_architecture` at the end of each sprint
- Declare interests for the requirements the sprint added — the declaration merges, so this is safe to repeat
- Take a snapshot after each significant increment of requirements
- Hand off the Architecture Document to the next sprint's planning

---

## Files created by task 7.4

| File | Contains |
|------|----------|
| `{project}_architecture.json` | Viewpoints, views, gaps, snapshot history |
| `{project}_traceability_repo.json` | The `stakeholders` field on requirement nodes — declared interests only (7.4 writes this one field; everything else in the file belongs to chapter 5) |
| `7_4_architecture_*.md` | Architecture Document → 4.4, 7.5 |

---

## Links to other tasks

| From | What comes in |
|------|----------------|
| 5.1 | Requirements repository — basis for viewpoint mapping and BFS gap analysis |
| 4.2 | Stakeholder registry — coverage check; the name↔role bridge for declared interests |
| 5.5 | Approval decisions — a vote on a requirement is evidence that it touches the voter |
| 7.1 | Artifact types — automatic mapping to viewpoints; the `owner` field — evidence of interest |
| 7.3 | business_context (BG) — coverage matrix |

| To | What we hand off |
|------|-------------------|
| 4.4 | Architecture Document — artifact for stakeholder communication |
| 7.5 | Architecture Document — input artifact for Design Options |

---

## Detailed methodology

- Viewpoints, type mapping, gaps, frameworks, problem patterns →
  `references/architecture_guide.md`
