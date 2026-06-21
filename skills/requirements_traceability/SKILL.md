---
name: requirements_traceability
description: >
  BABOK 5.1 skill — Trace Requirements. Use this skill when the BA wants to
  build or update the graph of links between project artifacts, add a traceability
  link, run an impact analysis, or export a traceability matrix.
  Triggers: "trace requirements", "traceability matrix", "requirement links",
  "impact analysis", "where did this requirement come from", "coverage", "requirements graph".
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: BABOK 5.1 — Trace Requirements
**Task:** managing requirements traceability throughout the life cycle.  
**MCP server:** `requirements_traceability_mcp.py`  
**Reference:** `references/traceability_guide.md`

---

## What this task is about

Traceability is a **graph of links** between all project artifacts.

```
Business need
  └─[derives]→ Business requirement (BR)
       └─[derives]→ Stakeholder requirement (SR)
            └─[derives]→ Solution requirement (FR/NFR)
                 ├─[satisfies]← Component / module
                 └─[verifies]← Test (TC)
```

Plus horizontal links: `depends` between requirements at the same level.

**Core value:** when a CR arrives or a requirement changes, the BA instantly
sees what's affected — which requirements, tests, components. Without traceability, it's guesswork.

---

## When this skill is activated

- BA adds a new requirement to the project
- A requirement has changed (CR or clarification)
- Need to assess the impact of a change (→ handed off to 5.4)
- Need to check coverage before prioritization (5.3) or approval (5.5)
- Request for a traceability matrix for stakeholders or an audit

---

## Three modes of operation

### Mode A — Initial traceability for a new requirement

**When:** a confirmed requirement arrives from 4.3, or a new requirement comes in via a CR.

Algorithm:
1. Determine the **requirement type**: `business` / `stakeholder` / `solution` / `transition`
2. Ask: **where did it come from?** → find the parent for the `derives` link
3. Ask: **what does it follow from, or what does it require?** → horizontal `depends`
4. Ask: **which component implements this?** (if already known) → `satisfies`
5. Ask: **which test verifies this?** (if already known) → `verifies`
6. Call `add_trace_link` for each link
7. If the repository is being created for the first time → call `init_traceability_repo` first

> 📌 If there's no answer to questions 4-5, that's fine. `satisfies` and `verifies`
> links can be added later. An orphan requirement without `satisfies`/`verifies` is an expected
> state at early stages. An orphan without `derives` is already a problem.

### Mode B — Maintaining traceability (requirement change)

**When:** a requirement has been updated (version, status, content).

Algorithm:
1. Update the requirement record: new version, new status
2. Call `run_impact_analysis` — get the list of all affected artifacts
3. For each affected artifact: is the link still valid?
   - If the link is stale → update `rationale` or remove it via `add_trace_link` with the `remove` flag
   - If new links have appeared → add them
4. If the change arrived as a CR → the `run_impact_analysis` result is passed to 5.4
   for expert assessment: accept or not, what's the cost

> ⚠️ Mode B is the most common cause of "dead traceability." The BA updates a requirement
> but forgets to update the graph. Claude should remind them: "this requirement changed —
> the links need to be checked."

### Mode C — Coverage audit

**When:** before prioritization (5.3), before approval (5.5), after a series of CRs.

Algorithm:
1. Call `check_coverage`
2. Interpret the results:
   - 🔴 **Orphan with no source** → clarify the business justification or freeze it
   - 🟡 **No implementation** → check with the developer or add to the backlog
   - 🟡 **No test** → check with QA or create a test
   - 🟢 **Full coverage** → ready for the next step
3. Make a decision for each problematic requirement
4. If needed → `export_traceability_matrix` for a report

---

## Formality levels — choose before you start

If the project context is unknown — **ask the BA**. Picking the right preset saves
hours of unnecessary work or guards against missed links.

| Question for the BA | If the answer is... | Recommend |
|---------------|---------------|------------|
| Are there regulatory requirements? (GDPR, local law, ISO) | Yes | Full |
| External audit or compliance? | Yes | Full |
| Team > 20 people? | Yes | Standard → Full |
| Is there a dedicated QA function? | Yes | Standard |
| Agile, sprints, startup? | Yes | Lite |

**The BA always makes the final decision.** The skill recommends, it doesn't impose.

Read the preset details: `references/traceability_guide.md` → section "Formality presets"

---

## Integration with other tasks

**Where requirements come from:**
- `4.3 save_confirmed_elicitation_result` → confirmed artifacts → add to the repository (Mode A)
- `4.2 save_cr_elicitation_analysis` → requirements from a CR → update traceability (Mode B)

### Mapping from 4.3 into the traceability repository

The 4.3 artifact stores requirements in the structure `{functional: [...], non_functional: [...]}`.
When adding to the traceability repository, convert as follows:

| Field in 4.3 | Field in the 5.1 repository |
|-----------|------------------------|
| `functional[].id` → `FR-001` | `id` |
| `"FR"` / `"NFR"` | `type: "solution"` |
| `functional[].statement` | `title` |
| `"confirmed"` (final_readiness) | `status: "confirmed"` |
| path to the 4.3 file | `source_artifact` |

Business requirements (BR) and stakeholder requirements (SR) come from earlier elicitation sessions (4.2).
Their type: `"business"` and `"stakeholder"` respectively.

**Where the results go:**
- `5.3` Prioritization → account for `depends` links: a requirement can't be prioritized above its dependency
- `5.4` Change assessment → pass the `run_impact_analysis` result as technical input
- `5.5` Approval → use `export_traceability_matrix` for the sign-off package
- `6.x` User Stories / Use Cases → every artifact traces back to an FR/SR

---

## MCP tools

| Tool | Mode | When to call |
|------------|-------|----------------|
| `init_traceability_repo` | A | Once, at project start |
| `add_trace_link` | A, B | For every new/changed requirement or link |
| `run_impact_analysis` | B | A change has arrived, need to understand what's affected |
| `check_coverage` | C | Audit before prioritization / approval / after a CR |
| `export_traceability_matrix` | C | Need a matrix for stakeholders or an audit |

---

## What 5.1 does NOT do

- **Does not prioritize** requirements — that's 5.3
- **Does not assess** whether to accept a CR — that's 5.4 (5.1 provides technical input)
- **Does not formally approve** requirements — that's 5.5
- **Does not create** requirements — that's 4.2/4.3
- **Does not manage** code configuration — that's outside BABOK

---

## Quick start for a new project

```
1. BA hands over confirmed artifacts from 4.3
2. Choose a formality level (Lite / Standard / Full)
3. init_traceability_repo — create the repository
4. For each requirement: add_trace_link (Mode A)
5. check_coverage — make sure there are no orphan requirements
6. export_traceability_matrix — save the initial state
```
