---
name: requirements_maintain
description: >
  BABOK 5.2 skill — Maintain Requirements. Use this skill when the BA wants to
  update requirement attributes, deprecate outdated requirements, check the
  health of the registry, or find candidates for reuse in a new project.
  Triggers: "update requirement," "maintain requirements," "deprecate,"
  "requirements health," "reuse."
project: "AI-powered Platform AInalyst"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com"
---
# SKILL: BABOK 5.2 — Maintain Requirements
**Task:** keep requirements and their attributes current throughout the requirements life cycle.
**MCP server:** `requirements_maintain_mcp.py`
**Reference:** `references/lifecycle_guide.md`

---

## What this task is about

5.1 built the link graph. 5.2 keeps that graph — and the requirements themselves — from going stale.

Requirements live, change, and age. The BA's job is to act as the registry's
"caretaker": update statuses, versions, and attributes, flag what's outdated,
and identify candidates for reuse. And to do this **regularly**, not only when a CR comes in.

**Three elements per BABOK:**
1. **Maintaining content** — the requirement stays correct and current
2. **Maintaining attributes** — metadata stays current even if the content hasn't changed
3. **Reuse** — requirements are accessible and understandable for other initiatives

---

## When this skill is activated

- A requirement's status has changed (confirmed → approved, approved → on_hold...)
- A requirement is outdated or replaced by another → needs to be marked deprecated/superseded
- A CR has come in → versions of affected requirements need updating (after 5.4)
- Before prioritization (5.3) → the priority and stability attributes need to be current
- Before approval (5.5) → a clean registry is needed, free of clutter
- The BA wants to find requirements for reuse in a new initiative
- A regular "health" audit of the registry

---

## Four operating modes

### Mode A — Updating a requirement or its attributes

**When:** status, priority, owner, wording, or any other attribute has changed.

Algorithm:
1. Determine what changed: content or just an attribute?
2. If content → new version (1.0 → 1.1 or 2.0)
3. If only an attribute (status, priority) → the version does not change
4. Call `update_requirement` — updates the attributes and logs the change in the history
5. If the change came from a CR → first run `run_impact_analysis` (5.1)

> 📌 Versioning rule:
> Minor (1.0→1.1): wording clarification, change to acceptance criteria
> Major (1.0→2.0): change in substance, merging or splitting requirements
> More detail: `references/lifecycle_guide.md` → "Versioning"

### Mode B — Deprecation (obsolescence/replacement)

**When:** the requirement is no longer relevant, or has been replaced by another.

Algorithm:
1. Determine the reason: outdated on its own? Replaced by another? Removed by a CR?
2. Choose the correct final status:
   - `deprecated` — outdated, no replacement
   - `superseded` — replaced by another requirement (specify which one)
   - `retired` — project closed, requirement goes to the archive
3. Call `deprecate_requirements` — marks it and logs the reason in the history
4. Check in 5.1 whether there are active links to the deprecated requirement

> ⚠️ A deprecated requirement is not deleted from the repository — only marked.
> The history must be preserved for audit and traceability.

### Mode C — Registry health audit

**When:** before 5.3 (prioritization), before 5.5 (approval), regularly once per sprint/stage.

Algorithm:
1. Call `check_requirements_health`
2. Interpret the results:
   - 🔴 High volatility → find the root cause with the stakeholder
   - 🟡 Not updated in a long time → check currency with the owner
   - 🟡 Stuck in draft for a long time → either confirm it or freeze it
   - 🟢 Healthy requirements → ready for the next step
3. For each issue, make a decision: update, freeze, or deprecate

### Mode D — Reuse

**When:** a new initiative is starting, or the BA is looking for existing requirements.

Algorithm:
1. Call `find_reusable_requirements` with a filter by type or topic
2. For each candidate, check:
   - Worded without ties to a specific system/department?
   - Status `approved` or `implemented`?
   - Low volatility (version ≤ 1.1)?
3. Stakeholders review the selected requirements before including them in the new initiative
4. When including it → create a new record with `source` pointing to the original

> 📌 The higher the level of abstraction, the better suited for reuse.
> The requirement "The user must be able to log in" → enterprise level.
> "Login button in SAP module X" → only this initiative.

---


## Requirement attributes — minimum set

| Attribute | Required | Who fills it in | When it changes |
|---------|------------|---------------|----------------|
| `status` | Always | BA | At every transition |
| `version` | Always | BA | When content changes |
| `source` | Always | BA | Once, at creation |
| `priority` | Standard+ | BA (after 5.3) | During prioritization and CR |
| `owner` | Standard+ | BA | On assignment/handover |
| `stability` | Standard+ | BA / automatic | Recalculated by version |
| `reuse_candidate` | Standard+ | BA | On identification or audit |
| `reuse_scope` | Full | BA | When tagging for reuse |
| `complexity` | Full | BA | During initial analysis |

Full description of attributes: `references/lifecycle_guide.md` → "Requirement attributes"

> The preset is chosen in **3.4** (`plan_information_management(attributes_preset=...)`),
> and `check_requirements_health` audits exactly that set. Without a 3.4 plan the audit
> checks `owner` only. A project on `Minimum` deliberately stops being asked for an
> owner — you audit what you planned to maintain.

---

## Integration with other tasks

**Where updates come from:**
- `4.3` → status: `confirmed` (after the BA's internal review)
- `5.1 run_impact_analysis` → list of affected requirements for a CR
- `5.3` → updated priorities
- `5.4` → CR decision: which requirements change, which are deprecated
- `5.5` → status: `approved` after formal sign-off

**Where results go:**
- `5.3` — current stability and priority for correct prioritization
- `5.5` — clean registry for the approval package
- `6.x` — reuse candidates for User Stories and Use Cases
- `Confluence` — via the export hook (once `integrations/confluence_mcp.py` is connected)

---

## Hooks for external stores

After every requirement update, the MCP server calls the export hook.
Until `integrations/confluence_mcp.py` is connected, the hook returns `local_only`.
Once connected, it automatically syncs with Confluence.

Connecting the integration requires no changes to 5.2 — only adding the module.

---

## MCP tools

| Tool | Mode | When to call |
|------------|-------|----------------|
| `update_requirement` | A | Status, version, or attributes changed |
| `deprecate_requirements` | B | Requirement is outdated or replaced |
| `check_requirements_health` | C | Audit before 5.3, 5.5, after a series of CRs |
| `find_reusable_requirements` | D | New initiative, searching for existing requirements |

---

## What 5.2 does NOT do

- **Does not prioritize** — that's 5.3 (but it maintains the `priority` attribute)
- **Does not assess CRs** — that's 5.4 (but it updates requirements based on the outcome)
- **Does not give formal approval** — that's 5.5 (but it prepares the registry for approval)
- **Does not build** the link graph — that's 5.1 (but it works with the same repository)
- **Does not publish** to Confluence directly — that's `integrations/confluence_mcp.py`
