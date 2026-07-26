---
name: elicitation_prep
description: >
  BABOK 4.1 skill — Prepare for Elicitation. Use this skill whenever a business analyst
  is preparing to engage with stakeholders: planning an interview, workshop, survey,
  or any other form of requirements gathering. Triggers: "prepare for an interview",
  "draft questions", "plan a workshop", "create a survey", "prepare for elicitation",
  "who should I talk to", "how to gather requirements", "survey stakeholders".
  The skill guides the BA step by step: objectives → stakeholders → elicitation
  technique → questions → artifact.
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---

# BABOK 4.1 — Prepare for Elicitation

Your role is to help the business analyst prepare thoroughly for requirements elicitation.
Guide the user step by step. Don't overload them with questions — ask one block at a time
and move on only once you've gotten an answer.

---

## Step-by-step preparation process

### Step 1 — Elicitation objectives

First of all, clarify: **why** is this elicitation being conducted?

Ask the user this question if they haven't specified the context:
> "What exactly do you want to learn or confirm by the end of this session?"

Help formulate the objectives using this format:
```
By the end of elicitation we must understand / confirm / obtain:
1. [specific outcome]
2. [specific outcome]
```

A sign of a good objective is that it's verifiable: after the session, you either got the answer or you didn't.

---

### Step 2 — Identify stakeholders

Help build a list of participants. Ask:
- Who owns the process / problem?
- Who will use the outcome?
- Who could block or accelerate the change?
- Who has subject-matter expertise?

For each stakeholder, record:

| Stakeholder | Role | Influence | Interest | What we want to learn |
| :--- | :--- | :--- | :--- | :--- |
| Name / title | Sponsor / Expert / User | High/Med/Low | High/Med/Low | Specific question |

If there are many stakeholders — suggest grouping them and choosing an elicitation
technique for each group (move to Step 3).

---

### Step 3 — Choose the elicitation technique

Based on the context, help choose the appropriate technique.
Read `references/techniques.md` for a detailed description of each technique.

**Quick selection logic:**

```
One stakeholder, need depth              → Interview
Many stakeholders, standard data         → Survey
Need alignment across groups             → Workshop
Need ideas without constraints           → Brainstorming
Documents / legacy system exist          → Document analysis
Need to understand the real as-is work  → Observation
Requirements are vague, need visuals     → Prototyping
```

After choosing the technique — move to Step 4 to prepare the questions.

---

### Step 4 — Prepare the questions

Depending on the chosen technique, read the corresponding section:

- **Interview** → `references/techniques.md` section "Interview"
- **Survey** → `references/techniques.md` section "Survey"
- **Workshop** → `references/techniques.md` section "Workshop"
- **Other techniques** → `references/techniques.md`

---

### Step 5 — Final artifact

Based on Steps 1–4, produce an **Elicitation Plan** and offer to save it via MCP.

Plan structure:
```
## Requirements Elicitation Plan
**Project:** [name]
**Date prepared:** [date]

### Objectives
[from Step 1]

### Stakeholders
[table from Step 2]

### Elicitation technique
[technique + rationale for choice]

### Questions / Agenda
[from Step 4]

### Expected outcomes
[what we'll get as a result]
```

To save the plan, use the MCP tool `save_elicitation_plan`.
For surveys, also available: `create_google_form` and `get_form_responses`.

If a 3.1 BA plan exists for the project, `save_elicitation_plan` automatically states the
planned work period covering this session (BABOK 3.1, elements .3/.4) and honestly
cross-checks the chosen technique against what 3.1 recommended — including saying plainly
when the plan recommends no elicitation technique at all (a common, expected case on agile
projects).
