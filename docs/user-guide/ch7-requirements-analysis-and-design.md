# User Guide
## AI-powered Platform AInalyst
**Download:** https://github.com/chaussky/ainalyst.git

**LinkedIn:** https://www.linkedin.com/in/anatole-tchaoussky-82957a40b/

# Chapter 7: Requirements Analysis and Design Definition

---

## Overview of Chapter 7

BABOK Chapter 7, "Requirements Analysis and Design Definition," is the shift from strategy to specifics. Chapter 6 answered the questions "why are we changing" and "what is the strategy." Chapter 7 answers the question: **what exactly are we building, how is it organized, is it written correctly, does the business actually need it, how will we implement it, and is it worth doing at all.**

The six tasks of Chapter 7 form a single logical flow:

```
7.1 Specification   →   7.2 Verification (written correctly?)
        ↓                        ↓
7.4 Architecture    →   7.3 Validation (does the business need it?)
        ↓
7.5 Design Options   →   7.6 Value Assessment and Recommendation
```

This is the most "productive" chapter of the project: this is where requirements are actually created (User Stories, functional requirements, business rules, data models, business processes). This is where they get checked for quality and value. And this is where the final recommendation to the sponsor takes shape: which implementation option to choose and why.

**Why this chapter often gets done poorly.** BAs frequently reduce Chapter 7 to a single action: writing a list of functional requirements in an Excel table. Verification gets skipped: "it's obvious anyway." Validation gets skipped: "the customer said what they want." Requirements architecture never gets built: "we'll figure it out as we go." As a result, developers receive a list of features with no context, no priorities, no explanation of "why," full of contradictions and gaps, and the project starts stalling as early as the first sprint.

**Project phase.** Chapter 7 runs in the `design` phase. If you haven't switched the phase yet, ask AInalyst or run `python phase.py design`.

---

## Task 7.1: Specify and Model Requirements (Specification and Modeling)

### Summary

The BA translates the confirmed elicitation results from Chapter 4 into formal specifications: User Stories, functional requirements, business rules, data models (ERD), and business process descriptions (BPMN). Every artifact created is automatically registered in the traceability repository (5.1) and becomes part of the project's living requirements registry.

### BA pain points

**"Requirements live in my head, not in a document."** The BA ran 15 interviews and understood everything, then started "transferring" that knowledge to developers in meetings. A month later, different team members have different understandings of the same requirement. There's no single source of truth.

**"One big list of FRs."** Everything is written as "The system shall..." in a single table: business processes, rules, user scenarios, and technical constraints, all mixed together. Different stakeholders read this list and see different things. Nobody sees the full picture.

**"Requirements are written vaguely."** "The system shall process requests quickly," "the interface must be user-friendly," "security must be ensured": these phrasings can't be tested or evaluated. The developer interprets them one way, QA another, the customer yet another.

**"There's no traceability."** A requirement is written, but nobody knows where it came from or why. When the sponsor asks, "why do we even need FR-047?", the BA can't answer. When a stakeholder suggests, "let's drop this one," there's no way to quickly see what depends on it.

**"There's no coverage check."** The BA has written 50 requirements and thinks the job is done. But three of six business goals aren't covered by a single requirement, simply because it got forgotten in the flow of work.

### What we built

**Elicitation context analysis as a starting point.** The first step is `analyze_elicitation_context`: the platform reads the 4.3 artifacts (confirmed elicitation results) and proposes a list of candidate requirements with a recommended type and priority. The BA doesn't start from a blank page: they see a structured list of starting points based on what was already captured in Chapter 4.

**Six artifact types, each for its own purpose.** The platform supports a full range of notations:
- **User Story**: a user scenario in the format "As a [role], I want [action], so that [benefit]," with Acceptance Criteria
- **Functional Requirement (FR)**: system behavior in the format "The system shall..."
- **Non-Functional Requirement (NFR)**: quality constraints such as performance, security, and accessibility
- **Business Rule (BR)**: domain rules the system must follow
- **Business Process (BP)**: a BPMN process model with an auto-generated Activity Diagram (.puml)
- **Data Dictionary + ERD**: a description of entities and their relationships with an auto-generated diagram

**Automatic registration in traceability.** Every artifact created immediately appears in the 5.1 repository with `draft` status. Traceability to business goals is built into the creation process: the BA specifies linked goals when creating a requirement rather than adding them later as a separate effort.

**Coverage matrix at the end.** `build_coverage_matrix` shows which business goals are covered by requirements and which aren't. Green means covered, red means zero requirements, yellow means more than 10 requirements (possible over-engineering). The BA sees gaps clearly, before moving on to the next task.

### Value for the BA

**From "I understood everything" to "everything is captured."** Knowledge that lives only in the BA's head is a risk. The platform turns that knowledge into structured artifacts with traceability and history. A new team member joining a month later sees the full context: where the requirement came from, why, and who the source is.

**Different artifacts for different audiences.** The customer reads the User Story and understands it. The developer reads the FR and understands it. The lawyer reads the BR and understands it. This isn't one document "for everyone": it's the right artifact type for the right stakeholder. The platform helps choose the type instead of leaving the BA to guess.

**Auto-generated diagrams without extra tools.** Business Process and ERD artifacts generate PlantUML diagrams automatically. The BA doesn't open Visio or draw anything by hand: they describe the logic in text, and the platform generates the visualization. This saves time and reduces the chance of the document and the diagram drifting apart.

**Business goal coverage as a completeness criterion.** "Done" no longer means "I wrote everything I could remember"; it means "every business goal is covered by requirements." The coverage matrix gives an objective answer to the question of readiness.

### How to use it: an example

Continuing the contract-approval project. Elicitation (Chapter 4) is complete, and Chapter 6 is done.

*"Analyze the elicitation context for the contract-approval project."*

The platform reads the 4.3 artifacts and proposes: 3 User Stories (approval roles), 7 FRs (statuses, notifications, integration), 2 BRs (escalation rules), 1 BP (approval process), 1 ERD (contract structure).

*"Create a User Story: as an Approver, I want to receive a notification about a new contract awaiting approval, so that I don't miss the deadline. AC: the notification arrives within 5 minutes of assignment; it contains a link to the contract and the deadline."*

US-001 is created, registered in 5.1, and linked to BG-001.

*"Check business goal coverage."*

BG-001 is covered by 4 requirements. BG-002 (status transparency) has none. The BA creates additional requirements.

---

## Task 7.2: Verify Requirements (Requirements Verification)

### Summary

The BA checks the requirements that have been written for quality of wording: atomicity, clarity, testability, completeness, and consistency. This is a check of "was it written correctly," not "is this the right requirement" (that's Task 7.3).

Verification is professional quality control before requirements go to developers and testers. A wording error caught here takes minutes to fix. The same error caught during development takes days.

### BA pain points

**"It's obvious anyway."** The most common reason to skip verification. But "obvious to the BA" and "obvious to the developer" are two different things. "The system must respond quickly": the BA means seconds, the developer means "well, it shouldn't hang." The first bug triggers a round of "what did you actually mean."

**Untestable requirements.** "The system must ensure a high level of security": what does that mean? How would a tester verify it? There's no way. Requirements like this create an illusion of a complete spec without adding real value.

**"One requirement, three functions."** "The system shall accept requests, process them, and send notifications" is really three separate requirements in one. The developer doesn't know how to track them, and the tester doesn't know how to verify them individually.

**Divergence between models.** The BA created an ERD with 8 entities and separately described a business process with a different set of entities. Nobody notices the mismatch until a developer asks "what maps to what."

**"Requirements are agreed" without any real agreement.** One stakeholder said "the system must support Excel," another said "no Excel, API only." Both requirements got written down, and nobody noticed the contradiction.

### What we built

**Automatic checks against BABOK's 9 characteristics.** `check_req_quality` analyzes all project requirements (or a selected list) across two groups:
- **Group A (automatic):** atomicity (no "and," "as well as," "or"), unambiguity (no "quickly," "conveniently," "as appropriate"), testability (a concrete criterion exists), prioritization, conciseness
- **Group B (structural):** consistency (no conflicting statuses in 5.1), completeness (a source_artifact and traceability exist)

The result is a concrete list of problems: which requirement, which characteristic was violated, severity (blocker / major / minor), and how to fix it.

**Verification issue tracker.** Every problem found is logged as a Verification Issue (VI-xxx) with a type, severity, and owner. The BA doesn't hold the list of fixes in their head: all open and closed issues are stored in the system. Once fixed, an issue is closed with notes describing exactly what was corrected.

**Model consistency checks.** `check_model_consistency` cross-checks the 7.1 artifacts against each other: entities in the Data Dictionary vs. the ERD, Use Cases vs. the UC diagram, business process participants vs. actors. Discrepancies are surfaced automatically: the BA doesn't have to hold several documents in their head and hunt for mismatches manually.

**The `verified` status as an explicit gate.** A requirement with blocker issues cannot get `verified` status without an explicit BA decision. This is a barrier: you can't "forget" about a critical problem and move on. Once all blockers are resolved, `mark_req_verified` moves the requirement to the next status.

**A Verification Report handed off to 5.5 and 7.3.** The final report contains: the percentage of verified requirements, top issue types, a list of remaining blocker issues, and a verdict on readiness for approval. This is a ready-made document; there's no need to prepare a separate summary.

### Value for the BA

**Errors are caught before development, not during it.** Replacing "quickly" with "within 2 seconds under a load of up to 500 users" takes a minute in 7.2. The same fix midway through a sprint means a discussion, a re-estimate, and possibly rework of the architecture. The cost of fixing an error grows exponentially with every stage; the platform helps catch it at the cheapest one.

**Testers work from clear criteria.** A verified requirement contains a measurable criterion. That's not just tidiness, it's a direct time saving for QA: fewer "what did you mean" questions, fewer test cases written on a guess, fewer disputed bugs over "is this a feature or a defect."

**A professional stance in front of stakeholders.** When the BA hands over a Verification Report with 94% verified and a list of closed issues, that's a demonstration of a mature process. Not "we wrote the requirements," but "we wrote the requirements and checked them against BABOK's 9 criteria, with documented results."

### How to use it: an example

*"Check the quality of all requirements for the contract-approval project."*

Result: US-003, missing_ac (blocker); FR-007, the word "promptly" (ambiguity, major); FR-012, two actions in one requirement (not_atomic, major).

*"Log an issue for US-003: no Acceptance Criteria, blocker."*

VI-001 created.

*"US-003 has been fixed: 3 AC added: the notification arrives within 5 minutes, contains a link and the deadline, and is logged if email is unavailable."*

*"Close VI-001."* The resolution note is recorded.

*"Check model consistency."* The ERD and Data Dictionary are in sync, no discrepancies.

*"Verify all the fixed requirements and generate a report."*

Verification Report: 48/50 verified, 2 minor issues still open, verdict: ready for validation.

---

## Task 7.3: Validate Requirements (Requirements Validation)

### Summary

The BA checks not the quality of wording (that's 7.2), but the substantive correctness: does the business actually need these requirements, do they align with the business goals and the future state from Chapter 6, and have the key assumptions been identified. This is an iterative task; it can be run several times at different stages of the project.

### BA pain points

**"The customer asked for it, so it's needed."** A requirement made it into the spec because someone asked for it. But does it align with the project's business goals? Sometimes stakeholders ask for what they want, not what the business needs. The distinction matters.

**"Orphan requirements."** Midway through the project, the BA discovers that 15% of requirements don't trace to any business goal. Where did they come from? Why are they there? Should they be removed? But someone wrote them, and now it feels risky to take them out.

**Implicit assumptions that blow up at the end.** "We assumed the ERP integration was possible through an API," and it turns out the ERP doesn't support an API. Nobody logged or validated that assumption. Now 30% of requirements need to be rewritten.

**"The business context exists only in the BA's head."** The BA knows the project's business goals, but they're never written down anywhere as a benchmark for checking requirements against. Every check is "I remember we wanted something like that."

### What we built

**Business context as an explicit benchmark.** `set_business_context` captures the business goals (with KPIs), a description of the future state, and the solution scope in one place. If Tasks 6.1 and 6.2 are complete, this data is pre-filled automatically from their artifacts: the BA doesn't re-enter the same data by hand. This context becomes the benchmark for all subsequent validation.

**Automatic business goal alignment check.** `check_business_alignment` runs a BFS traversal of the 5.1 traceability graph and checks: is a `business_goal` node reachable from each verified requirement? Requirements with no traceability to a business goal are flagged explicitly, and the BA decides: is this a gap in traceability, or is the requirement genuinely unnecessary?

**Assumption log with explicit status.** `log_assumption` records each assumption: what's being assumed, on what basis, and how risky it is. High-risk assumptions (`high_risk`) trigger a warning when trying to move a requirement to `validated` status. This pushes the BA to validate them before moving on to the next stage, rather than forgetting about them.

**Three axes of validation.** The platform structures validation around three questions: (1) Value, does the requirement deliver a benefit to stakeholders? (2) Alignment with the future state, does it help achieve the to-be from 6.2? (3) Assumptions, have hidden assumptions been identified, and are they being managed?

**A Validation Report as the output for 5.5.** The final report is a business goal coverage matrix, a list of orphan requirements, and the status of assumptions. A ready-made document to hand off for approval in Task 5.5.

### Value for the BA

**"Unnecessary" requirements are caught before development.** A requirement with no traceability to a business goal is a candidate for removal or clarification. Finding 8 such requirements in 7.3 saves development resources. Finding them after release means answering "why did we even build this?" with an unpleasant answer.

**Assumptions get managed, not just accumulated.** The assumption log isn't a formality. It's a list of "bombs" that could go off later. The platform makes them visible and trackable. A high-risk assumption logged and validated at the 7.3 stage doesn't turn into a crisis during development.

**Continuity with Chapter 6, without duplication.** A BA who conscientiously completed 6.1 and 6.2 gets a pre-filled business context automatically. The data is reused, not re-entered by hand. This reduces the risk of the strategic document and the validation criteria drifting apart.

### How to use it: an example

*"Set the business context for contract-approval."*

If 6.1/6.2 are complete, the platform pre-fills: BG-001 (cut the cycle from 14 to 3 days), the future state (a unified status registry, automatic notifications), the scope (status module plus ERP integration, excluding electronic signature).

*"Check whether all verified requirements align with the business goals."*

Result: 46 of 48 trace to BG-001 or BG-002. FR-031 and FR-032 are orphan requirements.

*"FR-031 and FR-032 are mobile app requirements. They're out of scope. Mark them as out_of_scope."*

*"Log an assumption: we're assuming the ERP supports a REST API. Risk: high, needs to be checked with the IT architect before development starts."*

ASM-001 is created with a validation priority.

*"Generate the Validation Report."* Ready to hand off to 5.5.

---

## Task 7.4: Define Requirements Architecture (Requirements Architecture)

### Summary

The BA organizes requirements into a coherent structure, an architecture: defining the viewpoints of different stakeholders, grouping requirements into the corresponding views, and identifying structural gaps. The result is an Architecture Document, which is handed off to 7.5 as an input artifact and to 4.4 for communication with the team.

### BA pain points

**"Every stakeholder sees something different."** The customer wants to see business processes, the developer wants functional requirements, the data architect wants data models, the CISO wants security requirements. If all 80 requirements are dumped into a single table, everyone wastes time hunting for "their" section and risks missing something important.

**"Nobody sees the whole picture."** The requirements are written, but it's unclear how they form a coherent system. There's no answer to: are all user roles covered by scenarios? Does every component have NFRs? Where are the gaps?

**"The architect gets requirements with no context."** A technical architect who needs to design the system receives a list of 60 FRs and has to work out the structure themselves. That's their time, their risk of misunderstanding something, and, indirectly, the project's time and money.

### What we built

**Automatic mapping by artifact type.** `analyze_requirements_architecture` reads the 5.1 repository and automatically distributes requirements across standard viewpoints: User Stories and Use Cases go to "Users and Interaction"; FR/NFR go to "Functionality"; BP goes to "Business Processes"; DD/ERD go to "Data"; BR goes to "Business Rules." This happens without any BA involvement: the platform builds the picture from what was already created in 7.1.

**Custom viewpoints for specific contexts.** `add_custom_viewpoint` lets the BA add a viewpoint that isn't in the standard set: "Security and Access" for banks, "Audit and Compliance" for regulated projects, "Data Migration" for legacy-system replacement projects. The BA specifies which requirements belong to it, and the platform includes them in the architecture.

**Whose interests a requirement touches — stated, not guessed.** `declare_stakeholder_interest` records that a stakeholder's interests are affected by specific requirements. This is deliberately a different thing from two facts the platform already holds: the `owner` field (7.1) says who is answerable for the *wording* of a requirement, and the RACI role (5.5) says who decided on an *approval package*. The BA does not re-enter those — the platform reads them as evidence and says where each tie came from. Repeat calls merge, so nothing an earlier call recorded is ever silently erased; withdrawing a declaration takes an explicit `remove`.

**Two-level gap check.** `check_architecture_gaps` identifies gaps at two levels:
- Matrix level: does every stakeholder in the registry have a recorded tie to at least one requirement? Is every business goal covered by at least one view?
- Semantic level: is there a Use Case with no business process? An NFR not linked to any FR? An FR with no usage scenario?

The stakeholder verdict rests on recorded facts — a declared interest, ownership of a requirement, or an approval decision on it. A person reachable only because their name happens to share a word with some requirement's title is reported as a *warning* that says so, not as a critical finding: a shared word is a coincidence, and a verdict that hides its method invites more confidence than its evidence carries.

**A versioned architecture snapshot.** `save_architecture_snapshot` captures the current state of the architecture with a version number and a comment. The history of snapshots is preserved, so you can see how the requirements architecture evolved over the course of the project.

### Value for the BA

**Every stakeholder gets "their" slice.** The Architecture Document is organized by viewpoint. The customer opens the "Business Processes" section and sees only what they need. The architect opens "Functionality" and "Data." This reduces the cognitive load of reading and lowers the risk that an important requirement gets missed by the stakeholder who needs it.

**Structural gaps are found before design.** Discovering that the "Financial Controller" role exists in the stakeholder registry but has no recorded tie to a single requirement takes minutes to resolve in 7.4 — either the tie exists and simply was never stated, in which case you declare it, or it genuinely does not, in which case a requirement is missing. Discovering the same thing in 7.5, while building design options, means rework and lost time.

**An input artifact for design.** The Architecture Document is exactly what a technical architect needs to start work on design options (7.5): a structured picture instead of a chaotic list. The BA saves the team time and reduces the number of clarifying questions.

### How to use it: an example

*"Analyze the requirements architecture for contract-approval."*

The platform builds the picture: 4 viewpoints, 48 requirements distributed. Warning: BG-002 isn't covered by the "Data" viewpoint.

*"Add a custom viewpoint 'ERP Integration': NFR-004, FR-019, FR-020, FR-021. Stakeholder: IT architect."*

*"Check for gaps."*

Critical: the "Financial Controller" stakeholder is in the 3.2 registry, but has no US/UC at all. Warning: NFR-008 isn't linked to any FR.

*"Save snapshot v1.0."* The Architecture Document is saved and ready to hand off to 7.5.

---

## Task 7.5: Define Design Options (Design Options)

### Summary

The BA forms and compares implementation options for the solution: build from scratch (Build), buy an off-the-shelf product (Buy), or combine the two (Hybrid). For each option, requirements are allocated across versions (v1 / v2 / out_of_scope), and the options are compared using weighted criteria. The result is a Design Options Report, handed off to 7.6 for the final recommendation.

### BA pain points

**"Only one option."** "We decided from the start that we'd Build, why consider anything else?" The result: no alternatives analysis, no comparison, no rationale for the choice. If something goes wrong later, there's no documented answer to "did you consider other options?"

**"Everything goes into the first version."** The BA puts 100% of the requirements into the MVP. As a result, the first release slips, the budget overruns, and the team is overloaded. Prioritizing requirements by version, "what's necessary" rather than "what would be nice," is one of the most painful conversations to have with the customer.

**"Dependencies aren't checked."** The BA decided FR-010 goes into v2, but FR-010 is a dependency for FR-003, which is in v1. As a result, the developer can't implement FR-003 without FR-010. This surfaces in Sprint 2 and forces a plan revision.

**"Selection criteria are personal opinion."** "I think Buy is better, it's cheaper and faster." Why exactly Buy? Unclear. The counterpart says, "I think Build is more flexible." The conversation turns into an exchange of opinions with no data behind it.

### What we built

**Three approaches with explicit trade-offs.** For each option (Build / Buy / Hybrid), the BA describes the components, improvement opportunities, and success metrics. The platform structures the description of each option using the same template, so all three options are comparable on the same dimensions.

**Automatic allocation of requirements to versions.** `allocate_requirements`, in `auto_suggest=True` mode, reads priorities from the 5.1 repository: Must goes to v1, Should goes to v1/v2, Could goes to v2, Won't goes to out_of_scope. The BA gets a proposal, reviews it, and overrides specific requirements as needed. This isn't an automatic decision; it's an automatically prepared starting point for the conversation.

**Automatic dependency checking.** Once the allocation is approved, the platform runs a BFS over the dependency graph: if requirement A in v1 depends on requirement B in v2, that's a warning. The BA sees the conflict clearly and decides: move B to v1, or reconsider the dependency.

**A comparison matrix with configurable criteria.** `compare_design_options` builds a comparison across standard criteria: cost, speed, risk, requirement coverage, flexibility. The BA can add custom criteria, for example "alignment with the company's vendor policy" or "ability to roll out in phases." The result is a comparison table with a rationale for stakeholders.

### Value for the BA

**A justified choice, not "we just decided."** The comparison matrix is a document for stakeholders. When the director asks "why Hybrid?", the BA opens the Design Options Report: here are the three options, here are the criteria, here are the scores, here's why Hybrid wins on the balance of coverage and flexibility given this budget. It's a data-driven conversation.

**v1 that's actually achievable.** Auto-suggest based on priorities from 5.3, plus dependency checking, protects against an overloaded MVP. The BA comes to the development team with an allocation where v1 contains only the Must items plus verified dependencies. Fewer unpleasant surprises in Sprint 1.

**The Design Options Report as a bridge to 7.6.** The document contains all the data needed for value assessment: options, components, requirement coverage by version, potential improvements. The BA doesn't have to prepare a separate document for the next step; it already exists.

### How to use it: an example

*"Create three design options for contract-approval. OPT-001: Build, an in-house module. OPT-002: Buy, the off-the-shelf DocuWare SaaS solution. OPT-003: Hybrid, an open-source BPM engine plus a custom notification module."*

Three options are created with components and improvement opportunities.

*"For each option, allocate requirements across versions using auto-suggest."*

Auto-suggest: 28 requirements to v1, 14 to v2, 6 to out_of_scope. Dependency check: FR-019 (v2) is a dependency for FR-015 (v1), a warning.

*"Move FR-019 to v1 for all options. Accept the rest."*

*"Compare the options."*

Matrix: OPT-003 (Hybrid) wins on coverage and flexibility, OPT-002 (Buy) wins on speed, OPT-001 (Build) wins on customizability. The BA documents a preliminary position: "Recommending OPT-003, to be finalized in 7.6."

---

## Task 7.6: Analyze Potential Value and Recommend Solution (Value Assessment and Recommendation)

### Summary

The BA assesses the potential value of each design option (benefits, costs, risks), compares them, and formulates an official recommendation to the sponsor. This is the final task of Chapter 7. The result is a Recommendation Document, handed off to the sponsor for a decision and to Chapter 8 as the baseline for measuring the outcome achieved.

### BA pain points

**"The recommendation is a personal opinion."** "I think this option is better" isn't a professional stance for a document going to a sponsor with a multi-million-dollar budget. No data, no methodology, no rationale.

**"Benefits are listed, not calculated."** "Option A will give us: faster processes, fewer errors, higher satisfaction." That's a wish list, not a value analysis. How much is each benefit worth? How confident are we in it?

**"There are no success metrics."** The decision is made, the project launches. A year later the sponsor asks: "did we achieve what we wanted?" There's no answer, because nobody defined what would count as success before the work began.

**"`no_action` never gets considered."** If no option delivers enough value, the right recommendation might be "do nothing" or "revisit the analysis." But the BA has no tool for reaching that conclusion, so the recommendation is always "do something."

### What we built

**A structured assessment based on a formula.** `add_value_assessment`, for each option, gathers: benefit types (financial, operational, strategic, human) with magnitude and confidence ratings; costs (implementation, operational); and a risk profile (pulled automatically from 6.3, if that file exists). `compare_value` calculates a Value Score using the formula: `Benefits×2.0 + Alignment×1.5 − Cost×1.5 − Risk_Penalty×1.0`. This isn't a "black box": the BA sees every component of the score.

**Four legitimate recommendation outcomes.** The platform supports every possible conclusion: `recommend_option` (one option is clearly the best), `recommend_parallel` (two options are implemented in parallel), `recommend_reanalyze` (none of them fit, a new analysis is needed), `no_action` (benefits are lower than costs, don't proceed). The BA isn't backed into a corner of "you have to recommend something."

**Success metrics as a mandatory element.** For a `recommend_option` or `recommend_parallel` recommendation, success_metrics are required. This isn't a formality: it's the baseline for Chapter 8. "NPS above 65 by December," "processing time under 3 days within 6 months": concrete, measurable success criteria, set before development begins.

**A pre-flight check before finalizing.** `check_value_readiness` (optional) checks the completeness of the assessments: are all options assessed, is the business context in place, is the data correct. This is a safety check before the document goes to the sponsor.

**Recommendation Document, a professional output artifact.** `save_recommendation` generates a document with: an executive summary for the sponsor, an assessment of each option, a Value Score matrix, the rationale for the recommendation, and the list of success metrics. This is a ready-made document for presentation.

### Value for the BA

**A recommendation to the sponsor backed by data, not opinion.** The Recommendation Document is a structured argument: here are the three options, here's how we assessed them, here's the formula, here's the winner with a Value Score of 8.4 against 6.1 and 4.7, and here's why. The sponsor makes the decision with a clear understanding of the rationale. The BA is protected if something goes wrong later.

**Success metrics protect the project's outcome.** When the sponsor asks a year later, "did we achieve the goal?", the BA opens the Recommendation Document: the success metrics were "processing time under 3 days" and "NPS above 65." The facts: 2.8 days and NPS 68. The project succeeded against its defined criteria. That's an objective assessment, not a subjective "it seems better now."

**Seamless handoff to Chapter 8.** The Recommendation Document with success metrics is a precise input artifact for the Solution Evaluation tasks (Chapter 8). There's no need to reconstruct "what were we actually trying to achieve": it's on record, dated and versioned.

**A professional closing act for Chapter 7.** A BA who works through the full path, 7.1 through 7.2, 7.3, 7.4, 7.5, and 7.6, arrives at the sponsor's desk with a complete package: requirements specified, verified, validated, organized into an architecture, implementation options compared, value calculated, recommendation justified. This isn't just a list of requirements; it's a complete analytical work product.

### How to use it: an example

*"Assess the value of all three options for contract-approval."*

OPT-003 (Hybrid): benefits, operational (reduced processing time, fewer errors, confidence 0.8), strategic (scaling flexibility, confidence 0.6); costs, moderate; risks pulled from 6.3 (2 High risks, but mitigation plans are in place).

*"Compare the options."*

Value Score: OPT-003 → 8.4, OPT-002 → 6.1, OPT-001 → 5.3. Winner: OPT-003.

*"Generate the final recommendation: recommend_option, OPT-003. Success metrics: approval cycle time under 3 business days within 6 months, adoption rate above 85% within 3 months."*

Recommendation Document saved. The project is ready for Chapter 8 (Solution Evaluation) and for handing the decision off to development.

---

## Final synthesis for Chapter 7

**Chapter 7 is the project's productive chapter.** If Chapter 6 provides the strategic rationale, Chapter 7 is where the BA's intellectual product actually gets created: structured, verified, validated requirements, with an architecture, implementation options, and a justified recommendation. This is what the business analysis profession exists for.

**Every task in Chapter 7 eliminates a specific class of risk:**

- 7.1 eliminates the risk of "requirements existing only in someone's head": it creates a single source of truth
- 7.2 eliminates the risk of "untestable, vague wording": it verifies quality
- 7.3 eliminates the risk of "unnecessary requirements with no value": it checks alignment with business goals
- 7.4 eliminates the risk of "nobody seeing the whole picture": it organizes requirements for every audience
- 7.5 eliminates the risk of "an overloaded MVP with unnoticed dependencies": it structures the options
- 7.6 eliminates the risk of "no success criteria": it locks in success metrics before development starts

**The Chapter 7 artifact chain**, after a full run through:

```
reports/
  7_2_verification_report_{project}.md    ← requirements quality, issues
  7_3_validation_report_{project}.md      ← business goal alignment, assumptions
  7_4_architecture_{project}.md           ← viewpoints, gaps, snapshot
  7_5_design_options_{project}.md         ← options, allocation, comparison
  7_6_recommendation_{project}.md         ← value, recommendation, success metrics
```

Requirement specifications (US, FR, NFR, BR, BP, ERD) are stored in `governance_plans/{project}_specs/` and are available as living artifacts, not a static document.

**The BA's responsibility in Chapter 7** is focused on analytical decisions: what actually constitutes a requirement, which assumptions are critical, how to allocate requirements across versions, which implementation option to recommend. AInalyst handles everything technical: storage, traceability, dependency checking, diagram generation, Value Score calculation, and document formatting.

**Practical outcome:** a BA who has gone through Chapter 7 on the platform hands development not a 60-row Excel table, but a structured package: traceable, verified requirements; a justified implementation choice; and defined success criteria. This is professional work that saves the whole team time and increases the odds that the project achieves its goals.
