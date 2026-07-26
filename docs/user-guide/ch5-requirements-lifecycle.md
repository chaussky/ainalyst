# User Guide
## AI-powered Platform AInalyst
**Download:** https://github.com/chaussky/ainalyst.git

**LinkedIn:** https://www.linkedin.com/in/anatole-tchaoussky-82957a40b/

---
# Chapter 5: Requirements Life Cycle Management

---

## Overview of Chapter 5

Chapter 5 of BABOK, "Requirements Life Cycle Management," covers what happens to requirements **after** they are elicited. Chapter 4 produces raw material (transcripts, facts, observations); Chapter 5 turns that raw material into a managed, living requirements registry that follows the project from start to delivery.

The key idea of this chapter: requirements are not a document written once. They live, change, age, conflict, acquire statuses, and accumulate relationships. The BA's job is to act as the "steward" of this registry throughout the project.

Chapter 5 answers five key questions every practicing BA faces:

- **5.1**: *Where did this requirement come from, and what changes if it changes?* (traceability)
- **5.2**: *Are my requirements still current right now?* (maintenance)
- **5.3**: *What should be done first, and how do we reconcile different stakeholders' opinions?* (prioritization)
- **5.4**: *Should this change be accepted, and what does it drag along with it?* (change assessment)
- **5.5**: *Are the requirements formally agreed?* (approval and baseline)

Work on Chapter 5 runs in parallel with Chapter 4: every requirement confirmed in 4.3 immediately enters the Chapter 5 infrastructure. From there, tasks 5.1-5.5 accompany the project all the way through the transition to Chapter 6.

---

## Task 5.1: Trace Requirements (Requirements Traceability)

### Summary

The BA builds and maintains a graph of relationships among all project artifacts: business needs, stakeholder requirements, functional requirements, tests, components. This graph is the "skeleton" that holds the project together and makes every change manageable.

### BA pain points

**A requirement change triggers an unpredictable reaction.** A CR comes in: "let's change the discount calculation logic." The BA changes FR-014. Only later, mid-sprint, does it turn out that FR-014 depends on FR-022, FR-022 is linked to NFR-005 for performance, and 4 QA test cases are tied to that same chain. None of this was visible in advance, because the relationships lived in someone's head or in a spreadsheet.

"Where did this requirement come from?" is a typical question during a review or audit. The BA flips through a notebook, trying to remember. In regulated projects (banking, pharma, government), the absence of traceability is not just a risk, it is a compliance violation.

**Coverage is checked manually, or not checked at all.** Before handing off to development, the BA doesn't know: does every requirement have a "parent" (a business need)? Is every requirement covered by test cases? Is every feature implemented? Doing this audit by hand takes hours in a spreadsheet.

**"Dead" traceability.** The BA created a matrix at the start of the project, and it looked great. Then requirements changed, and the matrix didn't. Three months later it describes reality only half the time. A stakeholder relying on it is working with stale data.

### What we built

**A relationship graph as a living repository.** `init_traceability_repo` creates a structured JSON repository for the project. From that point on, every requirement is a node in the graph, and every relationship between them is an edge with a type: `derives` (originates from), `depends` (depends on), `satisfies` (fulfills), `verifies` (verifies), `modifies` (changes, for CRs).

**Adding relationships in one step.** `add_trace_link` takes two nodes and a relationship type. The BA doesn't fill out tables: they describe the situation out loud, *"FR-014 originates from SR-003, note that down,"* and AInalyst calls the tool. The graph grows automatically.

**Impact analysis in seconds.** `run_impact_analysis` traverses the graph in depth from the changed requirement and returns a full list of affected artifacts: which requirements, tests, components, and CRs. This is the underlying mechanism for Task 5.4, assessing the cost of a change.

**Coverage audit.** `check_coverage` checks the entire graph and returns a list of issues with color coding: 🔴 a requirement with no source (orphan), 🟡 a requirement with no implementation or no test, 🟢 full coverage. This is done before prioritization and before approval.

**Traceability matrix on demand.** `export_traceability_matrix` generates a ready-made matrix in Markdown. It can be dropped straight into the approval package for stakeholders or sent off for audit.

**Three formality presets.** Lite (Agile, startup), Standard (mid-size projects), Full (regulated, external audit, enterprise). Chosen once, based on the project context. The BA doesn't have to guess which documentation level is needed: the skill recommends one based on a few questions.

### Value for the BA

**Every change is manageable.** Instead of "let's see what this affects," there's an instant list of everything affected, with the relationship type for each item. The BA can bring a complete impact report to a meeting with the customer, generated in 10 seconds instead of several hours.

**Audit-ready at any moment.** Traceability is stored in structured JSON, from which the matrix is generated in a single step. For regulated projects this matters a great deal: when asked *"show the traceability of requirement FR-047 back to the business need,"* the answer is ready immediately.

**Coverage is never missed.** Running `check_coverage` before each key step (prioritization, approval) guarantees that the BA doesn't carry requirements without business justification into the next stage. This reduces the risk of disputes during development: "why are we even doing this?"

**Traceability lives alongside the project.** Every CR, every requirement change passes through the graph. The matrix never goes stale, because it's updated through the skill's tools rather than by hand.

### How to use it: an example

The project has kicked off, and the first confirmed requirements have come out of Task 4.3. The BA says:

*"Let's start traceability for the CRM project. We're Agile, a team of 12, no external audit."*

AInalyst recommends the Standard preset and initializes the repository. Next, the BA adds the first requirement:

*"FR-001: user authentication. Originates from SR-002, a security requirement from the IT director."*

AInalyst calls `add_trace_link` and records the relationship `FR-001 derives SR-002`. After a few more iterations, the BA asks for a check:

*"Run a coverage audit before we move on to prioritization."*

`check_coverage` returns: FR-007 has no parent (🔴), NFR-003 has no test (🟡), everything else is fine (🟢). The BA asks the analysts where FR-007 came from: it turns out this requirement was never confirmed in 4.3, someone added it "on the fly." The problem is caught before development, not during it.

---

## Task 5.2: Maintain Requirements (Requirements Maintenance)

### Summary

The BA keeps the requirements registry current: updating statuses and versions, flagging obsolete requirements, regularly auditing the registry's "health," and identifying candidates for reuse in other initiatives. This is an ongoing task that runs throughout the entire project.

### BA pain points

**The registry freezes at the moment it's created.** The BA gathers requirements, records them, and never comes back. A month of active work later: 5 requirements have changed substantively, 3 are no longer relevant, 2 have a new owner. The registry still looks exactly like it did on day one.

**Requirement versioning isn't tracked.** A CR comes in, and the BA tweaks the wording of FR-017. The previous version isn't saved. A week later the customer asks: *"why does the requirement now say this? We agreed on something different."* The BA can't show the change history: there's no documentary trail.

**Requirement statuses are out of date.** A requirement has been sitting "in approval" for three weeks, but only because the approval actually went through and nobody updated the status. A developer looks at the registry and can't tell: start working on it, or wait?

**"Must drift."** By the end of the elicitation stage, 70% of requirements end up in the Must category. Everything is "mandatory," everything has high priority. The registry loses its structure: it no longer helps anyone make decisions, it just creates the appearance of work.

**Reuse never happens.** The BA starts a new project and writes requirements from scratch. Yet a previous project already had "The user must authenticate through corporate SSO," a requirement applicable to three out of five initiatives. But it sits in last project's folder, and nobody remembers it's there.

### What we built

**Updating requirements with history.** `update_requirement` updates a requirement's attributes (status, priority, wording, version) and automatically saves the history: what it was, what it became, the date, the reason. Three months later, you can pull up the full timeline of any requirement.

**Proper deprecation.** `deprecate_requirements` marks a requirement as obsolete with a choice of final status: `deprecated` (obsolete, no replacement), `superseded` (replaced by another requirement, which is specified), `retired` (project completed). The requirement is not deleted from the repository; the history is preserved for audit.

**Registry health audit.** `check_requirements_health` analyzes the entire registry and returns: 🔴 highly volatile requirements (changed too often, a signal of an unstable stakeholder or poor wording), 🟡 requirements that haven't been updated in a long time (possibly stale), 🟡 requirements stuck in `draft` status for too long. Each item comes with a recommended action.

**Finding reuse candidates.** `find_reusable_requirements` filters the registry by type, topic, status, and the `reuse_candidate` flag. It returns a list of requirements with a suitability rating: stable ones, worded without ties to a specific system, with a final status, make the best candidates.

**Automatic detection of "Must drift."** During the `check_requirements_health` audit, the system calculates the share of Must requirements out of the total. If it exceeds the threshold (40% by default), the BA gets a warning. This is a signal to revisit priorities before the next prioritization session.

**Two more checks read the plan from Task 3.4, when there is one.** If 3.4 planned a reuse scope, `find_reusable_requirements` ranks by it and names the planned repository — an explicit scope passed to the tool still wins. The scope raises a requirement's suitability score; it does not hide anything below the target, because most requirements are never tagged with a scope at all and filtering would empty the report. If 3.4 planned which attributes this project maintains (Minimum / Standard / Full), `check_requirements_health` audits exactly that set instead of just `owner`; a project on `Minimum` deliberately stops getting the "No owner" warning, because owner was never something it committed to tracking. Without a 3.4 plan, both tools behave exactly as they did before.

### Value for the BA

**The registry reflects reality, not history.** When a developer opens the registry before a sprint, they see current statuses, current versions, current owners. The time spent asking "is this approved yet?" and "is this still relevant?" drops sharply.

**Change history is the evidence base.** Whenever someone says "but we agreed on something else," the BA opens up the history of that specific requirement: version 1.0 looked like this, a CR came in on February 23, version 1.1 was agreed with so-and-so. The conversation turns constructive immediately.

**A healthy registry at every key step.** `check_requirements_health` runs before prioritization (5.3) and before approval (5.5). This guarantees the BA moves into the next stage with clean, current material rather than accumulated technical debt.

**Savings at the start of new projects.** `find_reusable_requirements` searches across every past project on the platform. A ready-made requirement from a previous project, complete with change history and an `approved` status, saves hours of elicitation and wording work. This is especially valuable in organizations running many similar initiatives.

### How to use it: an example

Midway through the project. A CR comes in: the customer wants to change the notification logic. The BA asked the developers to update FR-031, and 5.4 has already approved the CR. Now the registry needs updating.

*"Update FR-031: status changes to `under_change`, version goes from 1.0 to 1.1, here's the new wording. Reason: CR-005, approved by the sponsor."*

AInalyst updates it, and the history is recorded. A month later, an audit:

*"Run a registry health check before we move on to approval."*

`check_requirements_health` returns: NFR-002, last updated 6 weeks ago, possibly stale; FR-019, sitting in `draft` status for 3 weeks. The BA checks with stakeholders and closes out the open questions. A clean registry moves on to approval.

---

## Task 5.3: Prioritize Requirements (Requirements Prioritization)

### Summary

The BA determines the relative importance of requirements for stakeholders, chooses a prioritization method that fits the project context, collects scores, aggregates them, identifies conflicts between stakeholders, and facilitates their resolution. This task repeats with every planning cycle, not just once.

### BA pain points

**"Everything is important."** A classic situation: after elicitation you have 80 requirements and 5 stakeholders, each convinced their own requirements are the priority. The BA has to build a sensible order of implementation. Without a method, that's impossible. With a method, stakeholders still need convincing.

**Conflicts between stakeholders go undocumented.** The sales director wants FR-024 in the first sprint. The IT director wants FR-048. Both are right from their own department's point of view. The BA keeps track of the conflict in their head and tries to sort it out in a meeting. If the meeting never happens, the conflict stays unresolved and resurfaces during development.

**Choosing a prioritization method is a gut call.** Most BAs use MoSCoW because everyone does. MoSCoW is good for categorization, but it breaks down when there's a large number of Musts, and it ignores implementation cost. WSJF works better for Agile, but it needs estimates from developers that the BA may not have. The right method is the one that fits the context.

**Dependency violations go unchecked.** FR-019 is set to `Could`, FR-020 to `Must`. But FR-020 depends on FR-019, and it's impossible to implement without it. The conflict surfaces during sprint planning, not during prioritization.

**Unstable requirements get high priority.** FR-011 is set to Must, even though its wording has changed 4 times in 3 weeks. Planning a Must requirement with high volatility is a risk to the team's capacity: they build it, and then it changes again.

### What we built

**Four prioritization methods matched to context.** The skill supports MoSCoW (fast, easy for stakeholders to understand), WSJF (numeric ranking that accounts for cost and time-criticality, better for Agile), the Impact/Effort Matrix (visual, convenient for workshops), and Time Boxing/Budgeting (a fixed capacity or budget decides the scope — the answer to "everything is a Must"). Choosing a method isn't a gut call: the skill asks about the context and recommends one.

**Session-based score collection.** `start_prioritization_session` opens a session and builds the list of requirements to score. `add_stakeholder_scores` collects scores one stakeholder at a time. This lets scoring happen asynchronously: each stakeholder submits scores whenever it's convenient, and the BA aggregates everything with a single command.

**Automatic aggregation and conflict detection.** `run_aggregation` aggregates scores using stakeholder influence weights (from the 4.2 registry) and automatically flags: dependency violations (a requirement prioritized above something it depends on, which is impossible), conflicts between stakeholders (a wide spread of scores), and volatile requirements with high priority. Each conflict is logged as a separate record with a type and participants.

**Structured conflict resolution.** `resolve_conflict` records how each conflict was resolved: the method (escalation, compromise, expert judgment, pilot test), the participants, the final decision, and the rationale. This isn't just "we talked it over": it's a documented record that protects the BA.

**Results flow into the repository.** `save_prioritization_result` updates the priority attributes in the 5.2 repository for every requirement and saves a Markdown session report: the method, participants, final priorities, resolved conflicts, and rationale. This document is meant for stakeholders.

### Value for the BA

**Prioritization becomes defensible, not intuitive.** When the customer asks a month later, "why didn't FR-019 make it into the first release?", the BA opens the prioritization session report: here are the stakeholder scores, here's the weighted aggregation, here's the decision. It's a conversation backed by data, not by memory.

**Conflicts surface before development.** A dependency violation between FR-019 and FR-020, caught during aggregation, takes the BA a few minutes to fix. The same conflict, discovered mid-sprint, means reworking the plan and explaining it to the team.

**Stakeholders are engaged asynchronously.** The BA doesn't need to get everyone into the same two-hour workshop (and doesn't have to fight with directors' calendars). Scores are collected separately from each person, and aggregation happens afterward. For a large number of stakeholders, this is a substantial time saver.

**Unstable requirements don't slip into Must unnoticed.** The volatility flag in `run_aggregation` doesn't stop the BA from assigning high priority to an unstable requirement, but it forces that choice to be made consciously, with the risk understood.

### How to use it: an example

The elicitation stage has wrapped up, and the BA is ready for the first prioritization session. 45 requirements, 4 stakeholders with different influence weights.

*"Open a prioritization session for the CRM project. MoSCoW method, we'll score all 45 confirmed requirements."*

AInalyst opens the session and builds the list. The BA runs scoring with each stakeholder separately and enters the results via `add_stakeholder_scores`. After the fourth stakeholder:

*"Aggregate the results."*

`run_aggregation` returns: 3 conflicts (FR-007, a wide spread between sales and IT), 1 dependency violation (FR-031 in Must, but it depends on FR-044 in Could), 2 volatile requirements in Must. The BA resolves the conflicts, fixes the obvious dependency violation, and saves the result.

*"Save the session results."* The stakeholder report is ready.

---

## Task 5.4: Assess Requirements Changes (Requirements Change Assessment)

### Summary

The BA plays the role of "change gatekeeper": systematically assessing every Change Request, calculating its impact on the requirements graph, scoring it against a formula of business and technical axes, and preparing a well-reasoned recommendation for the sponsor or CCB. The decision itself isn't the BA's to make; the BA prepares the evidence-based material the decision gets made on.

### BA pain points

**Changes get accepted under pressure, not through analysis.** The project manager shows up: "the customer wants this feature added, let's just do it quickly." The BA says okay. A week later it turns out the feature conflicts with two existing requirements, drags along an architecture rework, and the customer had no idea about that cost when they asked for it.

**Nobody calculates the "cost" of a change systematically.** Impact analysis is done by hand, if it's done at all. The BA walks through related requirements from memory and inevitably misses something. The result: the CR gets accepted, and the affected artifacts only surface once development is underway.

**Every CR raises the question: "does this conflict with something we already decided?"** A change to FR-017 might conflict with a decision recorded in meeting minutes from three weeks ago. The BA can't remember every decision made on the project, and there's no time to dig through the archive.

**There's no single place for the history of all CRs.** One CR lives in an email, another in Jira, a third was just agreed verbally. A month later it's impossible to reconstruct: how many CRs were accepted? Which requirements are currently under change? What's still promised but not yet delivered?

**The "accept or not" decision has no structure.** The BA gives a recommendation on gut feel or under pressure. Without scoring against business axes and technical impact, that's not a recommendation, it's an opinion. The sponsor ends up deciding without data.

### What we built

**A staged pipeline for every CR.** `open_cr` → `run_cr_impact` → `score_cr` → `resolve_cr`. This isn't unnecessary formality: each step adds data the next one needs. For a small CR the cycle moves fast; for a large one, it delivers the full picture.

**A CR as a node in the traceability graph.** Every Change Request is stored in the 5.1 repository as a node with type `change_request`, linked to the affected requirements through a `modifies` relationship. The entire change history is visible right in the traceability matrix; there's no need for a separate CR register.

**Automatic impact analysis.** `run_cr_impact` uses the traceability graph from 5.1 (a BFS traversal) and returns a full list of affected artifacts: requirements, test cases, components. This is the technical input for scoring; the BA won't miss anything that gets "dragged along" by the change.

**Formula-based scoring with rationale.** `score_cr` calculates: `Score = Benefit×2 + Urgency×1.5 + Impact×1 - Cost×1.5 - ScheduleRisk×1`. The technical axes (Impact, ScheduleRisk) are computed automatically from the BFS traversal. The business axes (Benefit, Cost, Urgency) are entered by the BA after consulting the customer. The formula produces a preliminary verdict (Approve / Modify / Defer / Reject), and AInalyst adds a written rationale.

**Automatic status updates on resolution.** When `resolve_cr` is called with an Approved decision, it automatically moves the affected requirements into `under_change` status. The BA never forgets to update the registry by hand. The CR Decision Record is saved and flows into 4.4 (stakeholder communication) and into 5.5 (as context for approval).

### Value for the BA

**A recommendation backed by data, not opinion.** The BA doesn't go to the sponsor with "I think we should accept this," but with: 7 artifacts technically affected, a score of 6.5 (Modify), and here's what needs to change to reduce risk. The decision gets made with a clear understanding of the consequences, and accountability lands where it should.

**The history of every CR in one place.** `open_cr` with a unique ID, relationships in the traceability graph, Decision Records: together they form a complete audit trail. Three months later: how many CRs were there? Which were accepted, which rejected? Why? The answer is immediate.

**Changes don't "fly into development" unassessed.** The pipeline's mandatory impact analysis creates a checkpoint: before recommending a CR for acceptance, the BA understands what it drags along. This cuts down on surprises during development, one of the leading causes of delay.

**The BA is protected against scope creep.** When the manager is surprised two months later that "we added so much," the BA opens the CR register: here are the 12 accepted changes, here are the dates, here are the Decision Records signed off by the sponsor. This is professional documentation of scope creep, not an appeal to memory.

### How to use it: an example

A request comes in: the customer wants to add integration with a new CRM system that was never mentioned at the start.

*"Open a Change Request: the customer is asking to add Salesforce integration. It affects FR-022, FR-033, and probably something else too."*

`open_cr` creates CR-008. `run_cr_impact` runs through the traceability graph, and it turns out NFR-004 (API performance) and 3 test cases are also affected. The BA records the business-axis scores after talking with the customer, then runs the scoring. The score comes out to 4.2, "Modify": accept, but with adjusted timeline conditions. The BA prepares a recommendation for the sponsor, who makes the decision, and `resolve_cr` updates all the statuses.

---

## Task 5.5: Approve Requirements (Requirements Approval)

### Summary

The BA organizes formal sign-off of requirements with stakeholders and creates the Requirements Baseline: a fixed version of the requirements that becomes the contract for development. This task supports both the Predictive approach (a baseline at the end of a phase) and Agile (a Sprint Backlog Baseline).

### BA pain points

**"Approved" means something different to everyone.** Someone nodded in a meeting, someone wrote "ok" in an email, someone never responded at all, and the BA counts all of it as approval anyway. Then a developer shows up: "nobody told me FR-019 was approved, I was waiting for official confirmation." Or a stakeholder: "I never signed off on anything, how could you have started building this?"

**Conditional approvals get lost.** A stakeholder gives conditional approval: "I accept this, but only if you add a security section." The BA notes it privately and promises to follow up. The condition is fulfilled a week later, but it's never closed out officially anywhere. A month later, the stakeholder asks: "did you add what we agreed on?"

**No clear picture of whether the package is ready for baseline.** The BA has collected responses from 5 stakeholders. Three approved, one approved with a condition, one rejected. Is it time to create the baseline? Who's Accountable and who's just Consulted? Does a rejection from a Consulted stakeholder block anything?

**Different audiences need different package formats.** The business customer needs one thing, developers need another, the regulator needs a third. The BA prepares a single "one size fits all" document, and none of the audiences gets what they actually need.

**There's no baseline to speak of.** Requirements are "approved" somewhere in an email thread, but there's no fixed version, no date, no list of who signed off. A month later, it's impossible to answer: "what exactly was in baseline v1.0?"

### What we built

**An approval package tailored to the audience.** `prepare_approval_package` gathers the requirements, adds the traceability matrix (5.1), priorities (5.3), and CR Decision Records (5.4), then formats the document for a specific audience: `business` (no technical detail), `developer` (with technical attributes and dependencies), `regulator` (with full traceability and change history).

**Recording every stakeholder decision.** `record_approval_decision` logs each participant's response: Approved, Conditional (with the condition text, deadline, and owner), Rejected (with a reason), or Abstained. Decisions can be recorded for the whole package or for individual requirements within it.

**Closing out conditional approvals.** `close_approval_condition` records the fulfillment of a condition: what was done, and the closing date. The requirement moves from `conditional_approved` to `approved`. The history of the condition is preserved.

**Baseline readiness measured by criteria, not gut feel.** `check_approval_status` counts how many responses are Approved / Conditional / Rejected / still outstanding. It flags overdue conditions and flags rejections from Accountable stakeholders (these are blockers). It gives a clear verdict: ready for baseline or not, and why.

**An official Requirements Baseline.** `create_requirements_baseline` creates a snapshot of the package in `{project}_approval_history.json`, updates requirement statuses in the 5.1 repository (to `approved`), and generates an Approval Record: a Markdown document with the version, date, and the list of who signed off. This artifact flows into 4.4 (communication) and becomes an input to Chapter 6.

**Support for Predictive and Agile.** In a Predictive project, the baseline is created at the end of a phase and includes every requirement from that stage. In Agile, before each sprint, the Product Owner signs off on a Sprint Backlog Baseline tied to a specific sprint number.

### Value for the BA

**"Approved" now has a precise meaning.** There's an Approval Record with a date, a baseline version, and a list of participants and their decisions. The "well, we discussed it in the meeting" situation is gone. There's a documented trail that protects the BA and gives developers confidence in the material.

**Conditional approvals don't get lost.** Every condition is recorded with a deadline and an owner. `check_approval_status` will surface overdue conditions, so the BA won't lose track of them amid other work. The baseline won't be created until the condition is closed, unless the BA deliberately uses the `force` flag.

**The BA knows exactly when it's time to create the baseline.** `check_approval_status` removes the uncertainty: 4 Approved, 1 Conditional with an open condition, 1 Rejected from a Consulted stakeholder (not a blocker). Verdict: the baseline can be created with a documented risk around the Consulted rejection. Or: no, an Accountable stakeholder hasn't approved, the conflict needs to be resolved first.

**Different stakeholders get the format they need.** The sales director reads the business version of the package, free of technical language. Developers get the version with dependencies and attributes. This cuts down on "what does this mean?" questions and speeds up the approval cycle.

**The baseline is a legally meaningful moment in the project.** After the baseline is created, requirements can only be changed through a formal CR (5.4). This isn't a restriction, it's protection for the BA against informal scope creep. "The customer wants to add..." Fine, let's open a CR.

### How to use it: an example

The elicitation phase is complete, all requirements have gone through 4.3 and been entered into 5.1. Time for the first approval session.

*"Prepare the approval package for the CRM project. Predictive approach, requirements FR-001 through FR-045. For a business audience, this is going to the sales director and the CFO."*

`prepare_approval_package` assembles package APKG-001. The BA sends the document out through 4.4. Responses come in:

*"Sales director: approved everything. CFO: accepted, with one condition: FR-037 (the SAP integration) must pass a security review before development starts. Technical director: abstained."*

The BA records each decision via `record_approval_decision`. `check_approval_status` returns: 1 Approved, 1 Conditional (deadline in 2 weeks), 1 Abstained. Verdict: not ready for baseline, the CFO's condition needs to be closed first.

Ten days later, the security review is complete. *"Close out the CFO's condition on FR-037: the security review is done, the report is attached."* `close_approval_condition` records the fulfillment.

*"Create baseline v1.0."* The Approval Record is saved, the requirements get `approved` status, and the project moves into Chapter 6.

---

## Final synthesis for Chapter 5

**Chapter 5 is the quality infrastructure for the entire project.** If Chapter 4 produces raw material, Chapter 5 gives that material structure, history, status, and official weight. Everything that happens in Chapters 6, 7, and 8 is built on the foundation laid in Chapter 5.

**Each task in Chapter 5 removes a specific class of risk:**
- 5.1 removes the risk of unpredictable change consequences
- 5.2 removes the risk of working with stale data
- 5.3 removes the risk of subjective prioritization and hidden conflicts
- 5.4 removes the risk of uncontrolled scope creep
- 5.5 removes the risk of disputed approvals and diffused accountability

**The BA's responsibility in Chapter 5** stays right where it should: analytical judgment (what level of traceability formality is needed?), facilitation (how do we resolve a priority conflict?), assessment (what's the business value of this CR?). The platform takes on the infrastructure: storage, versioning, aggregation, report generation, coverage checks.

**The practical result:** a BA who works through the platform's Chapter 5 arrives at the transition to Chapter 6 with a clear answer to "what exactly are we building?": an approved baseline, full traceability, a current registry, and the history of every change. This isn't bureaucracy for its own sake, it's the precondition for quality work in every stage that follows.
