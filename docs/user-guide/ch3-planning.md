# User Guide
## AI-powered Platform AInalyst
**Download:** https://github.com/chaussky/ainalyst.git

**LinkedIn:** https://www.linkedin.com/in/anatole-tchaoussky-82957a40b/

---

# Chapter 3: Business Analysis Planning and Monitoring

## Overview of Chapter 3

Chapter 3 of BABOK, "Business Analysis Planning and Monitoring," is the foundation the entire project is built on. This is where you find the answers to the questions that matter most before you start working with requirements: exactly how we work, with whom, under what rules, where we store everything we create, and how we know we're moving in the right direction.

Without Chapter 3, everything else turns into chaos: the BA doesn't understand why they're documenting things at all, stakeholders expect different outcomes, requirement changes get made with no control, and conflicts between participants go unnoticed until it's too late.

In practice, most BAs either skip this chapter or do it "from memory": intuitively, without writing anything down. This is exactly where the platform delivers the biggest relative gain: it structures what usually stays informal.

---

## Task 3.1: Plan BA Approach (Choosing an Approach)

### Summary

The BA determines the project's working methodology: Waterfall, Agile, or Hybrid. This is the first strategic decision, and it affects everything that follows: how requirements are elicited, how changes are approved, and how detailed the documentation needs to be.

### BA pain points

**"Always Agile, because that's what everyone says"** is probably the most common mistake. The BA picks a methodology by default without considering the specific project's characteristics. The result: a regulated fintech project runs with no documentation, while a small internal IT tool ends up with a monstrous Waterfall process and mountains of artifacts.

**No justification.** Even if the BA chose correctly, the decision is recorded nowhere. A month later the sponsor asks, "Why are we working this way?" and the BA can't answer with data.

**Regulatory context gets ignored.** Compliance requirements (banking regulation, GDPR, ISO) call for a certain level of formality. A purely Agile approach on such projects creates audit risk, and the BA simply doesn't think about it at the start.

**The methodology gets chosen once and forgotten.** Then, midway through the project, it turns out the approach doesn't fit the context, and the team is forced to restructure on the fly at great cost.

### What we built

**Approach selection matrix.** The platform analyzes two parameters: the expected frequency of requirement changes and the level of uncertainty. Based on their combination (a 9-cell matrix), it recommends one of the three approaches along with a set of BABOK techniques.

**Regulatory override.** If the project has regulatory requirements, the platform automatically adjusts the recommendation: pure Agile turns into Hybrid with compliance gates. This guards against a methodology mistake in an audit context.

**Recording the decision with context.** The recommended approach, the parameters that led to it, and the BA's notes are all saved to `ba_plan.json`. This is a living artifact: it carries forward down the chain (into Task 5.5 for governance context).

**BABOK techniques for the approach.** The platform immediately recommends specific techniques that match the chosen methodology. The BA doesn't have to search for what to apply; they get a ready-made list.

### Value for the BA

- **Saves time and reduces cognitive load.** The methodology decision that a BA usually makes intuitively in 5 minutes (or copies from the last project) now surfaces through three questions and gets a structured rationale. The whole conversation takes 3 to 5 minutes with AInalyst.
- **A defensible position with stakeholders.** When the sponsor asks, "Why Hybrid and not Agile?" the BA opens the artifact and shows: here's the change frequency (High), here's the uncertainty (High), here's the regulatory context, and here's why it's Hybrid. The decision was made with data, not "because that's how it's done."
- **Insurance against methodology mistakes.** The platform won't let you just write "Agile" on a regulated project without explanation: the regulatory override raises the question automatically. This reduces the risk of an expensive methodology reversal midway through the project.
- **Consistency with the rest of the platform.** The chosen approach affects how other tasks behave: in Chapter 5, the level of governance formality will align with it; in Chapter 7, the approach to specification (User Stories vs. formal requirements) will follow the same decision.

### How to use it: an example

A BA starts a new project: an internal request portal for a bank's HR department.

They simply describe the situation to AInalyst:

> *"New project: an HR portal for a bank. Requirements are still fuzzy, HR doesn't know exactly what they want. Whether there are regulatory constraints is unclear, need to check with compliance."*

AInalyst asks two clarifying questions about change frequency and uncertainty. The BA answers. AInalyst recommends Hybrid with specific techniques and explains why. The BA says "agreed, save it," and the decision is recorded.

> The BA didn't pick parameters by hand, didn't open a spreadsheet, didn't have to memorize commands. They just described the context and got a well-reasoned decision.

### Optional step 3.1b: Plan BA Activities and Timing

BABOK 3.1 has two more elements beyond choosing an approach: which business analysis
activities will be performed (element .3), and when — in specific phases or iteratively
(element .4). This step is optional, and it's worth taking once the approach is settled:
call `plan_ba_activities` with the project ID. Leave the timing form unspecified and the
platform derives it from the chosen approach (Predictive → phases, Adaptive → iterations);
a plain Hybrid sits between the two on purpose, so the platform asks the BA to state the
form rather than guess it. Without any periods, the platform generates a starting skeleton
(two iterations or three stages, depending on the form) that the BA edits and re-runs.

Example call:

> *"Plan the BA activities for the HR portal project: two iterations, the first covers
> elicitation and current-state analysis with high effort, the second covers prioritization
> and specification with medium effort, planned for August and September."*

The result is saved into `ba_plan.json` and rendered in the report as a new
`## 3.1b BA Activities and Timing` section: the timing form and its source, a table of
periods (BABOK tasks, deliverables, effort, timing), and any timing constraints the BA
named (a regulatory deadline, vendor availability).

This isn't filed away either: Task 5.5 `prepare_approval_package` takes the methodology
straight from the planned timing form, so the BA no longer states Predictive/Agile a
second time when preparing an approval package. Task 4.1 `save_elicitation_plan` names the
work period that covers elicitation, with its planned effort, right in the session plan.

---

## Task 3.2: Plan Stakeholder Engagement (Stakeholder Map)

### Summary

The BA builds a registry of all project participants, determines their influence and interest, and assigns communication strategies and an engagement schedule. This is a "living document": it starts with one or two names and grows organically as the project moves forward.

### BA pain points

**The stakeholder registry is a "dead" document.** The BA creates a table at the start of the project, files it away, and never opens it again. Two months later it still has 4 outdated rows, even though there are really 12 stakeholders by now.

**The communication strategy lives in someone's head.** The BA remembers "write to James once a week, Rachel only on request," but nothing is written down. If the BA changes or gets sick, all of that information simply gets lost.

**Conflicts of interest go unnoticed in advance.** The BA doesn't realize two key stakeholders have opposing goals until an open conflict breaks out, and by then it's a matter of firefighting instead of managed facilitation.

**Blockers get discovered too late.** A stakeholder with high influence and a negative attitude toward the project is a manageable situation if you catch it at the start. If you catch it a week before sign-off, it's already a disaster.

**Nobody knows "who else to invite."** The BA talks to the people they already know. Every interview surfaces new participants, but nobody tracks the connections between them.

### What we built

**Power/Interest matrix with automatic classification.** The BA enters each stakeholder's influence and interest, and the platform automatically determines their quadrant (Key Players / Context Setters / Subjects / Crowd) and assigns a communication strategy with a recommended frequency.

**A living registry.** The registry isn't a static document. Task 4.2 (interview analysis) updates it via `update_stakeholder_registry`. Every time a stakeholder mentions a new participant, that person gets added to the registry with a note about the source.

**Blocker detection.** The platform automatically flags stakeholders with `attitude=Blocker` and lists them separately. This is a signal: this person needs special attention right now.

**Communication schedule.** The frequency and triggers for each stakeholder are recorded here and used by Task 4.4 to check who hasn't been contacted in a while and whose trigger has fired.

**Integration with Task 4.5.** A change in attitude (was Champion, became Neutral) is recorded via `update_engagement_status` with a history: what it was, what it became, and what's planned.

### Value for the BA

- **The stakeholder registry finally lives.** This is probably the hardest artifact to maintain in BA practice. The platform builds its update into the workflow: after every interview, AInalyst offers to add the participants who were mentioned. The registry grows organically instead of requiring a separate effort to "refresh the table."
- **Nothing gets lost when a project changes hands.** The new BA opens the registry and sees who's involved, how to treat them, when they last talked, and whether there were engagement issues. All the context that usually lives in one person's head is documented.
- **Early detection of engagement risk.** When James stops answering emails, it gets logged as a 🟡 signal, and the platform suggests possible reasons and tactics. The BA reacts proactively, before the problem becomes critical.
- **The communication schedule removes the nagging worry of "did I forget to write to someone."** Task 4.4 checks the schedule and produces a prioritized list of who to write to today. The BA doesn't have to keep it in their head.

### How to use it: an example

At the start of the project, the BA knows only two people. They tell AInalyst:

> *"Stakeholders: Patricia, CFO, very influential, very interested, supports the project. Michael, head of IT, high influence, medium interest, skeptical."*

AInalyst immediately determines: Patricia is a Key Player (Manage Closely, weekly), Michael is a Context Setter with a negative attitude (Keep Satisfied, needs special attention). The registry is saved.

A week later, during an interview, Patricia mentions Diane, the chief accountant, who also works with the system. The BA tells AInalyst:

> *"Patricia mentioned Diane, the chief accountant, who also uses the system."*

And Diane gets added to the registry with a note about the source.

---

## Task 3.3: Plan BA Governance (Decision-Making Rules)

### Summary

The BA sets the "rules of the game" for the project: who makes the final decisions on requirements, how change requests get handled, how conflicts get resolved, and where to escalate if something goes wrong.

### BA pain points

**"Who actually makes decisions here?"** is the question a BA ends up asking midway through the project, when the first serious CR lands. It turns out the Product Owner has no authority, the sponsor has no time, and the developers have already started doing things their own way.

**Scope creep with no governance.** Without a documented CR process, every stakeholder wish turns into a requirement. The BA can't say "no" without a formal procedure. As a result, scope creeps, the team gets frustrated, and deadlines slip.

**"Remember, we agreed that..."** Undocumented agreements create fertile ground for conflict. Three months later, everyone remembers it differently, and the BA has no document to point to.

**Different projects need different levels of formality.** A small internal project and a mission-critical system for 500 users need very different processes. The BA applies the same template to everything, either excessively formal or riskily light.

### What we built

**Governance templates by criticality level.** The platform offers three levels (High/Medium/Low) with ready-made processes: change control, who approves, the review cycle, the escalation chain. The BA doesn't build it from scratch; they pick the right template and adapt it to the specifics.

**Recording decision-makers.** It's explicitly recorded who signs off on requirements and CRs. This feeds directly into Task 5.4 (assess CR): the Decision Record goes to that specific person, not an abstract "sponsor."

**Planning how requirements will be prioritized.** Who takes part, by which technique, against which criteria. Task 5.3 then runs the session and reconciles it against the plan.

**Chapter 5 actually reads this section.** Task 3.3 is not a reference document the BA re-applies from memory. The approval package in Task 5.5 prints the planned approvers and the response deadline; Task 5.5 and Task 5.4 both check whether the person who recorded a decision is one of the planned decision-makers; Task 5.4 carries the escalation path into the CR Decision Record; Task 5.3 checks the session's technique and its participants and reconciles participation in the result report. The project criticality also supplies the default traceability level for Task 3.4.

**Everything read from the plan is a cross-check or a default, never an override.** If Task 5.3 runs with a different technique than the one planned, the session keeps the technique the BA chose and says the plan disagrees. The same holds everywhere: the platform reports the difference, and the BA decides which of the two is out of date. Decisions stay with the analyst.

**Plan roles; the platform recognizes people.** Task 3.3 records roles ("Product Owner"), but a CR is resolved by a person and a requirement is approved by a person. The stakeholder registry (built in Task 3.2 and kept up to date through Chapter 4) is what ties a name to a role, so "John Smith approved it" is recognized as the planned Product Owner. Without a registry the platform stays quiet instead of reporting a name it cannot match as a breach of governance — one more reason to do Task 3.2 before the Chapter 5 work.

**Governance decision archive.** Everything recorded in Task 3.3 lives in `ba_plan.json` and is available at any time. To the question "how did we agree to handle changes?" the answer is in a single file.

### Value for the BA

- **The BA gets "cover" for saying no.** When yet another change request shows up, the BA can say: "Under our process, this is a CR that needs to be submitted in this format and approved by James." That's not a refusal, it's a process. Professional scope protection.
- **The first CR doesn't turn into a crisis.** If governance isn't documented, the first serious change request causes chaos: nobody knows who decides, how to assess impact, or whether already-completed work needs to be redone. When governance is in place, it's just a routine procedure.
- **The level of formality matches the context.** A small internal tool doesn't get buried in bureaucracy. A mission-critical system gets the right level of control. The platform helps find that balance instead of forcing a single standard.
- **The rules don't quietly go stale.** A plan nobody reads drifts away from the project within a month, and nobody notices until an audit. Here, the moment a CR is resolved by someone outside the planned authority or a prioritization session runs with a different technique, the BA sees it — in the delivered document, not in a JSON file.

### How to use it: an example

The BA says:

> *"This is a critical project: an order management system for 300 users. Decisions are made by Victor (CEO), Susan (Product Owner), and me as Lead BA."*

AInalyst suggests the High-criticality template: a formal CR process with a CAB, weekly review, and escalation from BA to PM to Steering Committee. The BA can accept it as-is or adjust it. One phrase saves it.

---

## Task 3.4: Plan Information Management

### Summary

The BA determines where and how project requirements and artifacts are stored, who has access, and how detailed the traceability needs to be. This is a kind of "architectural" agreement, and it affects how easy Chapter 5 work will be later on.

### BA pain points

**Requirements are "everywhere and nowhere."** Some live in Confluence, some in email, some in Jira, some in a developer's head. When you need to find the current version of a requirement, nobody knows where it is.

**Traceability done "however's convenient."** Nobody agreed in advance how detailed the link tracking should be. The BA ends up building a full graph from business goals to test cases, and the team doesn't understand why it's needed and doesn't maintain it.

**Access is unstructured.** Developers accidentally edit requirements. Stakeholders don't know where to find the current version. Everyone goes to the BA in person, and the BA becomes a bottleneck.

**Confluence is set up "later."** Integration with corporate systems gets postponed and, in the end, never happens. The BA duplicates artifacts by hand.

### What we built

**A traceability agreement with three levels.** Lite (sources only), Standard (FRs + test cases), Full (the complete chain from business goals to code). The BA picks a level once, and the platform maintains traceability accordingly throughout Chapter 5.

**A registry of storage tools.** It records where each type of artifact is stored. Not just "Confluence," but specifically: "Confluence: final specifications; Jira: tasks and CRs; local repository: the traceability JSON graph."

**Access rules.** It's explicitly recorded who reads, who edits, and who approves.

**Confluence integration.** Set up once via environment variables. After that, every requirement update in Task 5.2 automatically syncs to Confluence. The BA doesn't have to think about it anymore.

**Three more decisions that other chapters act on, not just record.** The BA can also plan the level of detail each audience gets, the scope and repository for reuse, and which requirement attributes this project maintains (Minimum / Standard / Full). These aren't filed away: Task 4.4 states the planned level of detail in every communication package it builds, and Task 5.2 ranks reuse candidates by the planned scope and audits exactly the planned attribute set. A project that skips this planning has nothing read from it: 4.4 stays silent about detail levels, and 5.2 starts its reuse search at `initiative` and audits `owner` only. (Two repairs that shipped with the feature do reach every project, plan or no plan: the health report's action list is numbered from 1 instead of opening at 2, and the reuse report no longer calls its ranking bonus a minimum.)

### Value for the BA

- **"Where's the current version?" is no longer a question.** There's one documented source of truth. Everyone knows where to look.
- **The traceability level is agreed on before work starts.** This prevents the mid-project conflict where the BA builds a full graph and the PM says "that's overkill," or the reverse, where auditors demand traceability that nobody kept.
- **Confluence stops being manual work.** If the integration is set up, a requirement update publishes automatically. The BA doesn't copy artifacts by hand between systems.

---

## Task 3.5: Evaluate BA Performance

### Summary

The BA assesses the current state of business analysis practice on the team or in the organization, identifies problem areas, and puts together a concrete improvement plan. This task is optional; it's needed when there are clear problems or when onboarding onto a new project.

### BA pain points

**Symptoms are visible, causes aren't.** "Developers keep asking clarifying questions" is a symptom. The cause might be insufficiently detailed requirements, missing acceptance criteria, or requirements changing mid-sprint. Without a structured view, the BA treats symptoms instead of causes.

**No metrics, no conversation.** The BA can't make the case for investing in practice improvements without data. "I feel like quality has improved" isn't an argument. "Defect Rate dropped from 15% to 5%" is.

**Standard problems have standard solutions, but you have to remember them.** The BA knows what to do about scope creep or missing templates, but that takes time and mental effort, especially when onboarding onto a new project.

### What we built

**A problem-to-recommendation library.** The BA describes problems in free form, and the platform matches them against a database of known situations and gives concrete recommendations. "Scope creep" leads to "Strengthen governance: formalize the CR process via Task 5.4." "No metrics" leads to a list of metrics with instructions on how to calculate them.

**Recording metrics with a baseline and a target.** Not just "improve," but "Defect Rate: from 15% to 5%." This is the basis for measuring improvement later.

**Links to other tasks.** The problems identified often call for strengthening specific platform tasks. The platform points to exactly where: "weak traceability leads to setting up Task 5.1," "scope creep leads to strengthening Task 5.4."

### Value for the BA

- **Structured onboarding onto a new project.** A BA joins a project with an existing team. They describe what they see: "no templates, slow approvals, weak traceability," and get an improvement plan with priorities and concrete steps.
- **A case to make to leadership.** "We need to introduce a formal CR process," backed by data on current losses and target metrics, is a completely different conversation with the sponsor than a bare request.
- **Personal reflection for an experienced BA.** Useful not just for onboarding, but also after a project wraps up: what worked, what didn't, what to improve next time.

---

## Final synthesis for Chapter 3

**The overall value of Chapter 3 for the BA is the shift from "I work on instinct" to "we have a foundation."** Chapter 3 artifacts don't just document the initial decisions; they get used throughout the entire project: the stakeholder registry keeps growing through the end of Chapter 4, governance operates in every Chapter 5 task, and the information architecture determines how Confluence receives its data.

**The BA's technical burden in Chapter 3 is minimal.** There's no need to memorize a single command. Just describe the project context, answer AInalyst's 2 to 3 clarifying questions, and say "save it." All the technical work, choosing parameters, creating the JSON, saving artifacts, is handled by AInalyst. The BA gets finished documents in `governance_plans/reports/`.
