
# User Guide
## AI-powered Platform AInalyst
**Download:** https://github.com/chaussky/ainalyst.git

**LinkedIn:** https://www.linkedin.com/in/anatole-tchaoussky-82957a40b/
---
# Chapter 4: Elicitation and Collaboration


---

## Overview of Chapter 4

Chapter 4 of BABOK, "Elicitation and Collaboration," is the heart of a business analyst's work. This is where the BA interacts directly with stakeholders: preparing sessions, running them, checking the quality of what was collected, communicating results to different audiences, and managing relationships within the team.

Unlike Chapter 3 (planning, done once at the start), Chapter 4 is **iterative**. Every new interview, workshop, or survey is a new cycle of 4.1 to 4.2 to 4.3 to 4.4. A project spanning several months can produce 20 to 30 such cycles.

This is where the most valuable and most fragile material accumulates: what a stakeholder said, what is behind it, how it relates to what everyone else said. This material is easily lost (notes in a notebook), easily distorted (retelling from memory), and easily left incomplete (questions that were never asked).

The platform closes exactly these risks, without changing how the BA works with stakeholders in person.

---

## Task 4.1: Prepare for Elicitation

### Brief description

The BA prepares for a specific elicitation session: defines the goals of the meeting, chooses a technique, formulates questions, records a plan. This task is performed **before** every session: interview, workshop, survey, or observation.

### BA pain points

**An interview without a goal is just a conversation.** The BA goes in to "find out what the stakeholder thinks" without concrete goals. The result: an hour spent, a lot of interesting things said, but after the meeting it's unclear exactly what needed to be found out, and whether it was. The next session is needed simply because the first one didn't produce answers.

**Technique selection is random.** Most BAs always default to interviews, because that's what they're used to. For a group of 15 users, that's 15 hours of meetings instead of one workshop. For standard operational data, it's a workshop instead of a 10-minute survey.

**Questions are formulated on the fly.** The BA spends five minutes preparing for an interview and recalls questions as the conversation goes. Key topics get skipped, the stakeholder wanders into details that aren't needed, and important aspects surface only after the meeting.

**"What exactly do I want to get out of this?"** This question often goes unasked by the BA explicitly. A good elicitation goal is verifiable: after the session, there's either an answer or there isn't. A vague goal ("understand user pain points") is not verifiable.

**Google Forms by hand.** If a survey is needed, the BA builds it manually, formats it, shares it. This is a separate routine task that adds no analytical value.

### What we built

**A step-by-step preparation algorithm.** SKILL.md walks the BA through five steps: goals, stakeholders, elicitation format, questions, artifact. Each step is one block of questions, without overload. AInalyst won't let go without a verifiable goal.

**Technique selection logic.** The platform accounts for the situation: number of stakeholders, whether depth or breadth of coverage is needed, participant availability, availability of documents. Based on this it recommends a technique and explains why.

**Question generation for the chosen technique.** For the selected technique, AInalyst generates a concrete list of questions, taking into account the stakeholder's role, the session goals, and what is already known from previous interviews (if any).

**Recording the plan as an artifact.** `save_elicitation_plan` saves goals, participants, technique, and questions. This isn't just a document: the plan is linked to the results of 4.2, and afterward you can check whether all planned questions were asked and whether all goals got answers.

**Creating a Google Form.** `create_google_form` builds a form automatically from a given question structure. The BA doesn't touch Google Forms by hand.

**Reading the 3.1 plan, when there is one.** If the BA already ran the optional `plan_ba_activities` step in Chapter 3, `save_elicitation_plan` automatically states the work period planned for this session (with its effort and timing) and honestly cross-checks the chosen elicitation technique against what 3.1 recommended. On an agile project, where 3.1's recommended techniques are things like Backlog Management and Retrospectives rather than an elicitation technique, it says plainly that there's nothing to cross-check, instead of flagging every session as a mismatch.

### Value for the BA

**Every meeting now has an outcome.** When the goal is formulated before the meeting, there's a clear answer afterward: achieved or not. If not, another session is needed. If achieved, work can move forward. This removes the feeling of "wasted time."

**The right technique saves time.** Replacing 10 individual interviews with one workshop is the difference between a week of work and one evening. AInalyst makes this choice deliberate rather than habitual.

**Prepared questions mean better-quality material.** The stakeholder feels the structure of the conversation. All key topics get covered. The BA isn't scrambling to remember what else to ask. This directly affects the quality of the results in 4.2.

**Continuity between sessions is preserved.** AInalyst sees previous plans and results. When preparing for the next interview, it reminds the BA: here's what was left unresolved from the last meeting, here's what needs clarifying. The BA doesn't have to hold this in their head.

### How to use it: an example

The BA is preparing for a first interview with a new stakeholder, Sarah, the warehouse manager.

They tell AInalyst: *"I'm preparing for an interview with Sarah. She's the warehouse manager and will be one of the key users of the new WMS. I want to understand her pain points with the current system and what matters to her in the new one."*

AInalyst asks clarifying questions: how much time is available, has anyone from the warehouse already been interviewed, are there specific hypotheses that need testing. The BA answers. AInalyst proposes a structured 45-minute interview with three blocks of questions: current situation, pain points, and success criteria. The BA says "add one more question about the SAP integration," and AInalyst adds it. "Save it," and the plan is recorded.

**The BA goes into the actual interview with a ready list of questions, understanding exactly why they're there.**

---

## Task 4.2: Conduct Elicitation

### Brief description

After a session is complete, the BA hands off the raw material (transcript, notes, recordings) for analysis. The platform structures the results, identifies gaps, finds contradictions between sources, and recommends next steps. The task supports three scenarios: a single session, comparison of several sessions, and analysis for a Change Request.

### BA pain points

**The transcript sits unprocessed.** The BA ran the interview and captured a lot of interesting material, but doesn't know where to start the breakdown. Especially if the interview was long and unstructured. The material "cools off," details get forgotten, analysis gets postponed.

**"What exactly did I extract from this?"** The stakeholder talked about their work for an hour. The BA listened, nodded, took notes. But structuring this into requirements is a separate analytical task that takes as long as the interview itself.

**Gaps are only visible when it's too late.** The BA realizes they didn't ask about something important only after the stakeholder has moved on to something else, gone on a business trip, or left the project altogether. The gap in knowledge is discovered not right after the interview, but in the middle of Chapter 5, when the requirements have already been written.

**Contradictions between stakeholders go unnoticed.** James said one thing, Rachel said another, but the BA processed the interviews separately and didn't cross-check them. The conflict surfaces at the prioritization or approval stage, when it's much harder to fix.

**The stakeholder registry doesn't grow.** In every interview, the stakeholder names other participants ("talk to Max from IT too" or "we have a chief accountant, Grace, she also works with the system"). The BA nods, but these people never make it into the registry. A month later it turns out a key stakeholder was never included in the process at all.

**A Change Request means "start over."** A CR comes in. The BA doesn't know: which of the already collected requirements are affected? Which stakeholders need additional elicitation? What has changed in what they said before? This is several hours of manual work.

### What we built

**Structured analysis of a single interview.** `process_elicitation_results` accepts a transcript or notes in any format and returns: structured requirements, pain points, business rules, a stakeholder profile, identified gaps, and recommendations for the next step.

**Cross-analysis of multiple sessions.** `compare_elicitation_results` cross-references artifacts from different interviews and identifies: contradictions between stakeholders, gaps that no interview closed, consensus on key questions, and who needs to be asked more about what.

**Change Request analysis.** `save_cr_elicitation_analysis` takes a CR description and determines: which previously collected requirements are affected, who needs additional elicitation and about what, and what information is now outdated. This is a technical input for Task 5.4.

**Automatic registry expansion.** `update_stakeholder_registry` adds a new stakeholder or updates an existing one. It's called right during interview analysis: "James mentioned Max" leads to one request, and Max is in the registry with a note on the source.

### Value for the BA

**A transcript turns into requirements in minutes.** The BA no longer spends an hour on manual breakdown of recordings. They hand over the raw material and get back a structured artifact. This frees up cognitive resources for analytical work (decisions, interpretation) rather than mechanical work (formatting, structuring).

**Gaps are visible right after the session, while they can still be closed.** AInalyst explicitly points out: "here are three topics that remain unresolved." The BA knows what to clarify at the next meeting or by email, while the stakeholder still remembers the conversation.

**Contradictions are caught at the 4.2 level, not at 5.3.** Early detection of a conflict between stakeholders is a manageable situation. It can be clarified with an additional interview or workshop. Detection at the prioritization stage requires reworking artifacts that are already finished.

**The stakeholder registry grows organically.** After every interview, AInalyst suggests adding the people who were mentioned. This takes 30 seconds. A month in, the registry contains all the real participants, not just the ones the BA knew about at the start of the project.

**A CR stops causing panic.** There's a structured process: the platform works out what changed, what's outdated, and who to ask. The BA gets a clear action plan instead of a feeling that "now everything has to be redone."

### How to use it: an example

The BA has interviewed Sarah and hands the transcript to AInalyst: *"Here's the recording of our conversation [text]. What's in it?"*

AInalyst analyzes it and returns: three functional requirements, one business problem with a metric ("recounting inventory currently takes 4 hours, needs to be under 30 minutes"), two business rules that need to be checked against a possible contradiction with what James said, a gap ("Sarah said nothing about mobile access, needs clarifying"), and: "Sarah mentioned Dennis from IT support. Add him to the stakeholder registry?"

The BA says "yes, add him," and Dennis is in the registry. "Save the results," and the artifact is ready.

---

## Task 4.3: Confirm Elicitation Results

### Brief description

The BA checks the quality of the collected material **before** moving forward. This is internal work, not sign-off with the stakeholder, but a review of the BA's own records: are there contradictions, gaps, or vague wording?

### BA pain points

**"Done" does not equal "high quality."** The BA processed the interview, created an artifact, and considers it ready to move forward. But the artifact may contain wording like "the system should be user-friendly" (not testable), requirements without a source (where did this come from?), and conflicts that were missed during analysis. This surfaces later, when it's more expensive to fix.

**Requirements quality criteria are abstract.** BABOK gives 5 criteria (completeness, correctness, consistency, unambiguity, testability), but applying them to a specific text takes experience. A junior BA doesn't know exactly how to do this. A senior BA knows, but spends time on it.

**Clarifying questions are formulated poorly.** The BA sees that something needs to be clarified with the stakeholder, but phrases the question in BA jargon or too broadly. The stakeholder doesn't understand exactly what's needed, answers vaguely, and there's still no specificity.

**There's no formal moment of "closing" an artifact.** The BA works with the material, adding to it, editing it, and it's unclear when it's "done." Requirements go into analysis in a half-raw state, and problems are discovered only there.

### What we built

**Review against the 5 BABOK criteria with color-coded severity.** `run_consistency_check` reviews the artifact against each of the five criteria and, for every issue found, returns: the criterion, the severity (🔴/🟡/🟢), a specific example from the text, and a recommendation for what to do. Final verdict: ready / conditionally ready / 🔴 needs rework.

**Formulating questions for the stakeholder.** When issues are found, AInalyst formulates specific, short clarifying questions: no BA jargon, grouped by recipient, with a note on why it matters. The BA takes them and asks directly, or sends them by email.

**Final recording of the confirmed result.** `save_confirmed_elicitation_result` closes open issues and saves the final artifact with a confirmation date. This artifact is the official input for Tasks 6.1 and 6.3; the platform knows it has been verified.

### Value for the BA

**Problems are caught at the cheapest possible stage.** Fixing vague wording in a 4.3 artifact means clarifying one sentence with the stakeholder. Discovering it in 5.2 while updating a requirement means revisiting an already-built traceability graph. 4.3 is insurance against a cascade of errors in Chapter 5.

**A junior BA works like a senior one.** Quality criteria are applied systematically, not from memory. The platform won't let "should be user-friendly" slip through: it's guaranteed to be flagged as an ambiguity issue.

**The BA knows for certain that the artifact is ready.** There's an explicit moment: `save_confirmed_elicitation_result` with a date. Before that, it's work in progress. After, it's closed. No uncertainty about "well, it's probably good enough."

### How to use it: an example

The BA says: *"Here's my artifact from the interview with Sarah [text]. Check whether it's ready to move forward."*

AInalyst reviews it and returns: "🟡 FR-003: 'the system should work quickly,' has no specific metric. I recommend clarifying with Sarah: 'What is the maximum system response time that's acceptable to you, 3 seconds, 5 seconds?'" One issue, one specific action. The BA checks with Sarah, gets the answer "no more than 3 seconds," updates the artifact, and says "close it." The artifact is confirmed.

---

## Task 4.4: Communicate BA Information

### Brief description

The BA adapts finished artifacts for different audiences, chooses the right format and delivery channel, records the fact that a communication happened, and checks the schedule: who hasn't been contacted in a while, whose trigger has fired.

### BA pain points

**"The same requirements for everyone."** The BA sends the same document to the manager, the developer, and the tester. The manager sees technical details and doesn't understand why they need this. The developer doesn't see acceptance criteria. The tester doesn't see edge cases. Everyone comes back to the BA with questions, because they got something other than what they needed.

**The BA doesn't know what language to use with this particular audience.** A business sponsor needs ROI and business risks. An architect needs integrations and NFRs. A tester needs edge cases. These are different documents from the same source, and the BA writes them by hand, from scratch, every time.

**"Who did I last write to?"** The BA runs projects with 5 to 15 stakeholders. Each has their own communication schedule and their own triggers. This is impossible to keep in your head. Someone has been waiting two weeks for an update, and the BA didn't notice.

**The fact of communication is never recorded anywhere.** Sent the report, good. But when, to whom, in what format, whether there were questions, none of this is logged. In a conflict, there's no way to prove the information was delivered on time.

**A Blocker still gets the standard report.** A stakeholder who is actively against the project gets the same document as everyone else. There's no extra section on "why this matters specifically to you," no adaptation to their objections.

### What we built

**Audience adaptation with a single command.** `prepare_communication_package` takes a source artifact and the recipient's role and returns a repackaged document in the right language. The content doesn't change, the form does: irrelevant details are removed, what matters to that role is added, the tone shifts.

**An adaptation table for 5 roles.** Built into SKILL.md: business sponsor, manager, developer, architect, tester. For each role: what to remove, what to add, what tone to use. For a Blocker, add a section on "why this matters to you."

**The level of detail comes from Task 3.4, when it was planned.** If the BA recorded a planned level (Summary / Standard / Detailed) for this audience back in 3.4, `prepare_communication_package` states it in the package and adds an explicit include/leave-out checklist. The audience can be matched by its role archetype or by a stakeholder's job title from the registry — whichever the 3.4 plan used. If no level was planned for this audience, the package is built exactly as it would have been before this existed.

**Format and channel recommendation.** With high influence and a negative attitude, a 1:1 meeting is recommended instead of a written message. For a standard update, email. This isn't something you can guess reliably without a system; the platform makes the choice deliberate.

**A communication log.** `log_communication` records every instance of information being delivered: to whom, what, when, through which channel, whether follow-up is needed. This is both an evidence trail and a management tool.

**Schedule checking.** `check_communication_schedule` looks at the registry from 3.2: who hasn't been contacted in a while (per schedule) and whose trigger has fired (new requirements, a discovered risk). It returns a prioritized list: who to write to today.

### Value for the BA

**Everyone gets what they need, without extra effort from the BA.** One source artifact turns into 4 different documents in a few minutes. The BA doesn't write each one by hand. This reduces the number of clarifying questions from recipients, since they get the right format right away.

**The BA stops being a bottleneck.** When everyone gets a document they can understand, the questions "what does this mean?" and "can you explain?" disappear. Stakeholders read the artifact and make decisions instead of waiting for a verbal explanation from the BA.

**No one falls out of the communication loop.** `check_communication_schedule` is "don't forget to write to James" implemented at the system level. This matters especially during periods of intense work, when it's easy to miss that someone hasn't gotten an update in a while.

**Provability.** The communication log is the BA's protection in a conflict. "You never warned us about this risk" is answered with "here's the message from February 3rd, here's the read date." A professional position.

---

## Task 4.5: Manage Stakeholder Collaboration

### Brief description

A cross-cutting task throughout Chapter 4. The BA diagnoses stakeholder engagement problems, records decisions made, saves meeting minutes, and works through conflicts. It's not called on a schedule, but when something has gone wrong or an important moment needs to be recorded.

### BA pain points

**"Something's wrong, but it's not clear what."** A stakeholder has started avoiding meetings, or agrees but doesn't follow through, or unexpectedly became aggressive at the last meeting. The BA senses something is off but doesn't know how to interpret it or what to do. The problem accumulates.

**Decisions get made, and then forgotten.** At a meeting, everyone agreed that FR-005 moves to the next release. A month later, developers ask "why aren't we doing FR-005?" and no one remembers. "Remember, we agreed" is not documentation.

**Meeting minutes are a waste of time.** The BA knows minutes should be written. But it takes half an hour after every meeting, and the result is often just a retelling of the conversation with no structure. Action items get lost in the text, owners aren't specified, there are no deadlines.

**A conflict between stakeholders leaves the BA alone with the problem.** The sponsor wants one thing, the head of development wants another. The BA is in the middle, without tools to analyze the situation. They improvise. Sometimes it works, sometimes it doesn't.

**Changes in attitude are never recorded anywhere.** A stakeholder who was a Champion has become a Blocker. The registry still says Champion. The next time the project is handed off, the new colleague doesn't understand the situation.

### What we built

**Engagement signal diagnosis.** The BA describes the stakeholder's behavior, and AInalyst classifies the signal (🟢/🟡/🔴), names 2 to 3 likely causes, and suggests specific tactics for each. This isn't guesswork, it's pattern analysis grounded in BABOK stakeholder-management methodology.

**Decision Log.** `log_decision` records every decision made, with context: what was decided, why, what alternatives were considered, who made the decision, and how it affects requirements. Three months later, any "why did we do it this way" question has an answer.

**Structured meeting minutes.** `save_meeting_notes` takes notes in any format and returns: participants, agenda, key discussion points, decisions made, action items (action plus owner plus deadline), and open questions. Minutes are ready in 2 minutes instead of 30.

**Conflict analysis.** AInalyst identifies the type of conflict (priority-based, resource-based, conceptual, or territorial), surfaces the parties' real interests, and suggests a facilitation strategy. The BA's role is facilitator, not judge. Personal conflicts get escalated to the PM or HR.

**A history of attitude changes.** `update_engagement_status` updates the registry while preserving history: was, became, reason, planned action. This is the project's living memory.

### Value for the BA

**Early diagnosis saves relationships.** A warning signal noticed at the 🟡 level ("started replying to emails less often") is a manageable situation. The same signal at the 🔴 level ("openly sabotaging the changes") is a crisis that requires PM or HR intervention. Between the two is a matter of weeks. The platform helps catch that transition before it's missed.

**The Decision Log is the BA's insurance.** For any "why did we decide this" question, there's an answer backed by data: date, context, alternatives, who decided. This is professional protection in the event of a conflict or a team change.

**Minutes in 2 minutes instead of 30.** The BA takes notes during the meeting in whatever format is convenient. After the meeting, they hand them to AInalyst and get back structured minutes with action items. They send them to participants. This is actually achievable after every meeting, unlike "I'll sit down and write proper minutes later."

**Conflict becomes a workable task.** With an analysis tool in hand, a conflict stops being a vague threat and becomes a task with a typology, the parties' interests, and resolution strategies. The BA knows what to do, and does it professionally.

### How to use it: an example

The BA notices that Michael (the head of IT, who was initially skeptical) unexpectedly started actively supporting the project at the last meeting, but immediately afterward wrote an email to the PM raising objections, bypassing the BA.

*"Michael agrees at the meeting, but then writes emails to the PM with objections. What's going on?"*

AInalyst: "🟡 Signal. Two likely scenarios: 1) Michael doesn't feel his opinion is genuinely being taken into account at meetings, so he agrees publicly but tries to influence things privately. 2) He has specific concerns he doesn't want to voice in front of the group. I recommend a short 1:1 with Michael, with no agenda, just to hear his real position. Update his status in the registry?"

The BA holds the 1:1 and learns that Michael has a specific fear about the workload on his team. The problem turns out to be solvable; no one had simply asked. They update the status in the registry: was "skeptic," became "on board, needs monitoring."

---

## Final synthesis for Chapter 4

**The overall value of Chapter 4 is the quality of the raw material for everything else.** Chapter 4 produces what the entire project is built on: requirements, stakeholder profiles, recorded decisions, minutes. If this raw material is low quality, Chapters 5, 6, and 7 are built on an unreliable foundation.

**The platform removes mechanical load and reinforces analytical work.** Structuring a transcript, finding gaps, checking quality, adapting for an audience, writing minutes: all of this is mechanical work that the BA does instead of analytical work (making decisions, building relationships, facilitating). The platform takes the mechanical part off the BA's hands.

**The iterative nature of Chapter 4 makes automation especially valuable.** While Chapter 3 tasks run once, in Chapter 4 the cycle of 4.1 to 4.2 to 4.3 to 4.4 repeats for every elicitation session. On a large project that's 20 to 30 cycles. Every hour saved on one cycle is 20 to 30 hours across the whole project.

**The BA's responsibility in Chapter 4** stays human where it should: the quality of stakeholder relationships, facilitating conflicts, making analytical decisions. The platform takes on structuring, formatting, tracking, and recording.
