# checklist_templates.md — Verification Checklists by Requirement Type

Source: BABOK v3, section 7.2 + BA practice.
Used by: Claude Code when performing task 7.2 (Verify Requirements).

---

## How to use the checklists

Group A (rule-based) is checked automatically via `check_req_quality`.
Group B is checked through analysis of the 5.1 repository.
Group C (Feasibility + Understandability) — expert assessment by the BA using the checklists below.

**Working pattern:**
1. Run `check_req_quality` — get the automatic flags.
2. For each problematic req — open the corresponding checklist below.
3. Go through the Group C items.
4. If you find an issue — `open_verification_issue`.
5. After fixing it — `resolve_verification_issue` + `mark_req_verified`.

---

## Checklist: User Story

### Group A (automatic)
- [ ] Atomic: one story = one need
- [ ] Unambiguous: no signal words ("fast", "convenient", "usually")
- [ ] Testable: at least 2 Acceptance Criteria
- [ ] AC has no ambiguity signals
- [ ] Priority is set

### Group B (repository)
- [ ] Traceability to a 4.3 artifact (source_artifact filled in)
- [ ] No conflicting stories for the same scenario
- [ ] Has links in 5.1 (to BR, FR, UC)

### Group C — Feasibility (expert)
- [ ] The team understands how to implement the action ("I want…")
- [ ] No technical constraints blocking implementation
- [ ] Fits into an iteration/sprint of a reasonable size (if Agile)
- [ ] Dependencies on other stories are clear and documented

### Group C — Understandability (expert)
- [ ] The role is real, not abstract ("User" is too broad)
- [ ] The action describes a need, not a technical solution
- [ ] The benefit contains business value, not a technical consequence
- [ ] AC are written in the language of system behavior, not implementation
- [ ] The story is understandable to a developer without extra explanation
- [ ] The story is understandable to a business sponsor without technical detail

**Bad:**
`As a user, I want REST API endpoint /api/v1/applications POST, so that data is persisted.`

**Good:**
`As a loan officer, I want to submit a new loan application, so that I can start the review process.`

---

## Checklist: Functional Requirement (FR)

### Group A (automatic)
- [ ] Atomic: one FR = one system behavior
- [ ] Unambiguous: no words without a metric
- [ ] Testable: has a numeric criterion or a clear binary condition
- [ ] The wording starts with "The system SHALL…"
- [ ] Priority is set

### Group B (repository)
- [ ] No FR with a contradicting statement
- [ ] Traceability to 4.3 and/or a User Story / Use Case

### Group C — Feasibility (expert)
- [ ] Technically achievable with the current stack
- [ ] Does not contradict architectural constraints
- [ ] Estimated complexity: S / M / L / XL (document it)
- [ ] Implementation-level dependencies are accounted for

### Group C — Understandability (expert)
- [ ] Clear what the system does (the action)
- [ ] Clear under what condition this happens (trigger/context)
- [ ] Clear what the outcome is
- [ ] No jargon specific to a single department
- [ ] All abbreviations are defined
- [ ] A developer can write a test without follow-up questions

**FR wording template:**
`The system SHALL [action] [object] [under condition/context], [result/constraint].`

**Bad:**
`The system shall be fast when loading data.`

**Good:**
`The system SHALL return the list of applications within 2 seconds for a query of up to 1000 records.`

---

## Checklist: Non-Functional Requirement (NFR)

### Group A (automatic)
- [ ] Has a numeric metric value
- [ ] Has a unit of measurement
- [ ] Has a measurement condition (under what load, in what environment)
- [ ] No words without values ("fast enough", "high availability")

### Group B (repository)
- [ ] Does not contradict other NFRs of the same aspect (performance, security)
- [ ] Traceability to a business requirement or UC

### Group C — Feasibility (expert)
- [ ] The metric is realistic for the technology stack
- [ ] The cost of achieving the metric is acceptable
- [ ] There is an understanding of how it will be measured (testing tool)

### Group C — Understandability (expert)
- [ ] Clear who is responsible for compliance
- [ ] There is an SLA or SLO context

**NFR wording template:**
`The system SHALL [metric] [numeric value] [unit] under [condition], measured by [how].`

**Bad:**
`The system shall be highly available.`

**Good:**
`The system SHALL provide 99.9% availability per month (no more than 43 minutes of downtime), excluding scheduled planned maintenance.`

---

## Checklist: Business Rule (BR)

### Group A (automatic)
- [ ] Atomic: one BR = one business constraint
- [ ] Unambiguous: no vague wording
- [ ] Has an applicability condition (if/when/under)
- [ ] Priority is set

### Group B (repository)
- [ ] Does not contradict another BR (especially in the same area)
- [ ] Traceability to a regulatory document or business requirement

### Group C — Feasibility (expert)
- [ ] The rule is implementable in the system (not just an organizational process)
- [ ] The source of the rule is known (law, internal policy, contract)
- [ ] The effective date is known

### Group C — Understandability (expert)
- [ ] The rule is understandable without domain knowledge
- [ ] Exceptions to the rule are documented as a separate BR
- [ ] The owner of the rule (who can change it) is defined

**Bad:**
`The system should check whether the loan amount is acceptable.`

**Good:**
`The loan amount may not exceed 5,000,000 rubles for individuals. Exceptions: purpose-bound mortgage loans (see BR-012).`

---

## Checklist: Use Case (UC)

### Group A (automatic)
- [ ] Atomic: one UC = one actor goal
- [ ] Unambiguous: no vague steps
- [ ] Testable: has at least one exception
- [ ] Has a Primary Actor
- [ ] Has a Precondition and Postcondition
- [ ] Priority is set

### Group B (repository)
- [ ] The actor is defined in the UC Diagram (no mismatch)
- [ ] No duplicate UC with the same scenario
- [ ] Traceability to the business process or a higher-level requirement

### Group C — Feasibility (expert)
- [ ] Every happy path step is implementable
- [ ] Exceptions are handled in the system (not just in the process)
- [ ] External systems/actors are available and ready for integration

### Group C — Understandability (expert)
- [ ] The UC name is in "Verb + Object" format ("Submit application", not "Application")
- [ ] Happy Path steps are numbered, the subject of each step is clear
- [ ] The business sponsor can verify the scenario is correct
- [ ] The developer understands what needs to be implemented without follow-up questions

---

## Checklist: Business Process (BP)

### Group A (automatic)
- [ ] Atomic: one BP = one business process (not several)
- [ ] Unambiguous: every step has an owner
- [ ] Testable: the end outcome is defined
- [ ] A trigger is set

### Group B (repository)
- [ ] All participants are present in the stakeholder registry (4.2)
- [ ] No duplicate process
- [ ] Linked to a UC (BP steps → Use Cases)

### Group C — Feasibility (expert)
- [ ] The process is implementable within the current organizational structure
- [ ] Process SLAs are realistic
- [ ] Integrations with external systems are possible

### Group C — Understandability (expert)
- [ ] The process is understandable to participants without BA explanations
- [ ] The Activity Diagram (.puml) matches the textual description
- [ ] Branches in the process are documented with conditions

---

## Checklist: Data Dictionary (DD)

### Group A (automatic)
- [ ] Atomic: each entity is described separately
- [ ] Unambiguous: attribute names have no abbreviations, or are spelled out
- [ ] Testable: type + constraints are specified for every attribute

### Group B (repository)
- [ ] All entities are present in the ERD (no name mismatch)
- [ ] No duplicate entities under different names

### Group C — Feasibility (expert)
- [ ] Data types are compatible with the technology stack
- [ ] Constraints are implementable at the DB/application level

### Group C — Understandability (expert)
- [ ] Entity names match the domain terminology
- [ ] Business rules for attributes are documented
- [ ] A developer understands the relationships between entities without extra explanation

---

## Checklist: ERD

### Group A (automatic)
- [ ] Atomic: each relationship is described separately
- [ ] Unambiguous: cardinality is clear (one-to-many, many-to-many)
- [ ] All entities in the ERD are present in the Data Dictionary

### Group B (repository)
- [ ] No "dangling" entities (without relationships)
- [ ] Entity names match the DD

### Group C — Feasibility (expert)
- [ ] Relationships are implementable in the target DBMS
- [ ] Many-to-many relationships are split via a junction table (if needed)

### Group C — Understandability (expert)
- [ ] The diagram is readable without explanations
- [ ] Relationship labels are added for non-obvious relationships

---

## Matrix: what MCP checks vs. what the BA checks

| Req type | MCP automatically | BA manually (checklist above) |
|---------|-------------------|--------------------------|
| User Story | AC count, ambiguity signals, priority | Role specificity, action vs solution, AC language |
| Functional | Measurability pattern, atomicity, priority | Tech feasibility, full coverage of condition+result |
| Non-Functional | Number present, ambiguity, priority | Metric realism, measurement tool |
| Business Rule | Condition presence, atomicity, priority | Source/authority, exceptions documented |
| Use Case | Exception presence, actor present, priority | Step clarity, actor in diagram |
| Business Process | Outcome present, trigger, atomicity | Org feasibility, diagram matches text |
| Data Dictionary | Constraint presence, ambiguity in names | Type compatibility, naming conventions |
| ERD | Entity names match DD | Cardinality accuracy, implementability |
