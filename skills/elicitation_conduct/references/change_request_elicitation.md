# Scenario C — Elicitation in the context of a Change Request

Use this when a CR has come in and the BA needs to understand:
what changed in the understanding of the business domain,
who to re-elicit information from,
and which previously collected data is now outdated.

---

## Scenario logic

A CR is not just a change to requirements. It's a signal that:
- The stakeholder's business reality has changed
- New information has appeared that wasn't there before
- Previous elicitation was incomplete (and the CR exposed this)
- The context has changed — and old requirements need to be reconsidered

The BA's task is not just to "update the requirements," but to understand
**why** the CR came in and **what else** might change as a result.

---

## Algorithm

### Step 1 — Break down the CR

Get a description of the CR from the BA and answer these questions:

```
CR: [brief description of the change]

What exactly is changing:
- Business process? [yes/no]
- System requirements? [yes/no]
- Roles / responsibilities? [yes/no]
- External conditions (market, regulator, integrations)? [yes/no]

Change initiator: [who]
Reason for the change: [why now]
```

---

### Step 2 — Impact zone on previously collected data

Map the CR against already-collected elicitation artifacts.

| Artifact | Affected? | Nature of the change |
| :--- | :--- | :--- |
| Stakeholder profile [name] | Yes / No | Expectations / concerns have changed |
| Pain point #N | Yes / No | Outdated / intensified / new context |
| Requirement FR-XXX | Yes / No | Changing / being removed / being added |
| User Story US-XXX | Yes / No | Acceptance criteria need to be revisited |

---

### Step 3 — What is outdated

Explicitly record what can no longer be considered current:

```
Outdated artifact: [ID / name]
Why outdated: [link to the CR]
What to do with it: Update / Remove / Freeze pending clarification
```

---

### Step 4 — New elicitation questions

A CR generates new questions. For each one:

```
Question: [what needs to be clarified]
From whom: [stakeholder / role]
Why it arose: [link to the CR]
Priority: Critical / High / Medium
Format: Quick call / Follow-up interview / Written request
```

---

### Step 5 — Assessing the scope of re-elicitation

```
Number of affected stakeholders: [N]
Number of outdated artifacts: [N]
Scope of new elicitation: Minimal (1-2 calls) / Moderate / Significant

Risk: are there signs that the CR is a symptom of a deeper change?
[yes/no + rationale]

Recommendation: [what the BA should do first]
```

---

### Step 6 — Is a new workshop needed?

A workshop with multiple stakeholders is needed if:
- The CR touches the areas of responsibility of several parties
- There is a risk of conflicting interests from the change
- The change requires aligning priorities
- The scope of the change is significant

```
Workshop needed: Yes / No
Rationale: [why]
Participants: [who should attend]
Key agenda questions: [list]
```

---

## Final CR analysis report format

```markdown
# Elicitation Analysis in the Context of a Change Request
**CR:** [description]
**Analysis date:** [date]
**Status:** Requires further elicitation

## 1. CR breakdown
[essence of the change, initiator, reason]

## 2. Impact zone
[table of affected artifacts]

## 3. Outdated data
[what needs to be updated or removed]

## 4. Re-elicitation plan
[questions, stakeholders, formats, priorities]

## 5. Scope assessment
[scope of work, risks, recommendation]

## 6. Workshop
[needed or not, participants, agenda]
```
