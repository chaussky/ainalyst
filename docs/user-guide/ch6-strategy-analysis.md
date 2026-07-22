# User Guide
## AI-powered Platform AInalyst
**Download:** https://github.com/chaussky/ainalyst.git

**LinkedIn:** https://www.linkedin.com/in/anatole-tchaoussky-82957a40b/

---
# Chapter 6: Strategy Analysis

---

## Chapter 6 Overview

BABOK Chapter 6 (Strategy Analysis) is the bridge between "we know what is happening" and "we know what to do." If Chapter 4 provides raw material from interviews and workshops, and Chapter 5 structures and approves requirements, then Chapter 6 answers the strategic question: **why are we changing at all, where exactly are we heading, what stands in our way, and how exactly will we do it.**

The four tasks of Chapter 6 form a single analytical chain:

```
6.1 Current State  →  6.2 Future State
        ↓                          ↓
6.3 Assess Risks      →  6.4 Change Strategy
```

The outputs of this chain (business needs (BN-xxx), business goals (BG-xxx), risks (RK-xxx), and change strategy (SOL-xxx)) become the foundation for all subsequent work: Chapter 7 (requirements design) and Chapter 8 (solution evaluation).

**Why this chapter is often done poorly.** In practice, BAs frequently skip strategic analysis or treat it as a formality: they write a single page of "problem description" and jump straight to functional requirements. As a result, requirements end up floating in the air: no one can answer the question "why does the business need this?" Approval drags on, priorities are disputed, and by the time the project ends, it is unclear whether the intended goals were achieved.

**Project phase.** All of Chapter 6 runs in the `analysis` phase. If you have not switched the phase yet, ask AInalyst to do it, or run `python phase.py analysis`.

---

## Task 6.1: Analyze Current State

### Overview

The BA researches and documents how the organization operates **right now**: business processes, technology, structure, policies, external factors. The main goal is not to describe everything indiscriminately, but to identify the root causes of problems and formulate **business needs**: concrete, measurable justifications for change.

This is the starting point for everything that follows. Without it, you cannot describe the future state, cannot assess risks, cannot form a strategy, and cannot later measure the project's success.

### BA Pain Points

**"We describe symptoms, not causes."** The BA collects complaints: "it's slow," "it's inconvenient," "data gets lost." These are all symptoms. There may be a single root cause (for example, the lack of a unified database), but the BA never digs down to it. As a result, the solution is designed to address the symptoms, and six months later the problem resurfaces somewhere else.

**"The business need is framed as a solution."** A classic mistake: instead of "we are losing 30% of customers due to slow processing," they write "we need a CRM system." If the business need is already a solution, alternatives are never considered at all. The project follows a single path from the start, without analysis.

**"There are no numbers."** "The process is inefficient," "customers are unhappy," "there's a lot of manual work": these are all descriptions without metrics. Without baseline numbers, it will be impossible to prove the value of the change after it is implemented. And it is impossible to prioritize: how inefficient? How unhappy?

**"We analyze everything indiscriminately."** The BA tries to describe the entire organization, and three weeks later ends up with 80 pages of text that nobody reads. The analysis drags on, stakeholders lose interest, and real decisions never get made.

**"RCA is done as a formality."** "The fishbone diagram is drawn," box checked. But the real root cause was never established, because the facilitation was superficial. As a result, the solution ends up aimed at the wrong target.

### What We Built

**Scoping the analysis with smart defaults.** The first step is an explicit contract: exactly what to analyze, out of 8 possible elements (business needs, processes and capabilities, technology, org structure, policies and regulations, business architecture, assets, external factors). The platform proposes a default set depending on the initiative type: for `process_improvement`, that's processes, technology, and policies; for `new_system`, it's capabilities, technology, and architecture. The BA does not have to guess what to analyze: the platform provides a starting point.

**Structured data collection for each element.** For every element in scope, the platform asks specific questions and helps the BA structure the answers. The result is not a "stream of consciousness" but a concrete, measurable description with metrics, sources, and pain points.

**RCA: three techniques to choose from.** The platform supports three approaches to root cause analysis:
- **"Five Whys"**: for a single problem with a linear chain of causes. Fast, 15 to 30 minutes.
- **Ishikawa diagram (fishbone)**: when causes are multifactorial: People, Processes, Technology, Data.
- **Problem tree**: strategic analysis with consequences, useful when you need to convince the sponsor.

Regardless of which technique is chosen, the result is normalized into a single format, which matters for automatically linking it to business needs.

**Formulating and registering business needs.** After RCA, the platform helps formulate business needs using a strict template: what is wrong right now (with numbers), why it is happening (a link to the RCA), what happens if nothing changes (cost of inaction), and what we expect from the change. Each business need gets an identifier, BN-001, BN-002, and is automatically registered in the traceability repository (5.1) as the upstream node of the entire chain: `BN → BR → FR → TC`.

**Completeness check and final report.** Before wrapping up, the platform checks: whether every element in scope has been filled in, whether at least one RCA exists, and whether business needs are linked to root causes. The final report is saved to the `reports` folder in Markdown format, ready to send to stakeholders.

### Value for the BA

**Time saved on structuring.** BAs usually spend significant time not on the analysis itself, but on deciding what exactly to describe, in what format, and in how much detail. The platform removes that burden: scoping takes a five-minute conversation. After that, the BA answers specific questions for each element, thinking about content instead of structure.

**Protection against "treating symptoms."** RCA tools are built into the workflow, so the BA cannot "accidentally" skip cause analysis and jump straight to solutions. Once the root cause is explicitly documented and linked to a business need, every subsequent decision is checked against it. This reduces the risk of a costly reversal midway through development.

**A measurable justification for change.** Business needs backed by metrics speak the sponsor's language. Instead of "we need improvements," the BA shows up with "we are losing 2.4 million dollars per quarter due to manual request processing (RCA-001); with automation, we expect processing time to drop from 8 hours to 1.5 hours." That is a convincing case, not a request for resources.

**Traceability from day one.** The BN-xxx nodes created in 6.1 become the roots of the entire traceability tree. By the end of the project, it will be clear: this feature (FR-045) was built because business need BN-002 exists, which came from root cause RCA-001, confirmed by specific data. That is professional defensibility for every decision.

**A smooth transition into 6.2.** The data from 6.1 automatically becomes context for 6.2: business needs become the foundation for future-state goals, and current metrics become the baseline for KPIs. The BA does not start 6.2 from a blank page.

### How to Use It: An Example

Project: an internal contract approval system at a manufacturing company.

*"I need to analyze the current state for the contract-approval project. We have problems with the speed of contract approval. Initiative type: process improvement."*

The platform proposes a scope: business needs, processes and capabilities, technology, policies. The BA specifies the depth: standard. Next comes an iterative dialogue: AInalyst asks questions about each element, and the BA answers.

Once data collection wraps up: *"Run an RCA on the approval speed problem. I'll use Five Whys."*

The Five Whys dialogue reveals the root cause: the lack of a unified contract status registry forces every approver to check email and call colleagues.

*"Record the business need: speed up the approval cycle from the current 14 days to 3 days; the cost of delay is 180 thousand per month."*

BN-001 is registered. The final report is ready at `reports/6_1_current_state_contract-approval.md`.

**The BA did not memorize any commands.** Did not think about which tool to call. Just described the context: the platform guided the process.

---

## Task 6.2: Define Future State

### Overview

The BA describes the target state of the organization: how processes, technology, and structure should work **after** the change. The key outputs are SMART objectives with measurable KPIs, gap analysis (an explicit description of the gap between as-is and to-be), and an assessment of the change's potential value.

This is the task where the question "what exactly counts as project success" gets answered.

### BA Pain Points

**"Goals without metrics."** "Improve customer service," "increase efficiency," "reduce risk": these are intentions, not goals. They don't let you answer, at the end of the project, whether you achieved what you wanted. The sponsor can always say "well, we wanted more." The BA has no defense.

**"The future is described as a list of deliverables."** "We'll roll out a CRM, configure the integration, train the team": that's an implementation plan, not a description of the future state. The difference is critical: a future-state description answers "how will it work," not "what will we do."

**"Gap analysis is not done explicitly."** The BA understands the gap intuitively but never documents it in a structured way. As a result, task 6.4 has no basis for choosing a strategy: the BA either has to go back and redo the work, or make decisions "by feel."

**"Constraints surface too late."** Budget constraints, technical restrictions, regulatory boundaries: the BA learns about them midway through design, when part of the work is already done. Redesigning is expensive.

**"The value of the change is never assessed."** The BA knows things "will be better" but never tries to structure it: what types of benefits do we expect? How significant are they? This keeps the conversation with the sponsor abstract and reduces their willingness to allocate resources.

### What We Built

**"Past next to future": a UX pattern.** If 6.1 has been completed for the same project, whenever the BA describes each future-state element, the platform automatically shows the current state of that same element right next to it. The BA does not switch between documents; the contrast is visible right in the dialogue. This speeds up the work and reduces the risk that the "future" accidentally repeats the "current state."

**SMART validation of goals.** For every business goal, the platform checks: is there a measurable KPI, is there a baseline (what we're starting from), is there a deadline. A goal without a KPI is not a goal; the platform flags this and suggests an improvement. Each business goal gets a BG-xxx identifier and is registered in the traceability repository.

**Explicit gap analysis as a separate artifact.** Gap analysis is not a "step that's just implied"; it's a separate tool with its own artifact (`{project}_gap_analysis.json`). For every gap, the platform records: the type of change (new / improvement / elimination / replacement) and the degree of complexity. This file is a required input for task 6.4.

**A structured constraints registry.** Budget, timelines, technical restrictions, regulatory boundaries: every constraint gets a type, a description, and a status: assumed or confirmed. The platform explicitly flags assumed constraints as needing validation ("this might not actually be a constraint, just a habit").

**Assessment of potential value.** A structured list of expected benefits with types (financial, operational, strategic, human), a significance rating, and a confidence rating. This is not an accounting calculation; it is context for task 7.6, where a detailed value analysis will be performed.

### Value for the BA

**SMART goals as protection against overestimating success.** When, a year later, the sponsor says "well, we expected more," the BA pulls up BG-001: "the goal was to cut processing time from 14 to 3 days. We reached 4 days, 97% of the goal." That is a conversation about data, not impressions. The platform makes goals defensible from the moment they are set.

**Gap analysis as time saved in task 6.4.** A BA who completed gap analysis in 6.2 does not start from zero when choosing a strategy in task 6.4. The platform automatically uses the gap artifact as input: here is what needs to change, here is the complexity of each change. Task 6.4 work is cut in half.

**Documenting constraints early means fewer do-overs.** Constraints documented in 6.2 become context for design in Chapter 7. Instead of discovering a budget constraint while evaluating design options (7.5) and redoing work, the BA and the team work within known boundaries from the start.

**Connected to the rest of the platform.** The data from 6.2 feeds three later tasks: gap_analysis feeds 6.4 (strategy), business goals feed 7.3 (business context for requirements), and the value assessment feeds 7.6 (value analysis). The BA does the work once; the platform reuses the results.

### How to Use It: An Example

Continuing the contract-approval project. 6.1 is complete, BN-001 is on record.

*"Let's describe the future state for contract-approval. We want to cut the approval cycle from 14 to 3 days within 6 months."*

The platform scopes the analysis using the same elements as in 6.1. For every element, it shows the current state right next to it: "right now: approval by email, manual notification, no unified status." The BA describes how it should be.

*"Record the goal: cut the average approval time from 14 to 3 business days by October 1."*

The AInalyst platform checks SMART: there's a metric, there's a baseline, there's a deadline. BG-001 is registered.

*"Run the gap analysis."*

Three key gaps: no unified status registry (HIGH, replacement), no automatic notifications (MEDIUM, new), approval requires an in-person signature (LOW, improvement).

*"Record the constraint: budget no more than 3 million dollars, timeline: 6 months."*

The report and gap_analysis.json are saved, ready to be used in 6.3 and 6.4.

---

## Task 6.3: Assess Risks

### Overview

The BA identifies threats to achieving business goals, assesses them by likelihood and impact, plans response measures, and forms a justified recommendation for the sponsor: proceed with the project, proceed with risk-mitigation conditions, or do not proceed.

### BA Pain Points

**"Risks are a formality."** The risk table exists because "that's how it's done." Nobody reads it, response measures are never carried out, risks are never updated. A ghost document that has no effect on decisions.

**"Risks are vaguely worded."** "Integration risk," "schedule risk," "budget risk": these are categories, not risks. A vague risk cannot be scored for likelihood, and no one can devise a concrete mitigation plan for it. When such a "risk" actually happens, everyone is surprised.

**"There is no link between risks and decisions."** The BA described the risks in one document and wrote the strategy in another. Nobody checked whether the chosen strategy reduces the top risks, or makes them worse. The link exists only in the BA's head, if it exists at all.

**"The sponsor doesn't know their own risk position."** The BA shows up with a risk matrix, and the sponsor asks "so what?" There has been no conversation about risk tolerance, which means there are no criteria for evaluation: is a risk with a score of 15 fine, or a catastrophe? It depends on the organization's context.

**"The recommendation is just the BA's personal opinion."** "I think the risks are acceptable" is not a professional position. The sponsor may disagree, leaving the BA in a vulnerable spot. There are no objective criteria.

### What We Built

**Auto-importing draft risks from context.** If tasks 6.1 and 6.2 have been completed, the platform automatically scans the artifacts and proposes draft risks: from the root causes in 6.1, from the constraints and gaps in 6.2, and from problems stakeholders mentioned (4.2). The BA does not start from a blank page: they review the proposed list and add to it.

**The "If X, then Y" risk format.** The platform requires a clear statement: "If [trigger/condition], then [consequence]." For example: "If the legacy system's API does not support the required methods, then integration will take 6 weeks longer," instead of "integration risk." A statement like this can be scored, and a concrete mitigation plan can be built around it.

**A risk matrix with semi-quantitative scoring.** Every risk is scored on two axes: likelihood (1 to 5) and impact (1 to 5). The platform builds the matrix, classifies risks into Low / Medium / High zones, and generates a cumulative profile. This is not just a nice-looking table; it is the basis for the recommendation.

**An explicit risk-tolerance position.** Before building the matrix, the BA records the organization's tolerance_level and the High-risk threshold. Quick reference points: a bank or the public sector maps to risk_averse, a commercial company to neutral, a startup to risk_seeking. After that, a rating of "score 15 is High" carries concrete meaning for that specific organization.

**A deterministic recommendation with a narrative.** The logic for determining the recommendation type is algorithmic: no High risks maps to `proceed_despite_risk`; High risks with mitigation maps to `proceed_with_mitigation`; critical risks without mitigation maps to `do_not_proceed`. The platform adds specific text backed by numbers. The BA comes to the sponsor not with a personal opinion, but with a justified position.

**Integration with traceability.** When finalized, risks (RK-xxx) can be registered in the 5.1 repository with `threatens` links to business needs. This means that in task 5.4 (change management), it will be visible which risks threaten which business needs.

### Value for the BA

**From a "formal document" to a working decision-making tool.** A risk register built through the platform has a direct effect on 6.4: when comparing strategy options, each option is scored on which risks it reduces and which it makes worse. The risks from 6.3 literally feed into the strategy-selection matrix.

**A defensible recommendation for the sponsor.** When the sponsor asks "are you sure we should move forward?" the BA answers: "Of 11 identified risks, 2 are in the High zone. A mitigation plan has been developed for both. If the plans are carried out, the cumulative profile drops from 78 to 42. Recommendation: proceed_with_mitigation." That is concrete and defensible.

**Time saved through auto-import.** A BA who diligently completed 6.1 and 6.2 gets draft risks "for free": the platform scans the artifacts already created. Instead of thinking "what could go wrong?" from a blank page, the BA reviews the proposals and adds project-specific risks.

**Professional communication.** The 6.3 report is a document for the sponsor. It is written in plain language: the top 3 High risks, mitigation plans, the recommendation. The BA doesn't have to explain what a risk matrix is; they just hand over the document.

### How to Use It: An Example

*"Let's assess risks for the contract-approval project. Initiative type: process improvement. Standard analysis depth."*

The platform proposes a scope and, if the 6.1/6.2 artifacts are available, scans them. It proposes draft risks: "If the legacy approval system does not support API integration, then the module will need to be reworked. Add it?"

The BA confirms the relevant risks and adds specific ones: "Add a risk: If the key user (the director of legal affairs) does not accept the new process, then adoption will be under 40% and the goals will not be achieved."

*"Set the risk tolerance: commercial company, neutral position, High threshold: 15."*

*"Run the risk matrix."*

Result: 2 High risks (integration and user adoption), 4 Medium, 5 Low.

*"Generate the recommendation."*

Recommendation: `proceed_with_mitigation`. Narrative: "If the mitigations for RK-003 and RK-007 are carried out, the cumulative profile drops to an acceptable level. The key condition is to prototype the API in the first 2 weeks of the project."

---

## Task 6.4: Define Change Strategy

### Overview

The BA synthesizes everything accumulated in Chapter 6: builds the solution scope, assesses the organization's readiness for change, compares strategy options, and defines the transition plan: exactly how the change will be implemented, in one big step, in phases, or with a pilot first.

This is the culmination of strategy analysis and the starting point for Chapter 7.

### BA Pain Points

**"The strategy comes out of thin air."** "We decided to do it in three phases": where did that decision come from? There is no justification. If someone asks "why three phases and not two or five?" there is no answer. The decision was made in a meeting, by feel.

**"Scope creep starts immediately."** At the start of the project, there is no explicit document stating "what's in, what's out." The very first meetings start adding functionality, and nobody objects, because there are no documented boundaries. By the middle of the project, the scope has doubled.

**"Organizational readiness is never assessed."** The BA picks a big_bang strategy without accounting for the fact that the organization hasn't run a single major IT project in the last 5 years, has no internal expertise, and changes leadership every year. The project kicks off, and 3 months in, the team starts sabotaging it: a classic organizational readiness failure.

**"do_nothing is never considered."** "Why consider doing nothing, we've already decided to act?" is a common attitude. As a result, there is no explicit comparison of what happens if things are left as they are. This deprives the project of a clear justification in front of the board.

**"Transition states are never planned."** The BA described the end state but not the intermediate ones. As a result, every project phase is left hanging: there is no understanding of what should be working after phase 1, or what value it delivers right now, rather than only at the end.

### What We Built

**Auto-importing context from 6.1, 6.2, and 6.3.** When 6.4 is initialized, the platform reads the artifacts of the previous tasks: business needs BN-xxx, business goals BG-xxx, risks RK-xxx. The BA starts work with the context already filled in; there is no need to "remember what we did earlier." The 6.2 gap analysis is not auto-imported — record each capability's gap_severity in `define_solution_scope` (auto-import is on the backlog).

**An explicit solution scope with capability categorization.** Every capability (process, technology, data, people, org structure) that changes in the project is explicitly registered with a critical gap level (high / medium / low / none) and a link to the gap analysis from 6.2. What is **out** of scope is also explicitly documented: this is the first line of defense against scope creep.

**Organizational readiness assessment across 6 dimensions.** The platform assesses: leadership engagement, cultural readiness, resource availability, operational readiness, technical maturity, and the organization's track record with change. Each dimension gets a rating from 1 to 5 with a justification. The resulting readiness_score determines the verdict: ready / proceed_with_caution / not_ready. A low score is not a death sentence: it is a signal to add a "Phase 0" for organizational preparation.

**A strategic options registry that includes do_nothing.** The "do nothing" option (OPT-000) is added automatically and requires an explicit justification: what happens to the business needs if things are left as they are. This is not a formality; it is an argument for the board: "we considered the status quo, and here is why it's unacceptable." For every real option (big_bang / phased / pilot_first), the platform records the pros, the cons, the investment, and the link to the risks from 6.3.

**A weighted comparison matrix for the options.** The platform applies 6 weighted criteria: alignment with business goals (25%), risk reduction (20%), cost (20%), speed to first value (15%), alignment with readiness_score (10%), and feasibility (10%). The BA scores every option against every criterion, and the platform calculates the winner and generates a narrative: why this particular option won, with specific references to BG, RK, and readiness.

**Transition states with explicit value at every phase.** For every phase, the platform records: which capabilities are delivered, which gaps are closed, which risks remain, and, critically, **what standalone value the business gets at the end of that phase**. If a phase delivers no standalone value, that is a signal to rethink the phase breakdown.

### Value for the BA

**A justified strategy, not a decision "by feel."** When leadership asks "why phased and not big_bang?" the BA pulls up the comparison matrix: here is readiness_score = 2.8 (proceed_with_caution), here is risk RK-007 (technology, High), here is the "alignment with readiness" criterion: phased wins by a clear margin. The decision was made with data.

**Scope is locked in from the start.** An explicit list of capabilities in scope and an explicit "out of scope" list form a document you can point to. "Was this in the original scope? No, so it's a CR." The BA is protected from informal scope creep from day one.

**A realistic plan that won't fail on the human side.** Readiness assessment is a tool for preventing organizational failures, one of the leading causes of IT project failure. A BA who documented "leadership engagement = 2/5" ahead of time and added a Phase 0 for change management reduces that risk explicitly and proactively.

**Each phase as a mini-value.** Transition states with explicit value at every stage form the basis for managing expectations. After the first phase, the business has something working and useful. This sustains motivation, reduces the risk of the project being cancelled halfway through, and provides data to test hypotheses before full rollout.

**Strategy as a contract for all subsequent work.** `{project}_change_strategy.json` is the input for Chapter 7 (what to specify) and Chapter 8 (how to evaluate the outcome). A BA who did 6.4 well won't have to redo the requirements architecture midway through the project because the scope changed.

### How to Use It: An Example

*"Let's define the change strategy for contract-approval. Horizon: 6 months, Agile approach."*

The platform imports the context: BN-001, BG-001, the gap analysis (3 gaps), 2 High risks.

*"Define the solution scope: in scope: the contract status module, the automatic notification system, ERP integration. Out of scope: electronic signature (a separate project)."*

*"Assess the organization's readiness. Leadership engagement: 4 (the director personally initiated the project). Cultural readiness: 3 (the team is cautious about new things). Technology: 3 (the ERP is old but has an API). Change history: 2 (past projects have dragged on)."*

Readiness score: 3.1, `proceed_with_caution`.

*"Add the phased option: two phases, medium investment, integration risk reduced by a pilot in phase 1."*

*"Compare the options."*

Winner: phased. Narrative: "Given a readiness_score of 3.1 and the High integration risk (RK-003), a phased strategy is optimal: the first phase tests the technical risk and delivers value with limited investment."

*"Define the transition states. Phase 1 (3 months): status module plus notifications, closing the "no unified registry" gap. Value: the time to look up a contract's status drops from 2 hours to 5 minutes. Phase 2 (3 months): ERP integration, full automation. Value: goal BG-001 is achieved."*

The report and `contract-approval_change_strategy.json` are saved. The project is ready for Chapter 7.

---

## Chapter 6 Final Synthesis

**Chapter 6 is the analytical backbone of the entire project.** If Chapter 4 gives you "what stakeholders say" and Chapter 5 gives you "what we recorded as requirements," then Chapter 6 answers the question "why does this make sense, and how will we do it." Without it, requirements hang in the air with no strategic justification.

**Each task in Chapter 6 eliminates a specific class of risk:**

- 6.1 eliminates the risk of "treating symptoms": the root cause gets solved instead
- 6.2 eliminates the risk of "success being unmeasurable": SMART goals with KPIs provide a clear criterion
- 6.3 eliminates the risk of "mid-project surprises": top threats are identified in advance
- 6.4 eliminates the risk of "implementation failure": the strategy is justified and the scope is locked in

**The Chapter 6 artifact chain**, once you've gone through it fully, looks like this:

```
reports/
  6_1_current_state_{project}.md        ← as-is analysis, BN-xxx
  6_2_future_state_{project}.md         ← BG-xxx goals, gap analysis
  6_3_risk_assessment_{project}.md      ← RK-xxx register, recommendation
  6_4_change_strategy_{project}.md      ← SOL-xxx scope, strategy, phases
```

All four documents together form a professional strategy package, ready to present to the sponsor and hand off to Chapter 7.

**The BA's responsibility in Chapter 6** comes down to three things: providing context (describing what's happening in the organization right now), making the strategic decisions (where to draw the scope boundary, which option to choose, what the risk position is), and keeping the `analysis` phase active. Everything else (structuring, storage, report generation, traceability, context import between tasks) is handled by the platform.

**Practical outcome:** a BA who has gone through Chapter 6 using the platform arrives at Chapter 7 with a clear answer to "what exactly are we designing, and why." It's not just a list of requirements: it's a strategically justified position with measurable goals, known constraints, and a locked-in scope. A solid foundation for quality work at the next stage.
