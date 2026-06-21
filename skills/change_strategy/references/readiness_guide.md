# readiness_guide.md — Assessing Organizational Readiness for Change

## 1. Why assess readiness

**The problem:** BABOK says "assess organizational readiness," but doesn't say how.
The BA either writes a narrative like "generally ready" or skips this step entirely.

**Why this is critical:**
The most expensive project failures aren't technical.
According to McKinsey (State of the Art of Change Management), 70% of transformations
fail to meet their goals due to organizational causes: resistance, lack of skills,
or absence of sponsor support.

A readiness assessment is the **insurance policy** of a change strategy.

---

## 2. Six dimensions of readiness (ADR-079)

### 2.1 `leadership_commitment` — Leadership commitment

**What it assesses:** How much top management genuinely (not just in words) supports the change.

**Signals of high readiness (4–5):**
- The sponsor allocates time to the project (not just money)
- Middle managers are engaged as champions
- There are public statements about the priority of the change

**Signals of low readiness (1–2):**
- The sponsor has delegated everything downward and is "out of the loop"
- Competing initiatives without prioritization
- High turnover among key stakeholders

---

### 2.2 `cultural_readiness` — Cultural readiness

**What it assesses:** How well the organizational culture accepts change.

**Signals of high readiness (4–5):**
- Similar changes were successfully implemented in the past
- Employees see the value proposition and say "we need this"
- A culture of experimentation that tolerates mistakes

**Signals of low readiness (1–2):**
- "That's not how we do things" — heard at every meeting
- Previous changes are perceived as failures
- Fear of losing one's job / position due to automation

---

### 2.3 `resource_availability` — Resource availability

**What it assesses:** Whether there are enough people, time, and money for implementation.

**Signals of high readiness (4–5):**
- Budget is approved and reserved
- Key people are dedicated to the project (not "whenever they have time")
- No competing projects for the same resources

**Signals of low readiness (1–2):**
- "This is extra on top of regular work" for all participants
- Budget is not approved or depends on future decisions
- Key experts are tied up on other critical projects

---

### 2.4 `operational_readiness` — Operational readiness

**What it assesses:** Whether business processes and the operating environment are ready to accept the change.

**Signals of high readiness (4–5):**
- Processes are documented and stable (there's a baseline to change from)
- Training procedures are prepared
- There's a support plan for the transition period

**Signals of low readiness (1–2):**
- Current processes are chaotic — "you can't change what doesn't exist"
- No documentation of as-is processes
- The change period coincides with peak load (year-end, seasonal)

---

### 2.5 `technical_readiness` — Technical readiness

**What it assesses:** Readiness of the IT infrastructure, team, and architecture.

**Signals of high readiness (4–5):**
- Infrastructure meets the requirements of the new solution
- The IT team has the competencies, or a plan to acquire them
- Technical debt is manageable

**Signals of low readiness (1–2):**
- Outdated infrastructure requires parallel upgrades
- Key competencies are missing (and there's no hiring/training plan)
- Critical integrations are unknown or poorly documented

---

### 2.6 `change_history` — Change history (ADR-079)

**What it assesses:** How capable the organization is at carrying out change — based on past experience.

**Why this is a separate dimension (not part of culture):**
- Culture is about "do they want to"
- Change_history is about "do they know how" (independent of willingness)
- An organization can be culturally ready but lack experience managing large transformations

**Signals of high readiness (4–5):**
- The last 2–3 significant changes were completed successfully
- Mature change management practices are in place
- BA / PM functions are well developed

**Signals of low readiness (1–2):**
- The last major rollout failed (and there was no retrospective)
- No dedicated change management function
- This project is the first experience of this scale

---

## 3. Scoring scale (1–5)

| Score | Description | What to do |
|------|----------|------------|
| **5** | Fully ready | No obstacles |
| **4** | Ready with minor caveats | Monitoring, minimal measures |
| **3** | Partially ready, gaps exist | A concrete remediation plan is needed |
| **2** | Serious gaps | A preparatory stage is required |
| **1** | Critically not ready | Change is impossible in the current state |

---

## 4. Final readiness_score and verdict

```
readiness_score = arithmetic mean of the 6 dimensions
```

| Score | Verdict | Recommendations |
|-------|---------|--------------|
| ≥ 4.0 | `ready` | Ready for implementation |
| 2.5–3.9 | `proceed_with_caution` | Preparatory measures needed; consider pilot_first or phased |
| < 2.5 | `not_ready` | A separate organizational readiness program is required |

---

## 5. Industry benchmarks

### Large bank / public sector / pharmaceutical
**Typical profile:**
- leadership_commitment: 3–4 (strong governance)
- cultural_readiness: 2–3 (high resistance)
- technical_readiness: 2–3 (legacy systems)
- change_history: 3 (processes exist, but slow)

**Recommendations:** Invest time in cultural_readiness. phased is the preferred strategy.

### Mid-size retail / e-commerce
**Typical profile:**
- cultural_readiness: 3–4 (accustomed to change)
- resource_availability: 2–3 (competition for IT resources)
- operational_readiness: 2 (peak periods create constraints)

**Recommendations:** Plan launch dates outside of peak periods. big_bang or phased are both acceptable.

### Startup / digital company
**Typical profile:**
- cultural_readiness: 4–5 (culture of experimentation)
- change_history: 2–3 (young company, little experience with large changes)
- resource_availability: 2–3 (always "too much going on")

**Recommendations:** pilot_first is ideal for validation. Don't overrate change_history.

### Manufacturing / industrial
**Typical profile:**
- operational_readiness: 1–2 (no documentation, everything is "in people's heads")
- cultural_readiness: 2 (high resistance among operators)
- technical_readiness: 1–3 (depends on the age of the plant)

**Recommendations:** Start with operational_readiness. Without it, the other dimensions don't matter.

---

## 6. How to ask the BA questions to assess each dimension

If the BA doesn't know how to assess a dimension — use these questions:

**leadership_commitment:**
> "Does your sponsor personally attend key project meetings? How often?"
> "Are there middle managers who openly support the change?"

**cultural_readiness:**
> "When was the last time the company made a similar change? How did it feel to people, subjectively?"
> "Have you heard phrases like 'that's not how we do things' or 'that's not our style'?"

**resource_availability:**
> "Which key people are dedicated to the project full-time? Part-time?"
> "Has the budget been formally approved, or is it still 'in progress'?"

**operational_readiness:**
> "Are there documented as-is processes for what we're changing?"
> "When are the business's peak loads? Do they overlap with the planned rollout?"

**technical_readiness:**
> "Has the team already worked with the technologies of the new solution?"
> "Are there unknown integrations that might 'surface' unexpectedly?"

**change_history:**
> "Tell me about the last major rollout — what went well, what went poorly?"
> "Is there a dedicated change manager role in the company, or is it always 'the BA's job'?"
