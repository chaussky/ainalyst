# Scenario B — Cross-analysis of multiple interviews

Use this when the BA provides results from two or more elicitation sessions.
This may be: different stakeholders on the same topic, or a repeat interview
with the same stakeholder after new information was received.

---

## Input data

The BA provides:
- Two or more artifacts from Scenario A (already structured)
- Or raw transcripts of multiple sessions

If raw transcripts are provided — first process each one using the algorithm
from `single_interview.md`, then perform the cross-analysis.

---

## Cross-analysis algorithm

### Step 1 — Stakeholder map and growth map

**1a. Summary table of known stakeholders**

| Stakeholder | Role | Influence | Interest | Attitude | Covered by elicitation |
| :--- | :--- | :---: | :---: | :--- | :---: |
| | | | | | Yes / No |

Identify: who is a Key Player, who is a potential Blocker, where there are unexpected allies.

**1b. Stakeholder registry growth map**

The stakeholder registry grows in a chain — each new stakeholder leads to the next.
Visualize how we found them:

```
Sponsor (known from the start)
  └── Head of Department X (mentioned by the Sponsor)
        └── Process Manager Y (mentioned by Head of Department X)
        └── Legal department representative (mentioned by Head of Department X)
  └── IT Director (mentioned by the Sponsor)
        └── System architect (mentioned by the IT Director)
```

For each stakeholder not yet covered by elicitation, specify:

| Stakeholder | Source (via whom) | Why important | Priority | Status |
| :--- | :--- | :--- | :---: | :--- |
| | | | Urgent / As planned | Not covered / Planned |

**1c. Registry blind spots**

Explicitly indicate who was mentioned in interviews but is still not covered by
elicitation, and why this is a risk to the project.

Use `update_stakeholder_registry` to update the live registry.

---

### Step 2 — Contradictions between stakeholders

This is the central step of the cross-analysis.

Look across three levels:

**Level 1 — Factual contradictions**
Stakeholder A claims X, stakeholder B claims not-X.

```
Topic: [what the contradiction is about]
Position A ([role]): [statement]
Position B ([role]): [statement]
Criticality: High / Medium / Low
Hypothesis: [why the positions diverge — different context? conflict of interest?]
How to resolve: [who to involve, what to clarify, is a workshop needed]
```

**Level 2 — Priority contradictions**
Stakeholders agree on WHAT is needed but disagree on WHAT is more important.

```
Topic: [feature / requirement]
Priority for A ([role]): High
Priority for B ([role]): Low
Impact on the project: [what happens if not aligned]
Recommendation: [escalate to a workshop / escalate to the sponsor / ...]
```

**Level 3 — Coverage gaps**
Stakeholder A talked about topic X, stakeholder B did not raise this topic.
This is not necessarily a contradiction — but a signal that the topic needs to be checked.

```
Topic: [what only one stakeholder mentioned]
Mentioned by: [who]
Not mentioned by: [who — and this is odd, because...]
Action: [ask the second stakeholder]
```

---

### Step 3 — Consolidated requirements register

Merge requirements from all interviews into a single register.
Deduplicate: the same requirement may be phrased differently by different stakeholders.

| ID | Requirement | Sources | Priority | Status | Note |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-001 | | Stakeholder A, B | High | Agreed | |
| FR-002 | | Stakeholder A only | Medium | Needs confirmation | |
| FR-003 | | Stakeholder A vs B | — | Contradiction | Different phrasing |

Statuses:
- **Agreed** — mentioned by multiple stakeholders without contradictions
- **Needs confirmation** — only one source
- **Contradiction** — conflict between stakeholders
- **In question** — implicit, needs clarification

---

### Step 4 — Political map

Sometimes contradictions between stakeholders are not technical but political.

Signs:
- One stakeholder clearly avoids mentioning another, even though they should
- One stakeholder describes another's area of responsibility differently
- Different versions of "who makes the decision"
- Someone is actively pushing a specific solution (rather than a problem)

```
Observation: [what was noticed]
Parties involved: [who]
Risk to the project: [how this could affect it]
BA recommendation: [how to work with this dynamic]
```

---

### Step 5 — Re-elicitation plan

Based on the cross-analysis, build a concrete plan:

```
## Re-elicitation Plan

### Critical questions (an answer is needed before continuing work)
1. Topic: [what]
   From whom: [stakeholder / role]
   Specific question: [wording]
   Why critical: [consequences if not clarified]

### Medium-priority questions
...

### Recommended formats
- [topic X] → follow-up interview with [whom]
- [topic Y] → workshop with [whom + whom], because alignment is needed
- [topic Z] → document analysis [which documents]
```

---

## Final cross-analysis report format

```markdown
# Elicitation Results Cross-Analysis
**Stakeholders:** [list]
**Elicitation period:** [dates]
**Status:** Unconfirmed results (→ passed to 4.3)

## 1. Stakeholder map
[summary table]

## 2. Contradictions
### 2.1 Factual contradictions
### 2.2 Priority contradictions
### 2.3 Coverage gaps

## 3. Consolidated requirements register
[table]

## 4. Political map
[observations and risks]

## 5. Re-elicitation plan
[specific questions, formats, priorities]
```
