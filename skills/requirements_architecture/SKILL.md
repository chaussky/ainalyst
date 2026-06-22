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
3. check_architecture_gaps            ← find gaps: coverage matrix + semantics
4. save_architecture_snapshot         ← lock in the architecture → hand off to 4.4 and 7.5
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

### 3. `check_architecture_gaps`

**When:** after `analyze_requirements_architecture` — to find weak spots.

```
check_architecture_gaps(project_id = "crm_upgrade")
```

**Two levels of checking (ADR-038):**

**Level 1 — Coverage matrix:**
- Stakeholder with no view → `critical`
- BG with no viewpoint coverage → `warning`
- Empty viewpoint → `info`

**Level 2 — Semantic gaps (uses the 5.1 graph):**
- UC with no corresponding BP → `warning`
- NFR not linked to an FR → `warning`
- FR with no UC/US → `info`
- Stakeholder in the registry with zero requirements → `critical`

⚠️ **Interpretation:** level 2 depends on how complete the links in 5.1 are.
If the BA hasn't added traceability via 5.1, there will be many false positives. Keep this in mind.

---

### 4. `save_architecture_snapshot`

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

---

## Typical workflow

### Getting started
1. Make sure 7.1 has created artifacts of various types (BP, US, FR, etc.)
2. Call `analyze_requirements_architecture` — get the full picture

### If the project is standard
3. `check_architecture_gaps` — find gaps
4. Resolve critical gaps: create missing requirements (7.1) or add traceability (5.1)
5. `save_architecture_snapshot(version="v1.0")` — lock it in

### If the project is regulated (banking, healthcare, government)
3. `add_custom_viewpoint` — add viewpoints "Security", "Audit and Compliance"
4. `check_architecture_gaps` — check, accounting for custom viewpoints
5. `save_architecture_snapshot` — lock it in

### Agile project (iterative work)
- Call `analyze_requirements_architecture` at the end of each sprint
- Take a snapshot after each significant increment of requirements
- Hand off the Architecture Document to the next sprint's planning

---

## Files created by task 7.4

| File | Contains |
|------|----------|
| `{project}_architecture.json` | Viewpoints, views, gaps, snapshot history |
| `7_4_architecture_*.md` | Architecture Document → 4.4, 7.5 |

---

## Links to other tasks

| From | What comes in |
|------|----------------|
| 5.1 | Requirements repository — basis for viewpoint mapping and BFS gap analysis |
| 4.2 | Stakeholder registry — coverage check |
| 7.1 | Artifact types — automatic mapping to viewpoints |
| 7.3 | business_context (BG) — coverage matrix |

| To | What we hand off |
|------|-------------------|
| 4.4 | Architecture Document — artifact for stakeholder communication |
| 7.5 | Architecture Document — input artifact for Design Options |

---

## Detailed methodology

- Viewpoints, type mapping, gaps, frameworks, problem patterns →
  `references/architecture_guide.md`
