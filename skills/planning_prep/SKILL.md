---
name: planning_prep
description: >
  BABOK Chapter 3 skill — Business Analysis Planning and Monitoring. Use this skill
  whenever a business analyst is starting a new project or initiative and needs to plan
  their approach to the work. Triggers: "how should I approach this project", "which
  methodology to choose", "who are my stakeholders", "how to organize requirements work",
  "BA planning", "governance", "how to store requirements", "evaluate analysis
  effectiveness", "start business analysis", "plan the analysis".
  The skill guides the BA through the five tasks of Chapter 3: approach → stakeholders →
  governance → information management → performance evaluation.
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---

# BABOK Chapter 3 — Business Analysis Planning and Monitoring

Your role is to help the business analyst build the foundation for project work:
choose an approach, identify stakeholders, establish decision-making rules,
and organize information storage. Without this foundation, the rest of the BABOK
tasks are performed haphazardly.

Guide the user step by step. Each task is a separate step. Don't overload them with questions.

---

## The five tasks of Chapter 3

### Task 3.1 — Plan Business Analysis Approach

Help the BA choose a working methodology based on the project context.

Ask clarifying questions if the context isn't specified:
- How often do requirements change?
- How high is the uncertainty in the project?
- Are there strict regulatory requirements (compliance)?

**Selection logic:**

| Situation | Approach |
| :--- | :--- |
| Requirements are stable, low uncertainty | Predictive (Waterfall) |
| High volatility or uncertainty | Adaptive (Agile) |
| Need a balance of flexibility and control | Hybrid |
| Agile + strict compliance | Hybrid with compliance gates |

After choosing the approach — offer to save the decision via the MCP tool `suggest_ba_approach`.

---

### Task 3.2 — Plan Stakeholder Engagement

Help build a stakeholder map and choose an engagement strategy for each one.

**Important:** the stakeholder registry is a living document. At the start of a project
only 1–2 people are known (usually the sponsor). Each interview adds new ones.
The registry is never "closed" — it grows throughout the entire project.

Typical growth chain:
```
Sponsor → names managers → who name experts →
experts name adjacent departments → and so on
```

After each elicitation session the registry is updated via
`update_stakeholder_registry` (MCP task 4.2).

For each stakeholder, determine:
- Influence (High / Medium / Low) — ability to influence the project
- Interest (High / Medium / Low) — level of interest in the outcome
- Disposition (Champion / Neutral / Blocker)
- Coverage status: Identified / Planned / Not yet covered
- **Communication frequency** — how often they receive information
- **Communication trigger** — which event requires mandatory notification

**Communication schedule — matrix-based template:**

| Quadrant | Frequency | Typical triggers |
| :--- | :--- | :--- |
| High influence / High interest | After every significant step | Any decision, requirements change, risks |
| High influence / Low interest | At milestones or on request | Only critical decisions and blockers |
| Low influence / High interest | After elicitation sessions they took part in | Follow-up after interviews, status updates |
| Low influence / Low interest | Rarely, as needed | Only if directly affected |

The schedule is recorded in the stakeholder's profile and used by task 4.4
(`check_communication_schedule`) for monitoring — who hasn't been contacted in a while
and whose trigger has fired.

**Power/Interest matrix:**

| Influence ↑ / Interest → | Low | High |
| :--- | :--- | :--- |
| **High** | Keep Satisfied — inform about milestones | Manage Closely — involve in every decision |
| **Low** | Monitor — general distribution list | Keep Informed — demos, status updates |

**Questions for expanding the registry** (ask during every interview):
- "Who do you coordinate changes to this process with?"
- "Who else uses the results of this work?"
- "Whose work will change if we implement this?"
- "Who could block or slow down the project?"

Use the MCP tool `plan_stakeholder_engagement` to build the matrix.

---

### Task 3.3 — Plan Business Analysis Governance

Help establish the rules for decision-making and change control.

Key questions:
- Who makes the final decisions on requirements?
- How are changes handled — formally (CR + CAB) or flexibly (through the PO)?
- How are conflicts escalated?

**Response template by criticality:**

| Criticality | Change control | Approval |
| :--- | :--- | :--- |
| High | Formal CR → CAB | Sponsor + PO |
| Medium | PO approves via Backlog | PO + Lead BA |
| Low | Logged in Jira, verbal | Lead BA |

Use the MCP tool `plan_ba_governance`.

---

### Task 3.4 — Plan Business Analysis Information Management

Help plan where and how requirements and artifacts are stored.

Questions to discuss:
- Which tools are already used by the team?
- Is requirements traceability needed, and how detailed?
- Who has access to artifacts — only the BA or the whole team?

**Traceability levels:**

| Level | What it means |
| :--- | :--- |
| High | Business objectives → FR → Test cases → Code |
| Medium | FRs are linked to Jira tickets |
| Low | Basic requirement numbering |

Use the MCP tool `plan_information_management`.

---

### Task 3.5 — Identify Business Analysis Performance Improvements

Help identify problems in current practice and suggest improvements.

Warning signs worth paying attention to:
- Requirements change frequently even during development
- Developers complain about unclear or contradictory requirements
- There's no single place to store requirements
- Onboarding new BAs takes more than a month
- There are no requirements quality metrics

Use the MCP tool `evaluate_ba_performance` to build an improvement plan.

---

## When to use the MCP tools

All five tasks are supported by an MCP server (`skills/planning_mcp.py`). Call the tools
when you need to save an artifact or get a structured output:

| Task | MCP tool |
| :--- | :--- |
| 3.1 Plan approach | `suggest_ba_approach` |
| 3.2 Stakeholders | `plan_stakeholder_engagement` |
| 3.3 Governance | `plan_ba_governance` |
| 3.4 Information management | `plan_information_management` |
| 3.5 Performance evaluation | `evaluate_ba_performance` |
| Finalization | `save_ba_plan` |

All tools take `project_id` as the first parameter. Artifacts are saved
to `governance_plans/data/{project}_ba_plan.json` and `governance_plans/reports/`.
