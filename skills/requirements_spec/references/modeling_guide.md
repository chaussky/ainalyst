# Notation Selection Guide — BABOK 7.1

This file helps the BA choose the right artifact type for a specific task.
Used by SKILL.md as a reference during context analysis.

---

## Quick pick: what to use?

| Situation | Artifact | Tool |
|----------|----------|------------|
| Stakeholder says "I want the system to..." | User Story | `create_user_story` |
| A formal specification is needed for a developer | Functional Requirement | `create_functional_requirement` |
| There are non-functional requirements (SLA, speed, reliability) | Functional Requirement (type: non_functional) | `create_functional_requirement` |
| Stakeholder describes a business rule or constraint | Functional Requirement (type: business_rule) | `create_functional_requirement` |
| Need to describe user interaction with the system | Use Case | `create_use_case` |
| Need a diagram of all interactions on one page | Use Case Diagram | `generate_use_case_diagram` |
| Stakeholder describes how a process works "now" or "should work" | Business Process | `create_business_process` |
| Need to understand what data, which fields, which constraints | Data Dictionary | `create_data_dictionary` |
| Need to show relationships between entities | ERD | `create_erd` |
| Need to confirm all business objectives are covered | Coverage Matrix | `build_coverage_matrix` |

---

## Detailed selection criteria

### User Story vs Functional Requirement

**User Story** — when:
- The project follows Agile (Scrum, Kanban)
- The requirement describes user interaction with the system
- Value to the end user matters
- The artifact is planned to be added to the Product Backlog
- Format: "As a / I want / So that"

**Functional Requirement** — when:
- The project follows Predictive (Waterfall, RUP)
- The requirement describes system behavior without tying it to a specific persona
- A traceable identifier (FR-001) with attributes is needed
- The artifact will be part of an SRS document
- Format: "The system SHALL..."

**Both fit** Hybrid projects. Choose whichever the development team is more comfortable with.

---

### Use Case vs User Story vs Business Process

**Use Case** — when you need to:
- Describe a full interaction scenario (including alternatives and exceptions)
- Formalize the contract between the system and an external actor
- Combine several User Stories into one scenario
- Show how the system responds to different events from one actor

**User Story** — when you need to:
- Quickly capture a user need
- Hand it off to a sprint with clear acceptance criteria
- No alternative scenarios are needed (simple linear flow)

**Business Process** — when you need to:
- Describe a process with multiple participants (not just the system)
- Show a sequence of "as-is" or "to-be" steps
- The process includes manual steps, waits, handoffs between departments
- A basis for building a BPMN diagram in draw.io/Camunda is needed

---

### Data Dictionary vs ERD

**Data Dictionary** — when you need to:
- Understand the data structure of a specific entity
- Capture types, constraints, business rules for attributes
- Make sure the team understands the domain the same way
- There's no clear understanding yet of relationships between entities

**ERD** — when you need to:
- Show relationships between several entities
- Discuss the database schema with an architect/developer
- Capture relationship cardinality (one-to-many, many-to-many)
- A basis for physical database design is needed

**Usually both are needed**: the Data Dictionary describes attributes, the ERD describes relationships.
The BA creates the DD first (understands the structure), then the ERD (understands the relationships).

---

## Common notation-selection mistakes

### ❌ Wrong: Business Rule as a standalone document
Business rules should not exist in a vacuum. They are ALWAYS tied to:
- a specific Use Case (the rule applies at a scenario step), or
- a specific Functional Requirement (the rule constrains behavior).
Use `create_functional_requirement` with type `business_rule`, then link it in 5.1.

### ❌ Wrong: a Use Case for every button
A Use Case describes a user goal, not a UI element.
"Click the Save button" is not a UC. "Save a draft application" is a UC.
Rule of thumb: if the UC cannot be phrased as a verb+noun ("Submit application"), it's not a UC.

### ❌ Wrong: User Story without Acceptance Criteria
A User Story without AC is not a requirement, it's a wish. 2–5 criteria are mandatory.
AC template: "[When] [condition] → [System/User] [action]"

### ❌ Wrong: ERD as the only data artifact
An ERD shows structure but not semantics. Always supplement it with a Data Dictionary
that describes the business meaning of each attribute.

---

## Coverage strategies by project type

### Agile project (Scrum)
Priority: User Stories → Use Cases for complex flows → Data Dictionary
ERD — only if the team is building from scratch. Business Process — for AS-IS analysis.

### Predictive project (Waterfall)
Priority: Functional Requirements → Use Cases → Business Processes → ERD + Data Dictionary
User Stories — optional, but useful for the UI part.

### Hybrid project
Functional Requirements for the system backbone + User Stories for user-facing features.
Use Cases for integrations. Business Process for describing changed business processes.

---

## How PlantUML fits into the workflow

The `.puml` files are saved alongside the `.md` artifact:
```
governance_plans/crm_specs/
├── UC-001_approve_request.md
├── UC-001_approve_request.puml       ← diagram for an individual UC (if needed)
├── uc_diagram_crm.puml               ← consolidated UC Diagram for the whole project
├── BP-001_request_lifecycle.md
├── BP-001_request_lifecycle.puml     ← process Activity Diagram
├── ERD-001_core_entities.md
└── ERD-001_core_entities.puml        ← ER Diagram
```

**How to render `.puml`:**
1. **PlantUML Online**: https://www.plantuml.com/plantuml/uml/
2. **VS Code**: the "PlantUML" extension (jebbs.plantuml)
3. **Confluence**: the PlantUML for Confluence plugin
4. **IntelliJ IDEA**: built-in PlantUML support

**Local PlantUML install:**
```bash
brew install plantuml          # macOS
sudo apt install plantuml      # Ubuntu/Debian
```
Render to PNG: `plantuml file.puml`
