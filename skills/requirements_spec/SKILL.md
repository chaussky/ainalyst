---
name: requirements_spec
description: >
  BABOK 7.1 skill — Specify and Model Requirements. Use this skill when the BA
  translates elicitation results into formal specifications: user stories,
  use cases, business rules, data definitions, process models (BPMN).
  Triggers: "requirements specification", "user story", "use case", "business rules",
  "specify requirements", "write requirements", "formalize requirements", "BPMN", "models".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL.md — BABOK 7.1: Specify and Model Requirements

## What this task is about

Task 7.1 turns confirmed elicitation results (4.2/4.3) into formal requirements
specifications. The input is "what the stakeholders said," the output is
"requirements in standard notations with models."

This is the bridge between elicitation (Chapter 4) and verification/validation (7.2, 7.3).

---

## When to call these tools

Call the 7.1 tools when:
- Confirmed elicitation results exist (artifacts from 4.3)
- Requirements need to be handed off to developers, architects, testers
- Traceable formal specifications are needed
- You need to verify that all business objectives from elicitation are covered by requirements

---

## Recommended workflow

### Step 1 — Context analysis
Start with `analyze_elicitation_context`. The tool will read the 4.3 artifacts
and propose a list of candidate requirements with classification.

```
analyze_elicitation_context(
    project_id="crm_2024",
    context_text=""   # leave empty — the tool will find the file itself
)
```

If the 4.3 file is not found, the tool will ask you to pass the text manually:
```
analyze_elicitation_context(
    project_id="crm_2024",
    context_text="[paste the contents of the 4.3 artifact here]"
)
```

### Step 2 — Creating artifacts
Create requirements one at a time or in groups, using the appropriate tool.
**Every artifact created is automatically registered in the 5.1 repository**
with status `draft`. You don't need to call the 5.1 tools manually.

**Link each requirement to the business objective it serves.** Every creating tool takes
`business_goal_ids_json` — the IDs of the 6.2 objectives (`["BG-001", "BG-002"]`). This
writes a `satisfies` link into the 5.1 graph, and it is what makes the coverage matrix in
Step 4 precise instead of a checklist. Ask the BA which objective the requirement serves;
never guess it from the wording. If the ID is unknown the tool warns and creates the
requirement anyway — you can link it later with `add_trace_link` (5.1).

Supporting models (data dictionary, ERD) are usually left unlinked — they describe the
solution rather than serve an objective directly.

How to choose the artifact type → see `references/modeling_guide.md`.
Templates for each artifact → see `references/templates.md`.

### Step 3 — Diagrams (as needed)
- After creating Use Cases → call `generate_use_case_diagram` for a consolidated diagram
- Business Process automatically creates a `.puml` Activity Diagram file
- ERD automatically creates a `.puml` file

### Step 4 — Coverage check
At the end, call `build_coverage_matrix`. It reads the business objectives from 6.2
(Define Future State: the `business_goal` nodes registered in the 5.1 graph, or
`future_state_goals.json`) and reports, per objective, which requirements serve it.

**Precise coverage requires two things:**
1. objectives defined in 6.2 `define_goals_and_objectives` — that is what puts them in the
   graph as `business_goal` nodes with IDs;
2. requirements linked to them — pass `business_goal_ids_json=["BG-001"]` when creating the
   requirement (see Step 2), or link later with `add_trace_link` (5.1).

Then the report shows:
- 🔴 an objective no requirement serves
- 🟢 normal coverage (1–9 requirements)
- 🟡 10+ requirements on one objective — possible over-engineering, check for duplicates
- requirements not linked to any objective, grouped by type

**If the objectives have no IDs** (they came from `future_state_goals.json`, a legacy
"Business objectives" section in the 4.3 artifact, or grouping by source), no per-objective
claim is made at all: the objectives are shown as a checklist and the report says so. The
tool never guesses which requirement serves which objective from their wording.

For full per-requirement traceability (sources, implementation, tests) run `check_coverage` (5.1).

---

## Tools

### `analyze_elicitation_context`
Analyzes confirmed elicitation results and proposes a list of requirements.

```
analyze_elicitation_context(
    project_id="crm_2024",       # required
    context_text=""              # optional: text if the file is not found
)
```

Returns:
- List of business objectives from 4.3
- Candidate requirements with a recommended type and ID prefix
- Gaps: elicitation topics without specific requirements

---

### `create_user_story`

```
create_user_story(
    project_id="crm_2024",
    story_id="US-001",
    title="Submit a credit application",
    role="Application Manager",
    action="create a new credit application filling in all the fields",
    benefit="the application is registered and forwarded for review",
    acceptance_criteria_json='["The system saves the application with a unique ID", "The system sends a confirmation to the manager email"]',
    priority="High",
    source_artifact="governance_plans/4_3_crm_confirmed.md",
    notes=""
)
```

---

### `create_functional_requirement`

```
create_functional_requirement(
    project_id="crm_2024",
    req_id="FR-001",
    req_type="functional",           # functional | non_functional | business_rule
    title="Automatic application routing",
    description="The system SHALL automatically distribute incoming applications among managers using a round-robin algorithm that accounts for current workload.",
    rationale="Reduces client wait time and eliminates manual oversight.",
    priority="High",
    owner="Head of Sales",
    source_artifact="governance_plans/4_3_crm_confirmed.md",
    constraints="",
    related_ids_json='["BR-001", "UC-001"]'
)
```

**Phrasing by type:**
- `functional`: "The system SHALL [action]..."
- `non_functional`: "The system SHALL handle at least [N] requests per second under [condition]"
- `business_rule`: "[Subject] [constraint/rule]" — without referencing the system

---

### `create_use_case`

```
create_use_case(
    project_id="crm_2024",
    uc_id="UC-001",
    title="Review a credit application",
    primary_actor="Credit Analyst",
    secondary_actors="Security Department, Scoring System",
    precondition="The application has status 'Under review'",
    postcondition="The application receives status 'Approved' or 'Rejected'",
    trigger="The analyst opens the application in the system",
    main_scenario="1. The analyst opens the application.\n2. The system displays the client data and documents.\n3. The analyst checks the credit score.\n4. The system requests a check from the Security Department.\n5. The analyst makes a decision.\n6. The system records the decision and changes the status.",
    alt_scenarios="3a. The credit score is unavailable: The analyst requests a recalculation.",
    exc_scenarios="4a. The Security Department does not respond within 24h: The system notifies the manager.",
    business_rules="The decision must be made within 3 business days.",
    priority="High",
    source_artifact="governance_plans/4_3_crm_confirmed.md"
)
```

---

### `generate_use_case_diagram`

Generates a consolidated PlantUML Use Case Diagram covering **all** UCs in the project from the 5.1 repository.

```
generate_use_case_diagram(
    project_id="crm_2024",
    system_boundary="CRM system",
    diagram_name="crm_use_cases"
)
```

Result: file `{project}_specs/uc_diagram_{diagram_name}.puml`

---

### `create_business_process`

Creates **two files**: a text description `.md` + an Activity Diagram `.puml`.

```
create_business_process(
    project_id="crm_2024",
    bp_id="BP-001",
    title="Application lifecycle",
    process_owner="Head of Sales",
    trigger="A client applies for credit",
    outcome="The credit is issued or the application is closed with a rejection",
    participants="Manager, Credit Analyst, Security Department",
    steps="1. Manager: receive the client's request.\n2. Manager: create the application in the CRM.\n3. System: assign an analyst.\n4. Analyst: verify documents.\n5. ...",
    business_rules="Review period — 3 business days.",
    metrics="Average time: 2 days. Approval conversion rate: 65%.",
    exceptions="If the client does not provide documents within 5 days — auto-closure.",
    priority="Medium",
    source_artifact="governance_plans/4_3_crm_confirmed.md"
)
```

---

### `create_data_dictionary`

```
create_data_dictionary(
    project_id="crm_2024",
    dd_id="DD-001",
    title="Application entity",
    entities_json='[{"name": "Application", "description": "Credit application", "attributes": [{"name": "id", "type": "Integer", "required": true, "constraints": "PK, AUTO_INCREMENT", "description": "Unique identifier"}, {"name": "status", "type": "Enum", "required": true, "constraints": "draft|submitted|approved|rejected", "description": "Application status"}], "business_rules": ["The status changes only according to the transition business rules"]}]',
    source_artifact="governance_plans/4_3_crm_confirmed.md"
)
```

---

### `create_erd`

Creates **two files**: a relationship description `.md` + an ER Diagram `.puml`.

```
create_erd(
    project_id="crm_2024",
    erd_id="ERD-001",
    title="Core CRM entities",
    entities_json='[{"name": "Application", "pk": "id", "attributes": ["client_id FK", "manager_id FK", "status Enum", "created_at DateTime"]}, {"name": "Client", "pk": "id", "attributes": ["name String", "inn String UNIQUE"]}]',
    relations_json='[{"from": "Application", "to": "Client", "cardinality": "many-to-one", "label": "belongs to"}]',
    source_artifact="governance_plans/4_3_crm_confirmed.md"
)
```

---

### `build_coverage_matrix`

Reports which requirements serve which business objective. Objectives come from the 6.2
`business_goal` nodes in the 5.1 graph (or `future_state_goals.json`); requirements come from
the 5.1 registry.

```
build_coverage_matrix(
    project_id="crm_2024"
)
```

**Signals (when the objectives are graph nodes):**
- 🔴 objective with no requirement serving it
- 🟢 1–9 requirements
- 🟡 10+ requirements on one objective — possible over-engineering, check for duplicates
- requirements not linked to any objective, grouped by type
- requirements traced to a business need but not to an objective — usually a need 6.2 has
  not refined into objectives yet

Coverage is computed by traversing the `satisfies` links the analyst declares (`derives`
links to an objective count too). **Nothing is inferred from wording** — an objective is
covered only when a requirement is actually linked to its node.

**Without objective IDs** (objectives from `future_state_goals.json`, a legacy "Business
objectives" section in the 4.3 artifact, or grouping by requirement source), no per-objective
claim is made: the objectives are listed as a checklist and the report states why.

Nodes other chapters keep in the same graph — `change_request` (5.4), `risk` (6.3),
`solution` (6.4), `test` (5.1) — are not counted as requirements here.

---

## Artifact storage

All artifacts are saved to: `governance_plans/{project_id}_specs/`

```
governance_plans/crm_2024_specs/
├── US-001_submit_application.md
├── FR-001_auto_distribution.md
├── UC-001_review_application.md
├── uc_diagram_crm_use_cases.puml       ← consolidated UC Diagram
├── BP-001_application_lifecycle.md
├── BP-001_application_lifecycle.puml   ← Activity Diagram
├── DD-001_application_entity.md
├── ERD-001_core_entities.md
└── ERD-001_core_entities.puml          ← ER Diagram
```

---

## Automatic registration in 5.1

Every created artifact is **automatically** registered in the 5.1 repository
(file `governance_plans/{project_id}_traceability_repo.json`) with status `draft`.

You can:
- Immediately add links via `add_trace_link` (5.1)
- Change the status via `update_requirement` (5.2) once the requirement is ready for verification
- Check coverage via `check_coverage` (5.1)

---

## Links to other tasks

| From | What we take |
|--------|-----------|
| 4.2/4.3 | Confirmed elicitation results (input for `analyze_elicitation_context`) |
| 5.1 | Traceability repository (7.1 writes to it automatically) |

| To | What we pass |
|------|--------------|
| 7.2 | Requirements specifications for verification |
| 7.3 | Requirements specifications for validation |
| 5.3 | List of draft requirements for prioritization |

---

## References

- `references/modeling_guide.md` — how to choose the artifact type
- `references/templates.md` — templates for each artifact and PlantUML diagrams
