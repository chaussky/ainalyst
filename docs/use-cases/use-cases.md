## AI-powered Platform AInalyst
**Download:** https://github.com/chaussky/ainalyst.git

**LinkedIn:** https://www.linkedin.com/in/anatole-tchaoussky-82957a40b/

---

# AInalyst Platform Use Cases
## Use Cases: possible scenarios of a business analyst's work on the Platform. Situations and names are fictional, any resemblance is coincidental

---

In the user guide we walked through the platform's capabilities through one continuous project. Here the approach is different: independent scenarios from different industries and different working situations. Each one shows a specific pain point and how the platform relieves it.

The contexts differ. The analysts differ. But the principle is the same: you describe the situation, the platform does the work.

---

## UC-01: When the analyst leaves the project

> **For:** Heads of business analysis departments, CTOs, PMs
> **Pain:** The key BA quit, went on leave, or got sick, and the entire project context disappeared with them
> **Features:** Stakeholder registry (3.2), Decision Log (4.5), traceability graph (5.1), CR history (5.4), approval statuses (5.5)

### Situation

It's month five of a project to implement an assortment management system at a large retail chain. The key business analyst, Anthony, the person who knows every stakeholder personally, remembers why FR-034 was dropped back in March, and keeps three unresolved approval conditions with the CFO in his head, suddenly resigns.

The project has: 14 stakeholders with different histories of engagement, 87 requirements in various statuses, 9 approved change requests, and a Steering Committee presentation in three weeks.

The head of the BA department is in a panic. The new analyst, Julia, starts on the project on Monday.

This is a typical situation that turns into a crisis at most companies: weeks spent "fighting the archives," interviewing people who "remember something," and trying to reconstruct context from email threads and chat history.

With AInalyst, this story looks different.

### What Julia does

She opens AInalyst, looks at the project folder, and types one line:

> **Julia:** I just started on the assortment-2026 project. The previous business analyst, Anthony, resigned. Tell me about the current state: stakeholders, open questions, unresolved approvals.

### How AInalyst responds

AInalyst reads all the project artifacts and produces a structured summary in a few seconds:

---

> **AInalyst:** Project assortment-2026, active phase: lifecycle. Here's the current context:
>
> **Stakeholders (14 people):**
> Karen Foster (CFO): Key Player, Manage Closely. Status: ⚠️ Concerned since March 28. Last interaction: April 3, an email that went unanswered. Needs attention.
> Michael Turner (IT Director): Context Setter. Status: ✅ Champion. Active.
> *(12 more participants with history and statuses)*
>
> **Open approval questions:**
> 3 conditional approvals are still open. One is overdue: the CFO's condition on FR-037 (security review) had a deadline of April 1.
>
> **Recent decisions from the Decision Log:**
> March 15: FR-034 moved to v2. Reason: high cost, low priority after prioritization. Decision made by Anthony together with the Product Owner.
> March 22: CR-008 (ERP integration) approved with a condition: implement asynchronously.
>
> Would you like me to show the full stakeholder registry, or should we jump straight to the unresolved approvals?

---

Julia continues:

> **Julia:** Show me the situation with the CFO in detail: why is she Concerned, and what's going on with the overdue condition?

---

> **AInalyst:** Karen Foster moved to Concerned status on March 28, after the CR-008 meeting. In the Decision Log: she raised security concerns about the ERP integration. Anthony promised a security review by April 1.
>
> CR-008 condition: "FR-037 must pass a security review before development of the integration module begins."
> Status: ⛔ Overdue. Owner: Anthony (resigned).
>
> Recommendation: write to Karen today, introduce yourself, explain the situation, and agree on a new deadline. Should I draft the email?

---

> **Julia:** Yes, draft it. And update the owner of this condition to me.

### What Julia gets

In 20 minutes she knows:

- Which stakeholders need immediate attention and why
- Why every key decision over the last two months was made
- What exactly needs to happen today so the presentation in three weeks doesn't fall apart
- The full history of every requirement: where it came from, how it changed, who approved it

Context that usually lives in one person's head and disappears with them is here captured, structured, and available to the new analyst from minute one.

### What happens under the hood

> *The business analyst doesn't work with this directly, AInalyst does it all automatically.*

On the first request, AInalyst pulls from several sources at once: it reads the stakeholder registry with its status change history (Chapter 3 MCP server, `planning_mcp`), retrieves the Decision Log with every recorded decision (Task 4.5 MCP server, `elicitation_collaborate_mcp`), and checks approval statuses and open conditions (Task 5.5 MCP server, `requirements_approve_mcp`). The traceability graph (Task 5.1 MCP server, `requirements_traceability_mcp`) lets it instantly answer, for any requirement, "where did this come from and what depends on it."

All this information accumulated in structured JSON files in the `governance_plans/data/` folder throughout the project, every time Anthony saved interview results, updated a stakeholder status, recorded a decision, or closed a CR. Automatically, as a side effect of routine work.

For Julia this means: she doesn't get a folder of documents that takes hours to read, she gets a living, structured project memory she can talk to right away.

---

## UC-02: Choosing a methodology: one feature, two completely different outcomes

> **For:** Business analysts at any level
> **Pain:** The methodology gets picked "by default," without analyzing context, risking a costly mistake
> **Features:** Approach selection matrix, regulatory override (Task 3.1)

### Situation

The same analyst. The same platform feature. Two projects, and fundamentally different outcomes. A good illustration of how the platform doesn't work off a template, it works off context.

**Project A:** An HR startup automating onboarding. A five-person team, the client doesn't yet know what they want, everything will change.

**Project B:** A credit risk assessment system at a bank. Requirements are formally defined. There are regulatory obligations to the central bank, with an audit in a year. The team wants Scrum: "that's how we always do it."

BA Paul opens AInalyst for each project.

### What Paul does: Project A

> **Paul:** New project. HR startup, we're automating employee onboarding. Small team, the client doesn't fully know what they want yet, requirements will definitely change.

### How AInalyst responds: Project A

---

> **AInalyst:** Two clarifying questions:
> 1. How often will requirements change: rarely, regularly, or constantly?
> 2. How high is the uncertainty about the end result right now?

> **Paul:** Constantly. Uncertainty is high.

> **AInalyst:** Recommendation: **Adaptive (Agile)**.
>
> Rationale: high frequency of change plus high uncertainty is a classic Agile context. Iterative cycles will let you test hypotheses without costly rework.
>
> Recommended BABOK techniques: User Stories, Story Mapping, Iterative Elicitation, Product Backlog Refinement.
>
> Save this decision?

---

### What Paul does: Project B

> **Paul:** New project. A bank, credit risk assessment system. Requirements are laid out in regulatory documents, the team wants Scrum. There are central bank regulatory requirements, and an audit in a year.

### How AInalyst responds: Project B

---

> **AInalyst:** ⚠️ Regulatory context detected.
>
> The team wants Scrum, I understand the logic. But in this context that creates a serious risk. Here's why:
>
> A central bank regulatory audit requires full traceability: every requirement must be documented, approved, and have proof of fulfillment. Plain Scrum doesn't provide for that: artifacts are kept to a minimum, and the change history isn't rigorous.
>
> **Recommendation: Hybrid (Predictive + Adaptive).**
>
> Predictive layer: requirement capture, traceability, compliance gates before every release, an audit trail.
> Adaptive layer: iterative development, sprints, stakeholder demos.
>
> This lets the team work in Scrum inside the iterations, while still passing the audit without a scramble.
>
> Save the decision and put together a BA plan with a compliance checklist?

---

### What Paul gets

In the first case: quick confirmation of the right intuitive call. In the second: protection from a mistake he might not have caught himself, one that would only have surfaced during the audit.

The platform doesn't just pick a methodology from parameters. It notices context that changes the rules, and explains why.

### What happens under the hood

> *The business analyst doesn't work with this directly, AInalyst does it all automatically.*

The `planning` phase MCP server (`planning_mcp`), when the `select_ba_approach` tool is called, analyzes the supplied parameters against the `APPROACH_MATRIX`: frequency of change, uncertainty, team size, time horizon. For Project B, a separate `REGULATORY_OVERRIDE` check fires: if regulatory oversight is detected in the context, the recommendation is automatically adjusted to Hybrid regardless of the other parameters. The result is saved to `ba_plan.json` as the project's official methodology decision.

---

## UC-03: A 90-minute interview becomes a structured artifact

> **For:** Business analysts working with interviews
> **Pain:** Hours of manual review after an interview, and something important still gets lost
> **Features:** Processing elicitation results (Task 4.2)

### Situation

An insurance company. BA Daniel conducted a 90-minute interview with the director of claims settlement. The transcript is a raw Zoom recording: interruptions, digressions, two places where the interviewee contradicts herself, and one place where she clearly contradicts something the IT director said a week earlier. The file sits in the `inputs/` folder.

Daniel could spend two hours reviewing it by hand. Instead he writes one line.

### What Daniel does

> **Daniel:** Process the interview transcript with Helen Walsh from the file interview_helen_20260401.txt

### How AInalyst responds

---

> **AInalyst:** Processed the transcript (94 min, 8,400 words). Here's the result:
>
> **Candidate requirements (14):**
> FR candidate: The system should automatically calculate the payout deadline based on claim type. Source: "we spend 2 hours on every complex case just calculating deadlines" (min. 23).
> NFR candidate: Response time when opening a claim record should be no more than 3 seconds. Source: "right now it takes 10-15 seconds to load, people go get coffee."
> *(12 more requirements)*
>
> **Business rules (3):**
> Category A claims (over 500K dollars) must go through senior expert review before payout.
>
> **Metrics:**
> Target processing time for a standard claim: 4 business days (currently 9).
>
> **Gaps, need clarification (2):**
> Unclear: who has the authority to manually override the automatic deadline calculation?
> Unclear: how should the system handle claims on foreign policies?
>
> **Contradiction ⚠️:**
> Helen says: "the tax authority database integration is urgent, it's blocking our work." The IT director (interview from March 25): "the tax authority integration is next year, there's no capacity right now." Needs resolution.

> **Daniel:** Helen mentioned someone named Max from IT support, add him to the stakeholder registry.

> **AInalyst:** Added. Max (last name not mentioned): IT support, specific role not yet determined. Source: interview with Walsh, April 1, 2026, min. 47. Recommend confirming his last name and role at the next contact.

---

### What Daniel gets

Instead of two hours of manual review, a structured artifact in minutes. Every requirement is captured, the key metric wasn't lost, and the gaps and the contradiction are visible right away, while Helen still remembers the conversation and can easily answer a follow-up.

Max, whom Daniel "caught out of the corner of his ear," is now in the stakeholder registry with a note on where he came from.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

AInalyst reads the file from `inputs/` and passes it to the Task 4.2 MCP server (`elicitation_conduct_mcp`). The `process_elicitation_results` tool analyzes the text and returns a structured set: candidate requirements by type, business rules, metrics, gaps, contradictions. If new names are found in the text, it suggests calling `update_stakeholder_registry`, which adds the participant to `stakeholder_registry.json` with a note on the source. The resulting Markdown artifact is saved to `governance_plans/reports/` via `save_artifact` from `common.py`.

---

## UC-04: A stakeholder conflict nobody noticed

> **For:** Business analysts on projects with many stakeholders
> **Pain:** Two stakeholders want opposite things, and nobody notices until the approval stage
> **Features:** Cross-analysis of multiple elicitation sessions (Task 4.2)

### Situation

A manufacturing holding. The project: a unified production planning system. Over three weeks, BA Natalie conducted four interviews: the production director, the chief technologist, the head of supply chain, and the CFO. She processed each interview separately, got the requirements, saved the artifacts, and moved on.

Everything was fine until she asked the platform to compare the results.

### What Natalie does

> **Natalie:** Compare the results of the four interviews for the production-planning project. I want to understand where there are contradictions and where stakeholders agree.

### How AInalyst responds

---

> **AInalyst:** Analyzing the four elicitation artifacts...
>
> **Consensus, stakeholders agree:**
> All four consider visualizing production capacity utilization a priority
> Three of four want integration with SAP ERP
>
> **Conflict 🔴, requires resolution:**
> Speed vs. data accuracy.
> Production director (Bennett): "The main thing is replanning speed. We need data within 15 minutes, even if it's slightly stale."
> CFO (Reed): "We need 100% real-time accuracy for financial reporting. Speed is secondary."
>
> This is a fundamental architectural conflict: real-time vs. batch processing. Both requirements can't be satisfied without an explicit trade-off.
>
> **Gap, nobody clarified:**
> Who has the authority to manually adjust the plan? This is critical for the business rules.
>
> **Recommendation:** Hold a joint workshop with Bennett and Reed. There's no moving to architecture without a decision on data.
>
> Log the conflict as an open issue?

> **Natalie:** Yes. And suggest a workshop structure: what to discuss, in what order.

> **AInalyst:** Conflict logged. A 60-minute workshop structure:
>
> **Block 1 (15 min):** Show both requirements side by side on screen. Ask each person to state: what exactly breaks if we adopt the other side's requirement?
>
> **Block 2 (20 min):** Walk through three options: (1) real-time for everyone, (2) batch for everyone, (3) split streams, the finance module gets real-time, production gets 15-minute updates.
>
> **Block 3 (25 min):** Choose an option and record the decision.
>
> Your role is facilitator, not arbiter. You structure the conversation, they make the decision.

---

### What Natalie gets

A conflict that could have surfaced at the requirements approval stage (and demanded rework of already-finished artifacts) is caught now, while it's still easy to resolve with a single workshop. There's a concrete action plan.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 4.2 MCP server (`elicitation_conduct_mcp`), when `compare_elicitation_results` is called, reads the saved artifacts across all the specified elicitation sessions. For each topic, the tool compares what each stakeholder said, looking for direct contradictions and areas of consensus. A detected conflict can be passed straight to Task 4.5 (`elicitation_collaborate_mcp`), logged in the Decision Log as an open issue requiring resolution through a workshop or escalation.

---

## UC-05: The stakeholder quietly sabotaging the project

> **For:** Business analysts working in organizations with a complex political environment
> **Pain:** Something is clearly wrong, but it's not clear what, or how to respond professionally
> **Features:** Engagement signal diagnostics, status change history (Task 4.5)

### Situation

A government organization. A document archive digitization project. BA Steven has been on it for three months.

The deputy IT director, David, was initially one of the biggest supporters: he helped organize interviews, proposed ideas himself, showed up to every meeting. In the stakeholder registry: Champion status.

Three weeks ago something changed. David replies to emails after 3-4 days, briefly. He was silent through the entire last meeting. And yesterday the director wrote to Steven: "David sent me a list of project risks. Let's discuss."

Steven is confused and doesn't know how to interpret what's happening.

### What Steven does

> **Steven:** David used to actively support the project. For the last three weeks: he doesn't answer emails, stays silent in meetings, and yesterday wrote to the director going around me with a list of risks. What's going on and what should I do?

### How AInalyst responds

---

> **AInalyst:** Signal 🟡, requires a proactive response. This is a pattern of passive resistance. Three most likely causes:
>
> **Option 1: David doesn't feel heard.**
> He agrees publicly because disagreeing feels awkward in his role. He influences privately through the director, the only channel available to him. Tactic: a 1-on-1 meeting with no agenda. "I sense you have concerns. I want to hear them directly."
>
> **Option 2: Specific technical concerns that are awkward to raise publicly.**
> He may understand something about the architecture or integration that others don't see. He stays silent in meetings because the audience isn't technical. Tactic: the same 1-on-1, with a specific ask: "Tell me more about the risks you described to the director."
>
> **Option 3: A shift in leadership positioning or personal interests.**
> Something changed in the organizational context: new priorities, a threat to budget or to David's authority. Tactic: carefully probe through indirect sources before meeting directly.
>
> Which option seems most likely to you?

> **Steven:** Probably option 2, he definitely has technical knowledge the rest of us don't. I'll go through a 1-on-1. Update his registry status: was Champion, now Concerned. I've scheduled a meeting for Friday.

> **AInalyst:** Updated. History:
> Champion (since January 2026) → Concerned (April 14, 2026).
> Reason: passive resistance, going to the director around the BA.
> Planned action: 1-on-1 meeting on Friday, April 18.
>
> Come back after the meeting, we'll update the status and log what you learn.

---

### What Steven gets

Instead of a nagging "something's wrong, I don't know what," a concrete diagnosis with three hypotheses and tactics for each. A specific next step.

And importantly: the status change history is recorded. If Steven goes on leave or leaves the project, the next analyst will open the registry and see this whole history. No need to explain "why David suddenly became a problem."

### What happens under the hood

> *The business analyst doesn't work with this directly, AInalyst does it all automatically.*

AInalyst passes the situation description to the Task 4.5 MCP server (`elicitation_collaborate_mcp`). The `diagnose_engagement_signal` tool analyzes the behavior pattern and returns a signal classification, likely causes, and tactics. Once the BA has made a decision, `update_engagement_status` updates the record in `stakeholder_registry.json`, not just changing the current status but preserving the full history with date, reason, and planned action. This history accumulates over the life of the project and is available to any team member, including a new analyst who comes in as a replacement.

---

## UC-06: Joining a project already in progress

> **For:** Business analysts starting to work with the platform mid-project
> **Pain:** A lot of work has already happened without AInalyst: interviews conducted, requirements collected, correspondence piled up. Starting over isn't realistic. But continuing to work without structure is a risk.
> **Features:** Project initialization from existing materials, requirement import from Confluence, flexible phase switching

### Situation

A financial company. A credit underwriting process automation project has been running for three months. BA Kevin just joined the team, the previous analyst moved to another project.

A lot has piled up: a Confluence page with 60 requirements, four interview transcripts in a shared folder, several email threads with stakeholders, an informal priority table in Excel. All of it exists scattered, no unified structure, no traceability, no decision history.

Starting from scratch and re-asking stakeholders about things already discussed would mean losing their trust. But moving forward while keeping everything in different places is a risk too.

Kevin decides to plug AInalyst into the live project right now.

### What Kevin does

He starts the `planning` phase and begins not with a "new project," but by describing what's already there:

> **Kevin:** I need to connect the platform to a project that's already underway. The project is called credit-underwriting-2026. It's been running three months, I just joined. Requirements are collected on a Confluence page called "Underwriting / System Requirements." I know six stakeholders: Peters (business owner), Grant (IT architect), Sheridan (compliance), and three more business analysts. Four interviews have been done, transcripts are in inputs/.

### How AInalyst responds

---

> **AInalyst:** Got it, initializing the project from the existing materials.
>
> **Step 1: Creating the project structure.**
> Project credit-underwriting-2026 registered. Active phase: planning.
>
> **Step 2: Adding stakeholders.**
> Added all six. Peters: provisionally Key Player (confirm influence/interest when you can). Statuses set to Unknown, update after you've met them.
>
> **Step 3: Pulling requirements from Confluence.**
> Reading the page "Underwriting / System Requirements"...
> Found: 58 requirements. Structure is inconsistent, some are User Stories, some are free text, 7 lines have no explicit identifier.
>
> What would you like to do?
> (A) Import as-is and verify quality afterward
> (B) Normalize the format on import, will take a bit longer
> (C) Show me the first 10 first so I can decide

> **Kevin:** Let's go with option B, normalize on import.

> **AInalyst:** Normalizing... done.
> Imported 58 requirements: 51 correctly structured, 7 flagged as "needs clarification", incomplete wording, no acceptance criteria. I'll show you the list later.
>
> Recommended next step: switch to the `lifecycle` phase and run an initial traceability pass, linking requirements to each other and to the business objectives. For that I need to know: are the project's business objectives already recorded, or should we start drafting them together?

---

> **Kevin:** Objectives aren't recorded yet, but Peters mentioned cutting application review time from 5 days to 2. That's the main goal.

> **AInalyst:** Recording business objective: BG-001, "Reduce credit application review time from 5 to 2 business days by Q3 2026."
>
> Now let's see which of the 58 requirements serve this objective and which might be out of scope. It'll take a couple of minutes, want me to run it?

---

### What Kevin gets

In one working session, not starting from zero, but picking up exactly where the previous analyst left off:

- All the Confluence requirements in a structured repository with identifiers
- A stakeholder registry with a placeholder ready for status updates
- A first formulated business objective
- An understanding of which requirements look suspicious and need attention

The platform doesn't force you to start over. It plugs into what's already there.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

When initializing an existing project, AInalyst uses the `planning` phase MCP server (`planning_mcp`) to build the basic structure: registers the project, creates the stakeholder registry with the supplied names. To read Confluence it uses the built-in Confluence MCP server, which reads the page directly by title and passes the content along for processing. Requirement normalization runs through `requirements_traceability_mcp` (Task 5.1): each requirement gets an identifier, the structure is brought to a common format, and problematic entries are flagged. The transcripts in `inputs/` can be processed at any point through the `elicitation` phase, without switching to it right away, the phase order is flexible.

---

## UC-07: When there's no business analyst on the project

> **For:** Product managers, project managers, technical directors, and CTOs on projects without a dedicated BA
> **Pain:** Product understanding exists, but there's no methodological expertise, requirements are vague, stakeholders say different things, documentation is missing or outdated
> **Features:** Full BABOK methodology cycle guided by the platform, no need to know BABOK in advance

### Situation

A tech startup. The team is building a B2B SaaS product for managing corporate business travel. Eight people: three developers, a designer, a QA engineer, a CEO, and a CPO who is de facto the product manager.

CPO Alex understands the market and users well. But he has no experience with requirements methodology: requirements live in his head, in Notion as scattered notes, and in team chats. The architect has already rebuilt the booking module twice because "it turned out that wasn't what was meant."

Hiring a BA is expensive and premature. But continuing to work as they are means continuing to rebuild.

Alex decides to try AInalyst on his own.

### What Alex does

He doesn't prepare anything special and doesn't study BABOK. He just opens AInalyst and describes the situation in his own words:

> **Alex:** We're building a B2B SaaS for corporate business travel. I'm the CPO, we don't have a BA. I want to get our requirements in order, right now it's all in my head and in Notion. We keep rebuilding things because of misunderstandings. Where do I start?

### How AInalyst responds

---

> **AInalyst:** Good start, you've correctly diagnosed the problem. Here's a suggested route, briefly:
>
> 1. First, let's figure out who your stakeholders are and whose interests need to be considered, that'll take 15 minutes.
> 2. Then let's record the project's business objectives in measurable form, so it's clear what counts as success.
> 3. Then we'll move on to the requirements themselves, structuring what already exists and adding what's missing.
>
> Shall we start? Tell me: who pays for your product, and who uses it, are those different people?

> **Alex:** The company's HR director or CFO pays. It's used by the employees themselves who travel, and by travel coordinators who arrange everything.

> **AInalyst:** Good, you've got three different groups with potentially different needs. Let's go through each one. One more question: is there anyone on your team whose opinion of the product is critical, like a CTO or someone who's worked directly with clients?

---

*Twenty minutes into the conversation, AInalyst has built a map of 8 stakeholders with roles and preliminary statuses. Alex didn't know the term "stakeholder registry," now he has a structured artifact for BABOK Task 3.2.*

---

> **Alex:** Okay, stakeholders are clear. What's next?

> **AInalyst:** Now, objectives. You mentioned you keep rebuilding the booking module. Try to put it this way: what should change in your product or process in six months for you to say "we did this right"?

> **Alex:** Well... travel coordinators stop calling us with questions every day. And developers stop rebuilding the same thing twice.

> **AInalyst:** Good, those are two different objectives, let's make them measurable:

> BG-001 (draft): "Reduce travel coordinator support inquiries by 70% by Q3 2026."
> BG-002 (draft): "Cut the percentage of tasks sent back for rework due to unclear requirements from the current level to under 10%."
>
> How do these read to you? If the numbers aren't right, say so and we'll adjust.

---

From there, AInalyst walks Alex step by step through structuring the requirements, suggesting they record what's already built and what's planned, asking clarifying questions wherever the wording is vague, and pointing out contradictions between what's written in Notion and what Alex describes verbally.

### What Alex gets

After a few working sessions, no consultants, no BABOK courses, no new hire:

- A stakeholder registry with roles and priorities
- Formulated and validated business objectives
- A structured requirements repository with traceability
- An understanding of why specific requirements conflict with each other, and how to resolve it

Methodology here became the platform's job, not his. Alex brought knowledge of the product and the market. The rest, process, structure, artifacts, AInalyst took on itself.

### What happens under the hood

> *The user doesn't work with this directly, the Platform does it all automatically.*

AInalyst adapts its questions and explanations for a non-technical audience: BABOK terminology isn't used in the conversation, but the methodology is followed fully. Under the hood, the same tools are used as in a professional BA's work: `planning_mcp` builds the stakeholder registry (Task 3.2), `future_state_mcp` validates business objectives against SMART criteria (Task 6.2), `requirements_traceability_mcp` initializes the repository and builds the traceability graph (Task 5.1). The only difference is that AInalyst takes on the role of methodologist itself, proposing the next step, explaining why it's needed, and adjusting the depth of detail to the person it's talking to.

---

## UC-08: Impact analysis on a sudden change request

> **For:** Business analysts on active projects
> **Pain:** A change request "sounds simple," but drags half the project's artifacts behind it, and nobody sees that before development
> **Features:** BFS traversal of the traceability graph, CR scoring (Tasks 5.1 + 5.4)

### Situation

A logistics company. The project: a route management system. Work is on track, everything on schedule. Then the commercial director sends BA Andrew a short message: "We need to add real-time CO2 emissions calculation for each route, for the ESG report. That's simple, right?"

At first glance, a small addition. But Andrew is experienced enough to be wary. "Simple" from a stakeholder's mouth is one of the most dangerous signals in requirements management.

He opens the Platform.

### What Andrew does

> **Andrew:** Open a change request: the commercial director wants to add real-time CO2 emissions calculation for each route. Says it's simple.

### How AInalyst responds

---

> **AInalyst:** CR-011 created. Running impact analysis on the traceability graph...
>
> **Affected artifacts (11):**
>
> FR-022 (route cost calculation): direct dependency. CO2 needs to be calculated on the same route data as cost. A change in the calculation logic could affect FR-022.
> NFR-003 (performance: API response time no more than 500 ms): ⚠️ **conflict**. Real-time CO2 calculation requires a call to an external emissions API. That adds at least 200-400 ms to every request. NFR-003 is now at risk.
> ADR-002 (architectural decision: route data caching): needs review. Cached data doesn't work for a real-time CO2 calculation.
> TC-014, TC-015, TC-017 (three test cases): will need updating.
> *(5 more second-level dependency artifacts)*
>
> **CR assessment:**
> Score: 5.8, **Modify** (accept with a condition).
>
> Recommendation: accept CR-011, but modify the requirement, drop "real time." CO2 is calculated asynchronously and available the next time the route is opened. This removes the conflict with NFR-003 and doesn't require revisiting ADR-002.
>
> Send it to the commercial director for approval?

> **Andrew:** Yes. And prepare the arguments for why real time isn't possible without consequences.

> **AInalyst:** Done. Arguments for the meeting:
>
> Real time means calling an external API every time a route is opened. The system currently handles up to 800 requests per minute at peak hours. Adding an external call would increase average response time from the current 320 ms to an estimated 680-900 ms, which breaks the SLA agreed with clients in NFR-003.
>
> The asynchronous option: CO2 is recalculated in the background every 15 minutes. That's more than sufficient for the ESG report, reports are produced quarterly.

---

### What Andrew gets

He goes to the commercial director not with a refusal, but with data and an alternative. The conversation shifts from "you don't want to do this" to "here's why it has to be this way and how we'll implement it." The CR gets accepted, but in a form that doesn't create technical debt.

And importantly: nobody "forgot" about the three test cases and the caching architectural decision. They're on the list of affected artifacts, they'll be updated before development starts, not after.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 5.4 MCP server (`requirements_assess_changes_mcp`), on receiving a CR, traverses the traceability graph in `traceability_repo.json` using a BFS (breadth-first search) algorithm, finding all artifacts connected to the changed requirements, including second and third-level dependencies. The `score_cr` tool assigns a score based on the number of affected artifacts, the presence of NFR conflicts, and the complexity of the changes. All affected requirements' statuses are updated automatically, flagged as "needs review due to CR-011." The result is saved to the Decision Log via `elicitation_collaborate_mcp`.

---

## UC-09: Three prioritization methods for three different contexts

> **For:** Business analysts on projects with competing requirements
> **Pain:** Prioritization gets done "by feel" or turns into political horse-trading, with no defensible result
> **Features:** MoSCoW, WSJF, Impact/Effort Matrix (Task 5.3)

### Situation

One tool, three fundamentally different scenarios. BA Rachel works on three projects at once. Each has its own audience, its own constraints, its own expectations for prioritization.

**Project A:** An internal HR tool, 25 requirements, three stakeholders, a deadline in two weeks. Needs to be fast.

**Project B:** A product Agile team, 60 requirements in the backlog, needs numeric ranking, every requirement needs a score the team can order by.

**Project C:** A workshop with three directors tomorrow. Non-technical audience, numbers would scare them off, needs something visual, an hour to run.

### Project A: MoSCoW in 20 minutes

> **Rachel:** I need to prioritize 25 requirements for the HR tool. Three stakeholders, deadline in two weeks. Fast.

> **AInalyst:** I recommend MoSCoW, the fastest method for a small set with a tight deadline. Starting a prioritization session. I'll name the requirements one at a time, tell me for each: Must / Should / Could / Won't.

*Twenty minutes later: a MoSCoW matrix with rationale and an artifact ready for stakeholders.*

### Project B: WSJF for an Agile team

> **Rachel:** For the content management project I need numeric prioritization. 60 requirements, we work in Scrum, need a score for each.

> **AInalyst:** I recommend WSJF (Weighted Shortest Job First), the standard for SAFe and Agile teams, it produces a numeric score from business value, time criticality, and risk. For 60 requirements this is the right fit.
>
> For each requirement we need to score three parameters from 1 to 10: Business Value, Time Criticality, Risk Reduction. Shall we start? We can do it in batches of 10, easier than all at once.

*The result: a ranked backlog with WSJF scores, ready to load into Jira.*

### Project C: A workshop with directors

> **Rachel:** Tomorrow there's a workshop with three directors to prioritize product features. Non-technical audience, an hour max, needs to be visual, no formulas or numbers.

> **AInalyst:** I recommend the Impact/Effort Matrix. Two dimensions, no math involved, the directors place features themselves on a "high/low impact" vs "high/low effort" grid. Intuitive, gets everyone involved.
>
> I'll prepare the workshop materials: a list of all requirements described in business language, no technical jargon. Ready to print or put up on screen.

The day after the workshop:

> **Rachel:** Entering the workshop scores: FR-001, high impact, low effort; FR-007, high impact, high effort; FR-019, low impact, high effort...

> **AInalyst:** Building the matrix...
>
> ⚠️ **Dependency violation detected:**
> FR-019 landed in the "don't do" quadrant (low impact, high effort). But FR-004 ("quick win," high priority) has a direct dependency on FR-019, it can't be implemented without it.
>
> Options:
> (A) Raise FR-019's priority, accept it as a forced dependency
> (B) Revisit FR-004, remove the dependency or push it to the next release
>
> What do you want to do?

### What Rachel gets

On each project, a method that fits the context, not "always MoSCoW." And crucially: the dependency violation on Project C surfaced right there in the workshop, while the directors were still in the room, not during sprint planning when changing anything is already painful.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 5.3 MCP server (`requirements_prioritize_mcp`) starts a session with the chosen method via `start_prioritization_session`. For WSJF, the `run_aggregation` tool applies stakeholder influence weights from the registry (Task 3.2), scores from more influential participants carry more weight. When finalizing the matrix, `resolve_conflict` checks the traceability graph for dependency violations, it's not allowed to leave a requirement in "don't do" if high-priority requirements depend on it. The result is saved via `save_prioritization_result`.

---

## UC-10: Root cause analysis: three techniques for one problem

> **For:** Business analysts at the strategy analysis stage
> **Pain:** Projects fix symptoms instead of causes, and the problem comes back a year later in a different shape
> **Features:** Five Whys, Fishbone, Problem Tree (Task 6.1)

### Situation

Three different projects, three different tools. One principle: the platform doesn't impose a technique, it picks the one that fits the context.

**Context A, a medical center:** Patients complain about long waits for test results. The BA needs a fast answer, he has 20 minutes before a meeting with the chief physician.

**Context B, a bank:** Client churn is rising. The causes are clearly multifactorial: complaints about service, technology, competitors, processes. A full picture is needed.

**Context C, manufacturing:** Needs an argument for a 15-million-dollar budget committee. The directors want to see cause-and-effect logic.

### Context A: Five Whys in 20 minutes

> **BA Ian:** I need to quickly figure out why patients are waiting so long for test results. I have 20 minutes.

> **AInalyst:** Starting Five Whys, the fastest method for a linear problem.
>
> Why do patients wait a long time for results?

> **Ian:** The lab enters results into the system late.

> **AInalyst:** Why does the lab enter them late?

> **Ian:** Lab technicians enter data manually at the end of their shift, not right away.

> **AInalyst:** Why do they enter it at the end of the shift?

> **Ian:** Because the data entry system only sits on one computer in the corner, it's inconvenient to walk over there after every test.

> **AInalyst:** Root cause: an **infrastructure constraint**, not enough data entry points. This isn't a motivation or process problem.
>
> Business need BN-001: "Give lab technicians the ability to enter results immediately after completing a test."
>
> Log it?

*Two questions, and the root cause is found. Ian walks into the meeting with the chief physician with a concrete diagnosis, not a vague "we need to improve processes."*

### Context B: Fishbone for a multifactorial problem

> **BA Olivia:** The bank is losing clients. The causes are definitely multifactorial, complaints about everything. We need the full picture.

> **AInalyst:** For a multifactorial problem I recommend Fishbone (Ishikawa diagram). It organizes causes by category and makes sure you don't miss a whole branch of factors.

> Suggested categories for a banking context: Service, Technology, Process, Personnel, Product, External Environment. Which of these are definitely relevant?

> **Olivia:** All six.

> **AInalyst:** Let's start with Technology, that usually has the most concrete factors. What do you know about technology-related problems?

> **Olivia:** Opening an account takes 4 days, there's no online application. The mobile app crashes on transfers above 100,000. There's no integration with the Faster Payments System.

> **AInalyst:** Logged three factors under the Technology branch. Move on to Service?

*After filling in all six branches:*

> **AInalyst:** Synthesis: three groups of root causes stand out.
>
> **Technology gap**: the product lags market standards on 5 of 8 key parameters. This accounts for 40% of complaint mentions.
>
> **Process sluggishness**: average issue resolution time is 6.2 days vs. 1.8 for the market leader.
>
> **Product gap**: no cashback or loyalty programs, while three direct competitors have them.
>
> Registering three business needs: BN-001, BN-002, BN-003. Move on to defining the future state?

### What the BA gets

In both cases: not just a list of causes, but a structured business need with an identifier that automatically becomes the root node of the traceability graph. Every subsequent project requirement will be linked to it, and at any point it becomes possible to check: does this requirement actually solve the problem the project was launched to fix?

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 6.1 MCP server (`current_state_mcp`) supports three modes through the `run_rca` tool: `five_whys`, `fishbone`, and `problem_tree`. AInalyst picks the mode based on context: number of factors, presence of organizational pressure, time constraints. When the analysis is done, `register_business_need` creates a BN-xxx record in `traceability_repo.json` as a root node of the graph, all subsequent business objectives and requirements will inherit traceability links from it.

---

## UC-11: SMART objectives and gap analysis: from vague intentions to defensible goals

> **For:** Business analysts at the future-state definition stage
> **Pain:** Objectives are worded so vaguely nobody can tell if they've been met, and nobody has measured the gap between "now" and "want"
> **Features:** SMART validation of business objectives, gap analysis (Task 6.2)

### Situation

An EdTech company. A new LMS (learning management system) is launching. BA Chloe is starting the analysis phase, needing to record the future-state objectives.

The first attempt at wording is the kind that usually comes out of a strategy meeting.

### What Chloe does

> **Chloe:** Recording the project objective: improve employee engagement in training.

### How AInalyst responds

---

> **AInalyst:** ❌ The objective failed SMART validation.
>
> Problems:
> **Not measurable:** "improve engagement," how will we know we've achieved it?
> **No time horizon:** by when?
> **No baseline metric:** what's the starting point?
>
> Let's try rewording it. What's currently measured in your training system? Do you have data on completion rate or other metrics?

> **Chloe:** Yes, completion rate right now is 34%. We want 70% by year end.

> **AInalyst:** New wording: "Increase corporate training program completion rate from 34% to 70% by Q4 2026."
>
> ✅ SMART check passed:
> Specific: completion rate as the metric
> Measurable: 34% → 70%
> Achievable: a 36-point increase in a year is ambitious but realistic with a platform change
> Relevant: directly tied to business need BN-001
> Time-bound: Q4 2026
>
> Log it as BG-001?

> **Chloe:** Yes. Now run gap analysis.

> **AInalyst:** Gap analysis completed — **lms_2026**
>
> **Elements analyzed:** 3
> **Current-state baseline:** ✅ from 6.1
>
> ---
>
> ## Technology and Infrastructure (`technology`)
>
> **Change type:** ⬆️ Improve
> **Complexity:** 🔴 High
>
> **Current state:** Desktop-only LMS, no mobile client...
> **Target state:** Responsive platform, full course completion from a phone...
>
> **Gap:** Current: Desktop-only LMS, no mobile client... → Target: Responsive platform, full course completion from a phone...
>
> ## Capabilities and Processes (`capabilities`)
>
> **Change type:** ⬆️ Improve
> **Complexity:** 🟡 Medium
>
> **Current state:** Content refreshed ad hoc, no review cycle...
> **Target state:** Mandatory annual review of every course...
>
> **Gap:** Current: Content refreshed ad hoc, no review cycle... → Target: Mandatory annual review of every course...
>
> ## Business Architecture (`architecture`)
>
> **Change type:** 🆕 New
> **Complexity:** 🟡 Medium
>
> **Current state:** *(no 6.1 data)*
> **Target state:** LMS ↔ HR system integration, progress visible in the employee profile...
>
> **Gap:** No current state — the element is being created from scratch. Target: LMS ↔ HR system integration...
>
> One gap card per future-state element you captured, each with a change type and a complexity rating. `technology` is the hardest of the three — hitting 70% isn't realistic without it. Pass this to the design phase as a basis for requirements?

---

### What Chloe gets

Instead of a vague "improve engagement," a concrete, measurable target and one clearly described gap per future-state element, each rated for how hard the change is. The gap analysis shows immediately: not everything needs fixing, and `technology` is where the effort sits.

And importantly: BG-001 is now recorded in the traceability repository. When requirements for mobile access appear in the design phase, they'll automatically link to this objective. At any point you can ask "which requirements serve objective BG-001?" and get the full list.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 6.2 MCP server (`future_state_mcp`), when `capture_future_state_element` is called, immediately runs the wording through `validate_smart_goal`, checking for a metric, a time horizon, a baseline, and a target value. Objectives that fail validation aren't recorded. Once objective BG-001 is confirmed valid, the `run_gap_analysis` tool compares the current and future states element by element — one gap card for each of the future-state elements captured, out of the eight BABOK defines — and returns them with a change type (new / improve / eliminate / replace) and a complexity rating (low / medium / high). It assigns no gap IDs and no priorities: how big a gap is stays the analyst's judgement, recorded later as `gap_severity` in 6.4. The result is saved to `gap_analysis.json` and imported automatically in Task 6.4, where the platform reports which of those gaps the solution scope covers.

---

## UC-12: Verifying requirements: a junior BA works like a senior

> **For:** Junior BAs, team leads, heads of business analysis practice
> **Pain:** Requirements go into development "raw," and wording problems only surface during testing
> **Features:** Requirements quality check against 9 BABOK characteristics (Task 7.2)

### Situation

A fintech startup. Roman has been a business analyst for a little over a year. He wrote 40 requirements for a new credit scoring module, spent a week on it, reread it several times, was satisfied. Tomorrow he plans to hand it off to development.

Before handing it off, he decides to run it through the platform.

### What Roman does

> **Roman:** Check the quality of the requirements for the credit scoring module. All 40 of them, file requirements_credit_v3.md.

### How AInalyst responds

---

> **AInalyst:** Checking 40 requirements against the 9 BABOK characteristics...
>
> **Check summary:**
> ✅ Correct: 29 of 40
> ⚠️ With issues: 11 requirements
>
> **Problems found by type:**
>
> 🔴 **Ambiguity (6 cases)**, vague wording:
> FR-007: "The system should process applications quickly." What does "quickly" mean? No measurable criterion.
> FR-014: "The interface should be user-friendly." Unverifiable, what's the acceptance criterion?
> *(4 more requirements)*
>
> 🟡 **Not Atomic (3 cases)**, one requirement bundles several unrelated ones:
> FR-023: "The system should calculate the credit score AND send a notification AND save the calculation history." Three different requirements in one.
>
> 🟡 **Missing Acceptance Criteria (2 cases):**
> FR-031, FR-038: correctly worded requirements, but no acceptance criteria at all. A developer won't know when to consider the task done.

> **Roman:** Show me how to fix FR-007.

> **AInalyst:** Original version:
> *"The system should process applications quickly"*
>
> Problem: "quickly" is a subjective criterion. The developer will build "quickly" to their own understanding, the tester will check it against theirs.
>
> Fixed version:
> *"The system shall calculate the applicant's credit score in no more than 3 seconds from receipt of all required data, under standard load (up to 100 concurrent requests)"*
>
> What changed: a measurable metric was added (3 sec), a measurement condition (standard load), and a boundary value (100 requests). This requirement is now verifiable.
>
> Fix the remaining 5 ambiguity cases the same way?

---

### What Roman gets

11 problems that developers would have discovered during implementation, each one turning into clarifying questions, back-and-forth, lost time, and possibly rework. Found in a few minutes before handoff, not after.

For a junior BA this isn't just a fix to one document. Walking through each case is training on real material: why the wording was bad and what good wording looks like. After ten such sessions, requirement quality becomes a habit.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 7.2 MCP server (`requirements_verify_mcp`), when `check_req_quality` is called, checks each requirement against two groups of BABOK characteristics: Group A (atomic, unambiguous, verifiable, feasible, necessary) and Group B (prioritized, complete, consistent, traceable). Each problem gets a VI-xxx identifier in the verification tracker. After a fix, the BA marks the requirement via `mark_req_verified`, the status changes from `draft` to `verified`. Once all requirements are checked, `save_artifact` generates a Verification Report in `governance_plans/reports/`.

---

## UC-13: Assessing organizational readiness for change

> **For:** Business analysts and PMs on large transformation projects
> **Pain:** The director wants to launch everything at once, but the organization objectively isn't ready. And "that's my gut feeling" isn't an argument
> **Features:** Organizational readiness assessment, change strategy option matrix (Task 6.4)

### Situation

A pharmacy chain, 150 retail locations nationwide. The director of development, Hastings, has set the goal: roll out a new inventory management system across all locations at once by September 1. "Big bang." The team is afraid to push back, the director is used to fast results.

BA Vera senses something is off. Past major rollouts at the company have ended in chaos, but that's not something people say openly. She doesn't have the authority to say "no," but she has an obligation to present the data.

She opens AInalyst.

### What Vera does

> **Vera:** I need to assess organizational readiness for change for the WMS rollout project. The director is planning a big bang by September 1, 150 locations at once. I want an objective picture.

### How AInalyst responds

---

> **AInalyst:** Running an Organizational Readiness Assessment across six dimensions. I'll ask questions for each, answer from 1 to 5, where 1 is critically low and 5 is fully ready.
>
> **Leadership engagement.** How actively is top management supporting the change, allocating resources, publicly communicating its importance?

> **Vera:** 4, the director personally initiated the project, the budget is allocated.

> **AInalyst:** **Cultural readiness.** How does the company typically react to change, does staff embrace new things or resist? Have there been major changes in the last 2 years?

> **Vera:** 2, people are used to working the old way, the last CRM rollout two years ago was rough, a third of the stores resisted it for six months.

> **AInalyst:** **Change history.** How successfully has the company delivered major transformation projects in the past?

> **Vera:** 1, honestly, not a single major project was finished on time and without losses.

---

*After six questions:*

---

> **AInalyst:** Final Readiness Score: **2.4 / 5.0**, status **Proceed with Caution**.
>
> Breakdown by dimension:
> Leadership engagement: 4/5 ✅
> Cultural readiness: 2/5 ⚠️
> Change history: 1/5 🔴
> Technical maturity: 2/5 ⚠️
> Resource readiness: 3/5 ✅
> Communication maturity: 2/5 ⚠️
>
> **Key risk:** The director's high engagement creates an illusion of readiness. But cultural resistance plus a negative track record plus low technical maturity are three independent failure factors, any one of which alone could stop a big bang rollout across the locations.
>
> Comparing strategy options...

> **AInalyst:** **Analysis of three options:**
>
> **Option A, Big Bang (as the director is planning):**
> Speed: maximum. Risk: critical. At a score of 2.4, the historical success rate for big bang rollouts of this kind is under 30%.
>
> **Option B, Pilot First (recommended):**
> Launch at 5-10 pilot locations with varied profiles, different regions, sizes, staff experience. 2-3 months. Adjust and scale based on pilot results.
>
> **Option C, Phased Rollout:**
> Waves of 30-40 locations every 6 weeks. Lower risk than big bang, but higher than a pilot.
>
> **Weighted assessment:** Option B (Pilot First) scores highest given the risk profile and current readiness. Time to full coverage: December 2026 instead of September. The trade-off: 3 extra months versus a high probability of failure and a second rollout attempt.
>
> Put together a report with the rationale for the director?

> **Vera:** Yes. And add a section on what needs to happen before the pilot, the minimum set of conditions.

---

### What Vera gets

Not "I feel like this is risky," but a structured assessment with scores across six dimensions, a comparative analysis of three options, and a concrete alternative with a rationale. Now the conversation with the director is about data, not fears.

And a second benefit: if the director insists on big bang anyway, the Decision Log records that the risks were presented, assessed, and knowingly accepted. That's professional insurance.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 6.4 MCP server (`change_strategy_mcp`), when `assess_org_readiness` is called, collects scores across six standard dimensions and computes a weighted Readiness Score, change history and cultural readiness carry extra weight since they're the strongest predictors of failure. The `compare_strategy_options` tool builds a weighted matrix for each option against: speed, risk, cost, fit with the readiness profile. The result, with the recommended option, is saved to `{project}_change_strategy.json` and used when generating the final artifact via `save_artifact`.

---

## UC-14: One artifact, five audiences

> **For:** Business analysts on projects with complex communication needs
> **Pain:** Every audience needs something different, the director won't read a tech spec, a lawyer won't understand User Stories, a developer doesn't need a business case
> **Features:** Communication package with role-based adaptation (Task 4.4)

### Situation

A large retailer. The project: a new loyalty system. BA Marina has finished a set of requirements: 12 confirmed functional requirements, three NFRs, two business rules. A good set, now it needs to go out to interested parties.

The problem: the audiences are fundamentally different.

The marketing director wants to understand the business value, and nothing else. The CTO wants to see integration dependencies and architectural consequences. The dev team lead wants concrete user stories with acceptance criteria. The QA lead wants a list of testable conditions. The lawyer only cares about what touches GDPR and personal data.

The usual path: five different documents, five separate editing sessions. Marina tries a different one.

### What Marina does

> **Marina:** Prepare a communication package for the loyalty system requirements for five audiences: marketing director, CTO, dev team lead, QA lead, lawyer. Source: approved_requirements_loyalty_v2.md.

### How AInalyst responds

---

> **AInalyst:** Reading the requirements... Done. Generating five versions.
>
> **Version 1, Marketing Director (business summary, 1 page):**
> Focus: what the business gets, in what metrics, by when. Technical details excluded. Three key points: the points-accrual mechanic is projected to increase retention by 12-18%, personalized offers launch automatically, mobile app integration is ready for Q3.
>
> **Version 2, CTO (technical overview):**
> Focus: integration points, dependencies on existing infrastructure, performance and security NFRs. A list of open architectural questions requiring resolution before design is attached.
>
> **Version 3, Dev Team Lead (User Stories + AC):**
> The 12 requirements reformatted as User Stories with full acceptance criteria. Definition of Done for each story. Dependencies between stories are marked.
>
> **Version 4, QA Lead (test matrix):**
> For each requirement: testable conditions, positive and negative scenarios, boundary values. Format ready for import into TestRail.
>
> **Version 5, Lawyer (GDPR slice):**
> Only requirements touching personal data: collection, storage, transfer to third parties, retention period, consent withdrawal mechanism. Each one links to the relevant GDPR article.
>
> All five documents are saved in `governance_plans/reports/`. Want to preview one of them first?

> **Marina:** Show me the lawyer's version, I want to make sure I didn't miss anything.

> **AInalyst:** Here's the GDPR slice.
> Found 4 GDPR-relevant requirements:
> FR-003: collecting email and phone number at registration → Art. 6(1)(b), consent for processing
> FR-007: sharing data with partners for personalized offers → Art. 28, data processor agreement
> FR-009: purchase history retained for 3 years → Art. 5(1)(e), storage limitation
> FR-011: account deletion → Art. 17, right to erasure
>
> ⚠️ **Note:** FR-007 needs an explicit statement in the user agreement of which partners specifically and for what purpose. The current wording doesn't specify this. Recommend clarifying this before legal review.

---

### What Marina gets

Five documents from one source, in a single command. Each adapted to the audience's language and needs. And on top of that: the platform itself caught a potential GDPR issue in FR-007 that Marina might have missed while preparing the legal version.

Instead of half a day of editing, a few minutes and five finished artifacts.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 4.4 MCP server (`elicitation_communicate_mcp`), when `prepare_communication_package` is called, runs five parallel generations with different `role` parameters: `executive`, `cto`, `dev_lead`, `qa_lead`, `legal`. Each profile determines the relevant requirement filter, level of detail, and output format. For the legal profile, a GDPR analysis fires additionally, the tool checks each requirement for personal data markers and maps it to regulation articles. After generation, `log_communication` records the distribution in the communication log, and `check_communication_schedule` verifies whether a scheduled deadline was missed for any recipient.

---

## UC-15: Reusing requirements on a new project

> **For:** Business analysts at organizations with several similar projects
> **Pain:** Writing the same thing from scratch every time, authentication, roles, notifications, logging. Even though it's already been done three times
> **Features:** Requirement search and reuse (Task 5.2)

### Situation

An enterprise software company. Over three years it delivered three similar projects: an HR portal, an internal CRM, and a document management system. Each time the BA wrote requirements for authentication, the role model, and the notification system from a blank page.

Now a fourth project is starting: an employee self-service portal. BA Adam knows: authentication, roles, and notifications are coming again. He decides not to reinvent the wheel.

### What Adam does

> **Adam:** Starting a new project: self-service-portal-2026. Before writing requirements for authentication and the role model, check if there's anything reusable from past projects.

### How AInalyst responds

---

> **AInalyst:** Searching by tag `authentication` and `authorization` in the repositories hr-portal-2024, crm-internal-2024, docflow-2025...
>
> Found: 8 requirements tagged `authentication`.
>
> **By status:**
> ✅ Approved: 6 requirements
> ⚠️ Approved with notes: 2 requirements (have caveats, need a relevance check)
>
> **List:**
> FR-AUTH-001: The system shall support SSO via the corporate LDAP. Source: hr-portal-2024. Status: approved. Used in 2 projects.
> FR-AUTH-002: A user session shall end automatically after 30 minutes of inactivity. Source: crm-internal-2024. Status: approved.
> FR-AUTH-003: Login attempts with an incorrect password are locked out after 5 failed tries. Source: hr-portal-2024. Status: approved. Requirement passed a security review.
> *(5 more requirements)*
>
> On the role model (`roles`, `rbac`) found another 11 requirements. Show them?

> **Adam:** Yes. And tell me right away, of what you found, what can be added to the new project unchanged?

> **AInalyst:** Of the 19 requirements found:
>
> **Add unchanged (13):** basic authentication, SSO, lockout on failed attempts, read/write role permissions, login logging. They don't depend on the specifics of the business processes.
>
> **Adapt before use (4):** requirements for roles specific to previous domains (for example, the "HR manager role" from hr-portal doesn't apply directly and needs adapting).
>
> **Don't reuse (2):** requirements with notes from the 2024 security review, the architecture has changed, they're outdated.
>
> Add the 13 requirements to the self-service-portal-2026 repository, keeping a link back to the source?

> **Adam:** Yes, add them.

> **AInalyst:** Done. 13 requirements added to the self-service-portal-2026 repository. Source and version preserved for traceability. Total savings: roughly 3-4 hours of drafting and approvals.
>
> Now you can focus on what's actually unique to this project.

---

### What Adam gets

Three to four hours of work he'd already done isn't done again. 13 requirements in the new repository from minute one, all previously approved on past projects. And importantly: traceability is preserved, if a problem ever turns up in a source requirement, the platform will flag every project where it's used.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 5.2 MCP server (`requirements_maintain_mcp`), when `find_reusable_requirements` is called, searches by tags and keywords across all `traceability_repo.json` repositories available in the platform's working directory. The `approved` status acts as a filter, requirements in `draft` or `rejected` status don't appear in the results. When adding to the new repository via `init_traceability_repo`, each reused requirement keeps a link to its source (`source_project`, `source_id`), which provides two-way traceability: from the new project back to the original, and forward again.

---

## UC-16: Orphan requirements and assumption management

> **For:** Business analysts on projects with "sprawling" scope
> **Pain:** The repository accumulates requirements nobody's sure of the purpose of, and assumptions nobody has verified
> **Features:** Business alignment check, assumption log (Task 7.3)

### Situation

A large telecom. The project: a self-service portal for B2B clients: contract management, invoice viewing, support tickets. The repository has grown to 55 requirements. BA Stephanie suspects some of them appeared "along the way," with no link to real business objectives. And one critical assumption that nobody has verified is bothering her too.

### What Stephanie does

> **Stephanie:** Check business alignment for all 55 requirements on the b2b-portal-2026 project. I want to find orphan requirements, ones not linked to any business objective.

### How AInalyst responds

---

> **AInalyst:** Running the check against the traceability graph...
>
> Of 55 requirements, 7 are orphans (not linked to any business objective or business need):
>
> FR-041, FR-042, FR-043: mobile app requirements. The mobile app isn't in scope for b2b-portal-2026 per ba_plan.json.
> FR-047, FR-048: billing logic requirements. Billing belongs to the ERP-billing system, a different domain.
> FR-033, FR-039: duplicate FR-011 and FR-019 with minor wording differences.
>
> Recommendations: the first five, move out of scope or hand off to the relevant projects. The last two, verify and, if confirmed duplicates, remove.
>
> What do you want to do with each one?

> **Stephanie:** Accepted for all seven. Now I want to log a critical assumption: we're assuming the ERP system supports a REST API for exporting invoice data. This hasn't been confirmed.

> **AInalyst:** Logging assumption AS-001:
> "The ERP system (SAP version x.x) supports a REST API and provides an endpoint for exporting a customer's invoice data."
>
> Risk level: **high_risk**, if this assumption turns out false, it blocks implementation of FR-008, FR-012, FR-015, FR-021 (all invoice-viewing requirements, 4 requirements in total depend directly on this API).
>
> ⚠️ **Warning:** Validation of FR-008, FR-012, FR-015, FR-021 is blocked until AS-001 is confirmed. Recommend initiating a technical consultation with the ERP architect before the design phase wraps up.
>
> Assign an owner to verify the assumption?

> **Stephanie:** Yes, owner is Grant (IT architect). Deadline: April 18.

---

### What Stephanie gets

Seven "extra" requirements removed before development, that's several days of developer work saved that wasn't needed. A critical assumption is logged, its risk assessed, and four dependent requirements are flagged "don't validate until confirmed." Grant knows what's expected of him and by when.

If the assumption hadn't been logged, it might have been discovered mid-development, when a developer tried to call an API that doesn't exist.

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 7.3 MCP server (`requirements_validate_mcp`), when `check_business_alignment` is called, does a BFS traversal of the graph in `traceability_repo.json`, for each requirement looking for a path to a business-need root node. Requirements with no such path get the `orphan` status. When an assumption is logged via `log_assumption`, the tool automatically computes an impact_score, the number of requirements that depend on that assumption. If the score exceeds a threshold, or the risk level is `high_risk`, all dependent requirements are flagged `blocked_by_assumption`, and their status in the approval cycle is frozen until the assumption is verified.

---

## UC-17: A final recommendation to the sponsor with a Value Score

> **For:** Business analysts preparing a recommendation for senior leadership
> **Pain:** "We recommend option B" sounds like an opinion. Not a conclusion from an analysis.
> **Features:** Weighted evaluation of solution options, Recommendation Document (Task 7.6)

### Situation

A manufacturing company. The current MES (manufacturing execution system) is outdated: it breaks down, doesn't integrate with new equipment, and vendor support ends in a year. The board is waiting for a recommendation: what to do.

BA Ian put together three options. Now he doesn't just need to choose, he needs to defend the choice in front of people who will ask uncomfortable questions.

**Option A, Build:** Build a custom system. Budget 40 million dollars, 18-month timeline.
**Option B, Buy SAP ME:** Purchase and implement an off-the-shelf solution. Budget 25 million dollars, 8-month timeline.
**Option C, Hybrid Odoo:** Implement Odoo customized for manufacturing specifics. Budget 18 million dollars, 12-month timeline.

### What Ian does

> **Ian:** I need to compare three options for replacing the MES and prepare a recommendation for the board. Options: Build (40M / 18 mo), SAP ME (25M / 8 mo), Hybrid Odoo (18M / 12 mo). Critical requirements: SCADA loop integration, compliance with Russian production accounting regulations, scalability to 3 new plants.

### How AInalyst responds

---

> **AInalyst:** Running an evaluation across five parameters: Benefits, Strategic Alignment, Cost, Risk, Implementability. Let's start with the key constraint.
>
> You mentioned SCADA loop integration as a critical requirement. Clarify: does each option have a ready connector, or will custom development be needed?

> **Ian:** SAP ME, no ready connector for our SCADA. Needs custom development, that's +4-5 months and +8-10 million on top. Build, we write it ourselves, already included in the estimate. Odoo, there's a ready module, tested on a similar production line.

> **AInalyst:** Key point: this changes the picture for Option B. Realistic parameters for SAP ME: budget 33-35 million, timeline 12-13 months. Recalculating the scores...
>
> **Final Value Score table:**
>
> | Parameter (weight) | Build | SAP ME (adj.) | Hybrid Odoo |
> |---|---|---|---|
> | Benefits (×2.0) | 7.2 | 8.1 | 7.8 |
> | Strategic Alignment (×1.5) | 8.0 | 7.5 | 8.2 |
> | Cost (×1.5, inverted) | 4.0 | 5.8 | 8.5 |
> | Risk (×1.0, inverted) | 5.5 | 6.2 | 7.0 |
> | Implementability (×1.0) | 5.0 | 6.5 | 7.8 |
>
> **Final Value Score:**
> Build: 52.3
> SAP ME (adjusted): 61.4
> **Hybrid Odoo: 73.1** ✅ Recommended
>
> Hybrid Odoo leads despite lacking the "SAP" brand name. Deciding factors: the ready SCADA connector removes the main technical risk, cost is 40% lower than Build for comparable benefits, and there's a worked-out mitigation plan for Odoo, that risk would have stayed open for SAP ME.
>
> Success metrics to lock in before the project starts:
> OEE (Overall Equipment Effectiveness): target +8% by Q4 2027
> Line changeover time: −30% by Q2 2027
> Integration incidents: no more than 2 per month in year one
>
> Put together a Recommendation Document for the board?

> **Ian:** Yes. And add a section on "what happens if we do nothing," for the directors who'll want to defer the decision.

---

### What Ian gets

A recommendation with numbers that can be checked. The board sees not "we think Odoo is better" but a weighted matrix with a formula and parameters that can be challenged, and recalculated with different weights right there in the meeting if needed.

And importantly: success metrics are locked in before development starts. In a year and a half, once the system is running, it'll be clear whether the result was achieved, and there won't be arguments about "what we were even planning for."

### What happens under the hood

> *The business analyst doesn't work with this directly, the Platform does it all automatically.*

The Task 7.6 MCP server (`value_recommend_mcp`), when `add_value_assessment` is called, records each option's parameters, then `compare_value` applies the weighted formula: Benefits×2.0 + Alignment×1.5 − Cost×1.5 − Risk_Penalty×1.0. Adjusting SAP ME's real parameters for SCADA is a change to the Cost and Risk inputs before running the formula, not an exclusion from consideration. The `save_recommendation` tool generates the final Recommendation Document: an options table, the rationale for the choice, success metrics with baseline and target values, and a risk section. The document is saved to `governance_plans/reports/` and is ready to hand to stakeholders.

---

## Conclusion: why this works, and for whom

Reading all 17 scenarios above closely, one common thread stands out: in none of them does the business analyst type commands, recall tool names, or dig through documentation. Julia just talks about the project. Andrew describes the commercial director's request. Roman asks to "check the requirements." Ordinary human sentences, and the platform does the work.

That's not an accident and not a marketing trick. It's an architectural decision.

### How it works under the hood

Under the hood, AInalyst runs 21 specialized skills and 22 MCP servers with 113 tools, each of which "knows" a specific BABOK task: how to do it correctly, what to watch for, what artifact to produce.

Each skill is written to a strict specification and includes a YAML header with triggers: semantic patterns that describe exactly when this skill should fire. When the business analyst writes something in the chat, AInalyst analyzes the request, matches it against the triggers, activates the right skill, and that skill calls the corresponding tools from the MCP servers. The business analyst doesn't know what happened under the hood. And doesn't need to: they see the result.

That's why the same conversational request, "what's going on with this stakeholder," triggers engagement signal diagnostics, while "compare the interviews" triggers cross-analysis of multiple elicitation sessions. Not because the BA picked the right tool, but because the platform itself knows which tool is needed here.

### What this delivers in practice

**Reduced cognitive load.** A project can run for months, stakeholders, decisions, requirements, approval conditions, change history. Holding all of that in your head is impossible. AInalyst records every step and stores context in structured artifacts. At any point you can ask "what's currently open on approvals" or "why was this decision made back in March," and get an answer immediately. No digging through email, no flipping through folders, no polling colleagues.

**Methodological insurance.** BABOK is 500 pages of structured expertise. Nobody has to know it cold, but working by its principles means doing the job right. AInalyst has built that expertise into the process: it doesn't let you skip an important step, it warns about risks, it suggests the next action, and it reminds you of deadlines in time. A BA who isn't deeply versed in the methodology works with the platform just as confidently as an experienced specialist, because the platform guides them through the process.

### Who this is built for

The scenarios above cover a deliberately wide range of audiences.

**An experienced business analyst** gets a tool that removes the routine: structuring transcripts, building traceability matrices, generating communication packages for different audiences. It frees up time for what actually requires expertise: analysis, interpretation, decision-making.

**A junior or less methodologically trained BA** gets a reliable guide. The platform doesn't judge for not knowing BABOK, it just helps get it right: asking the right questions, explaining why a piece of wording failed validation, showing what a good requirement should look like.

**A product manager or project manager** on a project with no dedicated BA gets the ability to work by a professional methodology without studying it specially. The platform adapts its language to whoever it's talking to and takes on the role of methodologist, while the PM stays in their own area of responsibility: knowledge of the product, the market, the team.

**A startup founder or small team** with no budget for a full-time analyst gets a structured environment for working with requirements from day one, instead of accumulating years of chaos in Notion and chat apps.

---

Different roles, different experience, different context. One platform. Because at its core isn't a list of features, it's a principle: **you bring the knowledge of your project and product, AInalyst takes care of everything else.**
