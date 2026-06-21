# Reference: Prioritization Conflicts and Their Resolution (BABOK 5.3)

## Three types of conflicts

| Type | Description | Frequency | Complexity |
|-----|----------|---------|-----------|
| **Cross-stakeholder** | SH-A says Must, SH-B says Won't | High | Medium |
| **Dependency violation** | Must requirement depends on a Won't | Medium | High |
| **Priority inflation** | >60% of requirements are Must | High | Medium |

---

## Type 1 — Cross-stakeholder conflict

### Detection

Conflict = scores diverge between stakeholders by 2+ MoSCoW categories.

| Divergence | Severity |
|-------------|-------------|
| Must vs Should | 🟡 Moderate — usually resolved through discussion |
| Must vs Could | 🟠 Serious — needs facilitation |
| Must vs Won't | 🔴 Critical — needs a sponsor decision |
| Should vs Won't | 🟡 Moderate |

**Amplifying factor:** if both conflicting stakeholders have High influence, the conflict requires escalation to the sponsor and cannot be resolved by the BA alone.

### Resolution tactics

**1. Decompose the requirement**
A conflict often arises because the requirement is too large.
FR-001 "Personal account" → Must for one stakeholder, Could for another.
After decomposition: FR-001a "View profile" = Must, FR-001b "Edit avatar" = Could.
The conflict disappears.

**2. Clarify the benefit**
Ask each stakeholder: "What exactly happens if we DON'T implement this in the current version?"
Often a "Must" turns out to be a Must due to a misunderstanding of scope or simple habit.

**3. Weighted voting**
Applied automatically during aggregation: influence High = 3, Medium = 2, Low = 1.
The result is transparent — the BA can show the stakeholder the math.

**4. Escalate to the sponsor**
For Must vs. Won't with High/High influence — the BA does not decide alone.
Protocol: record the conflict in the Decision Log (4.5), schedule a meeting, invite the sponsor.

**5. Defer the requirement**
If the conflict cannot be resolved within a reasonable time, move it to Won't for the current session.
Record in the Decision Log: "Deferred pending additional information."

---

## Type 2 — Dependency Violation

### The core problem

If FR-B has a `depends` link from FR-A in the 5.1 repository, and:
- FR-B = Must
- FR-A = Should or lower

→ logical contradiction: a "mandatory" requirement depends on an "optional" one.

### Resolution options

| Option | When to apply |
|---------|----------------|
| **Raise FR-A to Must** | If FR-A is genuinely valuable on its own |
| **Lower FR-B to Should** | If a way was found to work without FR-B in the first version |
| **Decompose FR-B** | Extract a minimal version of FR-B that does not depend on FR-A |
| **Implement FR-A partially** | If the dependency is partial — clarify the boundary |

### Dependency chains

A BFS traversal in 5.1 may reveal that the problem runs deeper:
FR-C (Must) → FR-B (Should) → FR-A (Won't)

In this case, "raising FR-A" may force a reassessment of the entire chain.
The `run_impact_analysis` tool from 5.1 shows the full picture.

---

## Type 3 — Priority Inflation

### Signs

- > 60% of requirements are marked Must
- Almost all of one stakeholder's requirements are Must
- Must/Should are assigned without justification

### Causes

| Cause | Tactic |
|---------|---------|
| Stakeholder fears that "their" requirements won't make it in | Explain that Won't ≠ never |
| No understanding of resource constraints | Show capacity: "this sprint can fit 30 story points" |
| Requirements are too large | Decompose, then re-prioritize |
| Political pressure | Escalate to the sponsor, use WSJF to make it objective |

### "Fixed budget" tactic

An effective facilitation technique:
"We have 10 Must slots. Here's a list of 25 requirements. Pick 10."

This forces real trade-offs and reduces inflation.
The WSJF equivalent: an explicit Job Size (capacity) cap.

---

## Conflict matrix and action items for the BA

| Situation | Severity | Action for the BA |
|----------|-------------|---------------|
| Must vs Won't, both High influence | 🔴 | Escalate to the sponsor, Decision Log |
| Must vs Won't, one Low influence | 🟠 | Weighted voting, explain the math |
| Dependency violation (Must → Won't) | 🔴 | One of the 4 options above, must be documented |
| >60% Must | 🟠 | "Fixed budget" technique, rerun the session |
| One stakeholder marked everything Must | 🟡 | Individual conversation, clarify criteria |
| Should vs Could divergence | 🟢 | Weighted voting, usually resolves automatically |

---

## Documenting conflicts

**Each conflict is recorded with:**
- `req_id` — which requirement
- `conflict_type` — stakeholder_conflict / dependency_violation / inflation
- Parties to the conflict (stakeholder IDs)
- Final decision + rationale
- Who made the decision (`decided_by`)

This information:
1. Goes into the Decision Log (4.5) — for transparency and audit
2. Is stored in the prioritization session snapshot — so the BA can explain it during 5.5 (Approve)
3. Is available to the PM for the project plan

---

## Continuous prioritization — when to revisit

Per BABOK, priorities live on and change over time. Triggers for re-prioritization:

| Trigger | What to revisit |
|---------|--------------------|
| Cost estimates received from developers | All requirements — cost changes perception |
| Change Request accepted (5.4) | Affected requirements + their dependencies |
| Business context changed (strategy, market) | Full Business Value reassessment |
| Sprint/stage ended | Requirements for the next iteration |
| Requirement stability dropped (5.2: version 1.4+) | The specific unstable requirement |
| New stakeholder added to the project | Their requirements + recalculated influence weights |
