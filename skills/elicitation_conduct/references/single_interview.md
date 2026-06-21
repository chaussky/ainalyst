# Scenario A — Analysis of a single interview / workshop / notes

## Input data

The BA provides one of the following formats:
- An interview transcript (dialogue text)
- Notes from an interview or workshop
- Questionnaire answers
- An audio/video transcription (as text)

---

## Analysis algorithm (follow strictly, step by step)

### Step 1 — Structuring the stakeholder profile

Extract from the material:

| Field | What to look for |
| :--- | :--- |
| Role in the project | Title, function, area of responsibility |
| Type of involvement | Decision maker / Influencer / End user / Expert |
| Level of influence | High / Medium / Low + rationale |
| Level of interest | High / Medium / Low + rationale |
| Attitude toward the project | Champion / Neutral / Blocker + indicators |
| Key expectations | What the stakeholder wants to get from the project |
| Main concerns | What they fear, what might block the project |

---

### Step 2 — Extracting adjacent stakeholders and an expansion map

The stakeholder registry is a living document. Every interview should add to it.
Your task: find all mentioned people, roles, departments, and systems in the
transcript, and turn this into a concrete "who is next" list.

**2a. Adjacent stakeholder profile**

For each one mentioned, record:

| Field | What to look for |
| :--- | :--- |
| Who they are | Name, role, department |
| How they interact | With the current stakeholder and with the project |
| Criticality | High / Medium / Low |
| Potential conflict of interest | If there are signals |
| Registry status | New / Already known / Needs clarification |

**2b. Stakeholder expansion map**

This is the key question after every interview: **who else?**

Actively look in the text — not just for direct mentions, but also indirect signals:
- "we coordinate this with..." -> there is an approving stakeholder
- "this affects the work of..." -> there is an impacted party
- "this used to be handled by..." -> there is a historical participant
- "that is not my decision..." -> there is a hidden decision maker
- names of departments, systems, roles without names -> there are unknown stakeholders

For each one found:

```
Stakeholder: [who / role / department]
Source: via [name/role of the current stakeholder]
Why important: [how they relate to the project]
Coverage priority: Urgent / As planned / In question
Status: New / Already in the registry
Recommended format: Interview / Workshop / Written request
```

**2c. Questions to expand the registry**

If the BA has not yet asked these questions of the stakeholder, flag them as a recommendation:
- "Who do you coordinate changes to this process with?"
- "Who else uses the results of this work?"
- "Whose work will change if we implement this?"
- "Who could block or slow down the project?"
- "Are there external parties — partners, regulators, customers?"

After filling this in, use the MCP tool `update_stakeholder_registry`
to update the project's live registry.

---

### Step 3 — Needs and pain points

For each pain point, extract:

```
Pain point: [brief name]
Description: [context and essence of the problem]
Frequency: [how often it occurs]
Business impact: [what the company / person loses]
Suspected cause: [if the stakeholder named it, or if it is obvious]
Quote: [verbatim, if there is a strong statement]
```

Focus on problems, not solutions. If the stakeholder immediately proposes a
solution, record it separately as a "proposed solution," not as a requirement.

---

### Step 4 — Requirements

Group by type:

**Functional Requirements (FR)**
What the system must do. Format: "The system shall [action]".

**Non-Functional Requirements (NFR)**
Performance, security, availability. Only with a measurable criterion.

**Constraints**
Technical, budgetary, time, or regulatory boundaries.

**Business rules**
Rules the system must follow (calculations, logic, policies).

For each requirement:
- Explicit (stated directly by the stakeholder) vs. Implicit (inferred from context)
- Priority if specified, otherwise "not defined"

---

### Step 5 — User Stories

For each significant requirement:

```
As a [role]
I want [goal / functionality]
So that [business value]

Acceptance Criteria:
- GIVEN [context]
  WHEN [action]
  THEN [result]

Priority: High / Medium / Low / Not defined
Notes: [assumptions, risks, related requirements]
```

Do not invent Acceptance Criteria if they do not follow logically from the
material. It is better to write "needs clarification" than to guess.

---

### Step 6 — Completeness analysis (Gap Analysis)

This is a key step. Check each block of the profile:

| Block | Status | What is not covered |
| :--- | :--- | :--- |
| Role and context | Complete / Partial / Empty | ... |
| Influence and interest | | |
| Adjacent stakeholders | | |
| Needs and pain points | | |
| Requirements | | |

---

### Step 7 — Analysis of "blind spots" and hidden signals

**This is the most analytical step. It requires interpretation, not just facts.**

#### 7a. Where the stakeholder held back

Signs of something left unsaid:
- A topic is raised but quickly dropped ("well, that is a separate story...")
- Vague phrasing where they could have been specific
- "It is hard to explain," "that is specific to our process" without details
- An answer to "why" replaced with an answer to "what"

For each case, specify:
```
Signal: [quote or description of the moment]
What might be hidden: [hypothesis]
BA recommendation: [how to surface this in the next session]
```

#### 7b. Where the BA did not "push further"

Signs of unresolved topics:
- The stakeholder mentioned something important, but the next question went elsewhere
- No specific example was requested (the stakeholder spoke abstractly)
- "How often?", "Who else is involved?", "What happens next?" — was not asked
- A pain point was named but its business impact was not clarified

For each case:
```
Moment: [where in the interview this occurred]
Missed question: [what should have been asked]
Why it matters: [what this would reveal]
```

#### 7c. Internal contradictions

The stakeholder said A in one place and not-A in another.
This is not necessarily a lie — the context may differ, or the person may not
have settled on a position themselves.

```
Contradiction: [what versus what]
Quotes: [verbatim from the text]
Hypothesis: [why this might have happened]
Clarifying question: [how to resolve this]
```

#### 7d. Political and emotional signals

- A sudden shift in tone on certain topics
- Mentions of other people / departments with a negative connotation
- "That is not my decision," "no one asked me about that"
- Clear defensiveness about their own territory, or conversely, distancing

These signals are important for understanding the stakeholder's real attitude
toward the project.

---

### Step 8 — BA recommendations

A concrete list of actions following the analysis:

```
## Recommendations for the BA

### Needs clarification from this stakeholder
1. [topic] — [specific question] — [why it matters]

### Needs elicitation from other stakeholders
1. [topic] — [who to ask] — [specific question]

### Needs documentary confirmation
1. [what to verify] — [where to look]

### Is a follow-up interview necessary?
Yes / No — [rationale]
```

---

### Step 9 — Requirements maturity assessment

| Criterion | Rating | Comment |
| :--- | :--- | :--- |
| Clarity | Low / Medium / High | |
| Completeness | | |
| Value (business value) | | |
| Feasibility | | |
| Testability | | |

**Overall maturity level:** Low / Medium / Good / High

---

## Final report format

```markdown
# Elicitation Results (Unconfirmed)
**Stakeholder:** [role]
**Session date:** [date]
**Session type:** Interview / Workshop / Questionnaire
**Status:** Unconfirmed results (→ passed to 4.3)

## 1. Stakeholder profile
[from Step 1]

## 2. Adjacent stakeholders
[from Step 2]

## 3. Needs and pain points
[from Step 3]

## 4. Requirements
[from Step 4]

## 5. User Stories
[from Step 5]

## 6. Completeness analysis
[from Step 6]

## 7. Blind spots and hidden signals
[from Step 7 — things left unsaid, unresolved topics, contradictions, signals]

## 8. BA recommendations
[from Step 8]

## 9. Requirements maturity assessment
[from Step 9]
```
