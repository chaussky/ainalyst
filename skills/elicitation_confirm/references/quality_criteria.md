# Quality criteria for elicitation results (BABOK 4.3)

Use this file when performing the internal check in Mode A.
Each criterion is a separate dimension. A problem may relate to one or several of them.

---

## 1. Completeness

**What we check:** whether there are gaps in the captured information.

**Indicators of violation:**
- The stakeholder mentioned a topic, but the BA didn't explore it ("there are also problems with reports")
- No answer to the question "what happens in an exceptional situation"
- A business process is described partially: there's a beginning, no end
- An actor is named, but their needs aren't described
- The gap analysis from 4.2 contains unclosed blind spots

**How to phrase the problem:**
> "It is not recorded what happens when [condition]. The stakeholder mentioned this
> in passing ([quote if available]), but the topic was not explored."

**Recommendation when violated:** clarify with the source or conduct additional elicitation.

---

## 2. Accuracy

**What we check:** whether what was recorded matches what the stakeholder actually said.

**Indicators of violation:**
- The BA rephrased with loss of meaning (the stakeholder's words don't match the record)
- The quote doesn't match the recorded requirement
- Quantitative figures were recorded approximately ("about 100" → "up to 100")
- The BA invented implementation details that the stakeholder never mentioned

**How to phrase the problem:**
> "Requirement [ID] is phrased as '[wording]', but in the source the stakeholder
> talked about '[original context]'. There is a risk of meaning drift."

**Recommendation when violated:** go back to the original transcript, clarify with the stakeholder.

---

## 3. Consistency

**What we check:** whether there are conflicts within a single source or between sources.

### 3a. Internal consistency (single source)
- The stakeholder said A in one interview, then said not-A
- A requirement conflicts with a business rule from the same source
- Priorities are set inconsistently

### 3b. Cross-source consistency (multiple sources)
- Stakeholder A requires X, stakeholder B requires not-X
- Different sources describe the same process differently
- Different sources give different numbers for the same metric

**How to phrase the problem:**
> "Contradiction: [source A] states [X], [source B] states [Y].
> Type: [internal / cross-source]. Required: [facilitation / clarification]."

**Recommendation when violated:**
- Internal contradiction → clarify with the same stakeholder
- Cross-source → facilitation meeting or escalation to the decision maker

---

## 4. Unambiguity

**What we check:** whether each requirement can be interpreted in only one way.

**Indicators of violation:**
- Vague words without criteria: "fast", "convenient", "reliable", "flexible"
- Modal words without clarification: "typically", "usually", "in most cases"
- Unclear subject: "the system shall" — which part of the system exactly?
- Unclear trigger: "if necessary", "when needed"
- Two meanings in one sentence

**Examples of fixes:**

| ❌ Ambiguous | ✅ Unambiguous |
|---|---|
| The system shall work fast | Response time is no more than 2 sec with 100 users |
| Notifications arrive in a timely manner | A notification is sent within 5 minutes of the event |
| The system shall be reliable | Availability is at least 99.5% during business hours |

**How to phrase the problem:**
> "Requirement [ID] contains an ambiguous phrase '[phrase]'.
> Possible interpretations: [A] or [B]. A measurable criterion needs to be added."

**Recommendation when violated:** clarify the metric with the stakeholder or tech lead.

---

## 5. Testability

**What we check:** whether fulfillment of the requirement can be unambiguously verified.

**Indicators of violation:**
- No criterion for "how we'll know this works"
- The requirement describes an intent, not system behavior
- Boundary conditions for verification are missing
- The requirement relies on subjective judgment ("the user should like it")

**Relation to unambiguity:** an ambiguous requirement is almost always untestable.
But a requirement can be unambiguous and still untestable: "the system shall not crash" — clear, but how do you test it?

**How to phrase the problem:**
> "Requirement [ID] has no acceptance criterion. It's unclear how to verify
> fulfillment. Proposed criterion: [option]."

**Recommendation when violated:** add acceptance criteria (in Gherkin format where possible).

---

## Severity classification

| Severity | Indicator | Action |
|---|---|---|
| 🔴 Critical | Blocks analysis or leads to an incorrect decision | Stop, clarify before continuing |
| 🟡 Significant | Creates risk at the development or testing stage | Clarify before handing off to Chapter 5/6 |
| 🟢 Minor | Cosmetic inaccuracy, doesn't affect meaning | Log it, fix on the next iteration |

---

## Artifact readiness rating

**✅ Ready for analysis**
No critical or significant problems. Hand off to 6.1/6.3.

**⚠️ Conditionally ready**
There are significant problems, but they don't block overall understanding.
Can be handed off with open questions explicitly flagged.

**🔴 Needs rework**
There are critical problems. Clarification is mandatory before continuing work.
