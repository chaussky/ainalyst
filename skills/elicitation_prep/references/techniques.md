# Elicitation Techniques (BABOK 4.1)

A detailed description of each technique: when to use it, how to prepare,
what questions to ask.

---

## Contents

1. [Interview](#1-interview)
2. [Survey](#2-survey)
3. [Workshop](#3-workshop)
4. [Brainstorming](#4-brainstorming)
5. [Document Analysis](#5-document-analysis)
6. [Observation](#6-observation)
7. [Prototyping](#7-prototyping)
8. [Focus Group](#8-focus-group)
9. [Benchmarking](#9-benchmarking)

---

## 1. Interview

**When to use:**
- You need depth, not coverage
- The stakeholder has unique expertise
- The topic is sensitive (conflicts, risks, politics)
- You need to understand motivation and context, not just facts

**Two types:**

| Type | When | Characteristics |
| :--- | :--- | :--- |
| **Structured** | Need comparable answers, multiple respondents | Fixed list of questions, strict order |
| **Unstructured** | Exploratory phase, one key expert | Follow the stakeholder, questions emerge from answers |

**Preparation:**

1. Define the interview goal — one sentence: "By the end of the interview I must understand X"
2. Draft a list of topics (no more than 5–7 for a 60-minute interview)
3. For each topic — 2–3 open-ended questions
4. Prepare follow-up probing questions (see below)
5. Agree on time, format (in-person / online), duration

**Question structure:**

```
Opening (context and trust):
→ "Can you describe what a typical workday looks like for [topic]?"
→ "How long have you been working with [process / system]?"

Core (the substance):
→ "What works well in the current process?"
→ "What causes the most difficulty?"
→ "If you could change one thing — what would it be?"
→ "What outcome would mean success for this project, to you?"

Follow-up probes (going deeper):
→ "Can you give a specific example?"
→ "How often does that happen?"
→ "What happens next in that case?"
→ "Who else is involved at that point?"

Closing:
→ "Is there anything important we haven't talked about?"
→ "Who else do you think we should talk to?"
```

**Tips:**
- Silence is your tool. Don't rush to fill pauses.
- One question at a time. Compound questions ("How and why...?") confuse people.
- Take notes or record (with consent). Transcribe right after.
- The stakeholder should talk 80% of the time, you 20%.

---

## 2. Survey

**When to use:**
- Many respondents (10+), need coverage
- Need standardized, comparable data
- Stakeholders are geographically distributed
- Need quantitative confirmation of hypotheses

**Important:** questions can't be adjusted mid-flight — wording errors
will only surface at the end. So question quality is critical.

**Preparing a survey:**

**Step 1 — Define what you want to measure**
Every question must answer a specific objective. If it's unclear why a question is there — remove it.

**Step 2 — Choose question types**

| Type | When to use | Example |
| :--- | :--- | :--- |
| Closed (Yes/No) | Fact, presence/absence | "Do you use the current system daily?" |
| Scale (1–5, 1–10) | Satisfaction rating, frequency | "Rate the interface's usability from 1 to 5" |
| Multiple choice | Categories, options | "Which features do you use most often?" |
| Open-ended | Opinion, ideas, details | "What would you like to improve?" |
| Ranking | Priorities | "Rank the features by importance" |

**Step 3 — Question quality checklist**

Before sending, check every question:

- [ ] The question is clear without additional explanation
- [ ] One question — one idea (no "and" acting as a logical fork)
- [ ] No leading wording ("Do you agree the system is inconvenient?")
- [ ] No professional jargon the respondent won't understand
- [ ] Closed questions have an "Other / Not sure" option
- [ ] Scales are symmetric (not "Bad / OK / Great / Awesome")
- [ ] The survey takes no longer than 10–12 minutes to complete (up to 15 questions)

**Step 4 — Test the survey**

Mandatory! Give the survey to 2–3 people not involved with the project.
Ask them to flag: what's unclear, what's annoying, how long it took.

**Step 5 — Distribution**

Via Google Forms: use the MCP tool `create_google_form`.
The cover message must include:
- The survey's purpose (1–2 sentences)
- How long it will take
- The deadline
- Who to contact with questions

**Step 6 — Process the results**

Use the MCP tool `get_form_responses` to retrieve and structure the answers.

---

## 3. Workshop

**When to use:**
- Need alignment across several stakeholder groups
- Requirements conflict and a compromise is needed
- Need to gather a large amount of information quickly
- Joint solution development (buy-in) matters

**Preparation:**

1. Define the workshop's goal and expected outcome
2. Draft a list of participants (6–10 people is optimal)
3. Assign roles: facilitator, scribe, timekeeper
4. Prepare an agenda with time slots
5. Prepare materials: templates, sticky notes, a board (Miro / physical)

**Workshop agenda template:**

```
## Workshop agenda: [name]
**Date / time:**
**Participants:**
**Facilitator:**
**Goal:** By the end of the workshop we must have [outcome]

| Time | Block | Format | Owner |
| :--- | :--- | :--- | :--- |
| 09:00–09:10 | Opening, goals, ground rules | Presentation | Facilitator |
| 09:10–09:30 | Context and current state | Discussion | Everyone |
| 09:30–10:00 | [Main topic 1] | Group work | Facilitator |
| 10:00–10:30 | [Main topic 2] | Brainstorming | Everyone |
| 10:30–10:45 | Prioritizing outcomes | Voting | Everyone |
| 10:45–11:00 | Recording agreements, next steps | Wrap-up | Scribe |
```

**Rules of a good workshop:**
- Announce ground rules at the start: one person speaks, no criticizing ideas, phones away
- Capture everything in plain view (flipchart, shared board)
- Parking lot — a dedicated space for important but off-topic questions
- The outcome of a workshop is a concrete list of agreements and next steps

---

## 4. Brainstorming

**When to use:**
- Need ideas without constraints or criticism
- Exploratory phase, the problem isn't yet defined
- Usually as part of a workshop (20–30 minutes)

**Rules:**
- No criticism during idea generation
- Quantity matters more than quality at first
- Building on others' ideas is encouraged
- All ideas are recorded, none are lost

**Process:**
1. Frame the question ("How might we...?")
2. Silent generation — everyone writes their own ideas (5 min)
3. Share-out — everyone reads theirs out, the facilitator records them
4. Group similar ideas
5. Prioritize (dot voting or MoSCoW)

---

## 5. Document Analysis

**When to use:**
- A legacy system, regulations, or instructions exist
- Need to understand the current as-is state
- Stakeholders are hard to reach
- As preparation for an interview (to avoid asking basic questions)

**What to look for in documents:**

| Document type | What we extract |
| :--- | :--- |
| Regulations / instructions | Current rules and processes |
| Reports / dashboards | Metrics, KPIs, pain points |
| Complaints / support tickets | Real user problems |
| Meeting minutes | Previously made decisions |
| Technical specifications | Constraints of the current system |

**Document analysis checklist:**
- [ ] Document date — is it current?
- [ ] Who's the author — how authoritative is the source?
- [ ] Does the document match actual practice?
- [ ] What requirements can be extracted from it?
- [ ] What questions does it raise for the follow-up interview?

---

## 6. Observation

**When to use:**
- Stakeholders can't clearly describe their work ("I just do it")
- Need to understand the real process, not the documented one
- Suspect a gap between "how it should be" and "how it actually is"

**Two types:**

| Type | Description |
| :--- | :--- |
| **Passive (shadowing)** | The BA observes silently, without intervening |
| **Active** | The BA asks questions as the work happens |

**What to record:**
- Sequence of actions
- Tools and systems used
- Deviations from the regulation (and why)
- Bottlenecks and pain points
- Informal practices (users' "workarounds")

---

## 7. Prototyping

**When to use:**
- Requirements are vague and stakeholders struggle to articulate them
- Need to quickly validate a hypothesis about the solution
- High risk of misunderstanding

**Types of prototypes:**

| Type | Tools | When |
| :--- | :--- | :--- |
| Paper (wireframe) | Pencil, paper | Earliest stage |
| Digital lo-fi | Figma, Miro, draw.io | Discussion with the business |
| Interactive hi-fi | Figma, Marvel | Validation with users |

**Important:** a prototype is a conversation tool, not a technical specification.
Tell the stakeholder explicitly: "This isn't the final design, it's a way to discuss requirements."

---

## 8. Focus Group

**When to use:**
- Need the opinion of a group of end users
- Group dynamics and discussion matter
- Researching perception of a product / process

**Difference from a workshop:** a focus group explores opinions, a workshop produces decisions.

**Optimal composition:** 6–8 participants, one moderator, one observer/scribe.

---

## 9. Benchmarking

**When to use:**
- Need to compare against industry practices or competitors
- No internal expertise on the topic
- Need to justify the choice of approach

**Sources:** industry reports, case studies, open standards, competitive analysis.

**Outcome:** a list of best practices with an assessment of applicability to the current context.
