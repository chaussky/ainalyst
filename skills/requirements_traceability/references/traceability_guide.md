# Reference Guide: Requirements Traceability (BABOK 5.1)

## Four relationship types — and when to use them

| Type | Direction | Meaning | Example |
|-----|-------------|-------|--------|
| `derives` | top-down | B follows from A (hierarchy) | BR-001 → SR-003 → FR-007 |
| `depends` | horizontal | B doesn't make sense without A | FR-007 depends on FR-005 (authorization) |
| `satisfies` | requirement → component | A component/module implements the requirement | FR-007 ← COMP-API-Auth |
| `verifies` | requirement → test | A test verifies that the requirement is met | FR-007 ← TC-042 |

**Common mistake:** tagging everything as "related" without a type. The link type is critical for impact analysis:
- When FR-007 changes due to a CR → a `depends` link will show FR-005 is also at risk
- A `verifies` link will show which tests need to be rerun
- A `satisfies` link will show which components are affected

---

## Formality presets

### Lite — Agile, small projects
We trace only:
- `derives`: business need → solution requirement
- Versioning: major changes only

Not traced: `depends`, `satisfies`, `verifies`

When to choose: Agile projects under 6 months, no regulatory requirements, team < 10 people.

### Standard — Most projects
We trace:
- `derives`: full vertical chain
- `verifies`: requirement → test
- Versioning: all changes with status

Not traced: `depends`, `satisfies` (optional)

When to choose: enterprise projects, Agile at scale, an established QA process.

### Full — Regulated domains, enterprise
We trace all 4 relationship types.
`rationale` is mandatory for every link.
Versioning: full change history.

When to choose: healthcare, finance, government, safety-critical systems,
projects with external audit or compliance requirements.

---

## Warning signs — what to look for during an audit

### 🔴 Orphan requirement (no upstream link)
The requirement exists, but it's unclear which business need it came from.
Diagnosis: a "nice-to-have" pushed through without analysis, or a link lost during restructuring.
Action: find the business need or freeze the requirement until clarified.

### 🟡 Unimplemented requirement (no downstream link)
The requirement is approved, but there's neither a component nor a test.
Diagnosis: a coverage gap, or a dead requirement (never picked up in a sprint, forgotten).
Action: check the status with the developer, add to the backlog, or mark it `deprecated`.

### 🟡 Requirement without a test (no `verifies`)
Implemented, but not verified.
Diagnosis: a QA gap, or the test exists but wasn't entered into traceability.
Action: check with the tester, add the link, or create a test.

### 🟢 Full coverage
Present: a source (derives ↑), an implementation (satisfies/derives ↓), a test (verifies).

---

## Versioning — naming pattern

```
FR-001       → current active version (always the current entry in requirements)
FR-001_v1.0  → original version (stored in history)
FR-001_v2.0  → after a substantial change
```

Rule: when a requirement changes, the old version moves to `history`,
and `requirements` retains only the current record with the new `version`.

---

## Node types in the 5.1 repository

Full list of valid node types:

| Type | Description | Source |
|-----|----------|----------|
| `business_need` | Business need from 6.1 — the **upstream root** for all traceability | 6.1 `define_business_needs` |
| `business_goal` | Business goal from 6.2 — a SMART goal with KPIs, the second tier of traceability | 6.2 `define_goals_and_objectives` |
| `business` | Business requirement — a top-level requirement | 4.3, manual entry |
| `stakeholder` | Stakeholder requirement | 4.3, manual entry |
| `solution` | Solution requirement (functional/non-functional) | 4.3, 7.1 |
| `transition` | Transition requirement (for migration, launch) | manual entry |
| `test` | Test case | 7.2, manual entry |
| `component` | Architectural component | 7.4 |
| `user_story` | User Story (Agile) | 7.1 |
| `functional` | Functional requirement | 7.1 |
| `non_functional` | Non-functional requirement | 7.1 |
| `business_rule` | Business rule | 7.1 |
| `use_case` | Use Case | 7.1 |
| `business_process` | Business process | 6.1, 7.1 |
| `data_dictionary` | Data dictionary element | 7.1 |
| `erd` | ERD entity | 7.1 |
| `change_request` | Change request | 4.2 |

**End-to-end traceability chain (start to finish):**
```
BN-001 (business_need) → derives → BG-001 (business_goal) → satisfies → FR-001 (solution) → verifies → TC-001 (test)
```
`run_impact_analysis` (5.4) can start from `BN-001` or `BG-001` and show the full downstream chain.
`check_coverage` checks: whether every BN is covered by at least one business goal, and whether every BG is covered by a requirement.

---

## Integration with other BABOK tasks

### Inputs to 5.1
- **6.1** `define_business_needs` → registers BN-xxx nodes of type `business_need`
  as upstream roots. End-to-end traceability starts right here (ADR-054).
- **6.2** `define_goals_and_objectives` → registers BG-xxx nodes of type `business_goal`
  with `BG derives BN` links. The second tier of traceability (ADR-062).
- **4.3** `save_confirmed_elicitation_result` → confirmed elicitation artifacts.
  This is the primary source for creating requirements in the traceability repository.
- **4.2** `save_cr_elicitation_analysis` → for a CR: new requirements or changes to
  existing ones. A trigger for updating traceability.
- **3.2** Stakeholder registry → determines who is the source of each requirement.

### Outputs from 5.1
- **5.3** Prioritization uses the traceability repository: dependencies between
  requirements affect implementation order (B cannot be prioritized above A if
  B depends on A).
- **5.4** Change assessment calls `run_impact_analysis`: the traceability graph is the
  infrastructure for CR assessment. 5.4 adds expert judgment on top of the technical result.
- **5.5** Requirements approval: `export_traceability_matrix` generates the matrix
  for formal sign-off. Orphan requirements do not go forward for approval.
- **6.x** User Stories, Use Cases, and functional requirements must always trace back
  to business requirements. Without traceability, coverage cannot be proven.

---

## Living traceability vs. a dead spreadsheet — keeping the repository from going stale

The most common problem in practice: the matrix gets created at project start and then forgotten.

**Update rule:** each of the following events triggers a traceability update:
1. A new requirement is added → `init_traceability_repo` or `add_trace_link`
2. A requirement changes → update the version, check affected links
3. A CR is accepted → run `run_impact_analysis`, update the affected links
4. A test is created → add a `verifies` link
5. A component's scope changes → check `satisfies` links

**Who is responsible for keeping it current:** in the AInalyst project, the MCP tools
are the "owner" of the repository. Every call to `add_trace_link` and every requirement
status update automatically updates the JSON file with the change date.
