# Reference Guide: Root Cause Analysis (BABOK 6.1)

## Why RCA matters in the context of 6.1

The most common BA mistake: describing symptoms instead of root causes.

| Symptom | Root cause (example) |
|---------|---------------------------|
| "Customer complaints are increasing" | The approval process contains 3 extra levels due to a 2012-era policy |
| "Data is lost during transfer" | The integration between the CRM and the 1C system runs through a manual Excel export |
| "Employees are overloaded" | No prioritization automation — everything is queued manually |

**Without RCA:** the business need is formulated as "we need a system for X"  
**With RCA:** "we need to eliminate cause Y, which leads to problem X"

The second version gives a precise solution scope and allows the value to be assessed (7.6).

---

## Three RCA techniques

### Technique 1: Five Whys

**When to apply:**
- The problem is linear (a single chain of causes)
- A fast path to the root cause is needed
- The team is small, time is limited

**How to apply:**
1. State the problem as an assertion (not a question)
2. Ask "Why does this happen?" → record the answer
3. Ask "Why [answer 1]?" → record the answer
4. Repeat for 4–5 iterations (until the answer goes beyond our authority to change)
5. The last answer is the root cause

**Example:**
```
Problem: Request processing time increased from 2 to 8 hours

Why? → Approval takes up most of the time (5.5 of 8 hours)
Why? → Managers wait in line in a shared mailbox
Why? → There's no notification system for approval requests
Why? → The approval process was manually configured around a 2012-era policy
Why? → The policy wasn't updated after the 2019 digitalization

Root cause: The approval policy is outdated and contains manual steps
incompatible with the current infrastructure
```

**Limitations:** not suitable if the problem has several independent causes.

---

### Technique 2: Fishbone / Ishikawa (Cause-and-Effect Diagram)

**When to apply:**
- The problem is complex (many possible causes)
- All categories need to be covered systematically
- There's time for a workshop with stakeholders

**6 categories (manufacturing's 6M → adapted for business analysis):**
| Category | Description |
|-----------|----------|
| **People** | People, skills, motivation, overload |
| **Process** | Business processes, procedures, work instructions |
| **Technology** | Systems, tools, integrations, infrastructure |
| **Policies** | Regulations, rules, constraints |
| **Data** | Data quality, availability, formats |
| **Environment** | External factors: regulators, market, competitors |

**How to apply:**
1. Write the problem (the effect) at the "head of the fish"
2. For each category: brainstorm — what in this category affects the problem?
3. List all possible causes (without evaluation)
4. Rank: which causes are most likely? (voting or expert judgment)
5. Select the top 3–5, confirm with data

**Example (partial):**
```
Problem: High error rate during data transfer between systems

Process:  ← No formal transfer protocol
          ← Manual Excel export used as a "temporary solution" since 2018
Technology: ← CRM and the 1C system have no direct integration
            ← Different date formats across systems
People:   ← Different employees perform the export differently (no standard)
```

---

### Technique 3: Problem Tree

**When to apply:**
- Causes and effects need to be connected into a single picture
- A strategic change with broad scope
- The sponsor needs to see the "full picture" of the problem

**Structure:**
- Roots of the tree = root causes
- Trunk = the key problem (statement)
- Branches/leaves = consequences and effects of the problem

**How to apply:**
1. State the central problem
2. Go down: "Why does this happen?" → root causes → even deeper
3. Go up: "What does this cause?" → effects → consequences
4. Verify: does each cause genuinely lead to the problem? (cause-and-effect link)
5. Prioritize: which root causes are addressable? which have the greatest impact?

---

## Normalized RCA output format (ADR-056)

Regardless of the technique used, the result is saved in a unified format.
The technique is a thinking tool. The MCP saves the normalized artifact.

```json
{
  "rca_id": "RCA-001",
  "problem_statement": "Customer request processing time increased from 2 to 8 hours over the last 6 months",
  "technique_used": "fishbone",
  "root_cause": "The approval process contains 3 extra levels inherited from a 2012-era policy",
  "contributing_factors": [
    "The approval system hasn't been updated since 2012",
    "No automation for notifications about pending approvals",
    "Mid-level managers duplicate checks already done by senior managers"
  ],
  "evidence": [
    "Average approval wait time: 5.5 of 8 total hours (team interview, 03/15)",
    "78% of requests wait more than 4 hours for approval (system data, Q1 2025)",
    "The approval policy is dated 04/12/2012 and has not been updated"
  ],
  "affected_elements": ["capabilities", "policies", "technology"],
  "created": "2025-03-15T10:00:00"
}
```

### Field descriptions

| Field | Description | Required |
|------|----------|-------------|
| `rca_id` | Unique ID: RCA-001, RCA-002, ... | Yes |
| `problem_statement` | A clear, measurable statement of the problem | Yes |
| `technique_used` | fishbone / five_whys / problem_tree | Yes |
| `root_cause` | One main root cause (not a symptom!) | Yes |
| `contributing_factors` | Factors that reinforce the root cause | No (but recommended) |
| `evidence` | Data confirming the cause-and-effect link | No (but critical for convincing the sponsor) |
| `affected_elements` | Which of the 8 current-state elements are affected | No |
| `created` | Date and time | Yes (automatic) |

### How to tell a root cause from a symptom

**Test 1 — The "if we eliminate X, will the problem disappear?" test**
- If we eliminate the symptom → the problem will resurface differently
- If we eliminate the root cause → the problem will go away

**Test 2 — Can "Why X?" be asked again**
- If the answer can still be followed by another "Why?" → it's not yet the root cause
- If "Why?" no longer makes sense → this is the root cause

**Test 3 — "Is it within our power to change X?"**
- If the cause is outside the organization's control → it's an external influence, not a root cause
- If we can change it → it's our root cause

---

## How RCA connects to business needs

After RCA: we formulate business needs using the `define_business_needs` tool.

Diagram:
```
RCA-001 (root_cause: "outdated approval policy")
  ↓ links to ↓
BN-001 (need: "Optimize the request approval process")
  ↓ registered in the 5.1 repository as ↓
A business_need node of type BN-001
  ↓ becomes upstream for ↓
BR-001 (business requirement)
  → FR-001, FR-002 (functional requirements)
```

The `root_cause_ids` parameter in `define_business_needs` links the need to RCA artifacts.

---

## Signs of a poor RCA (checklist for Claude)

🔴 **Symptom instead of a cause:**
- "There's no system" — this is a description of a solution, not a cause
- "Employees don't know how" — a symptom; the cause is "no training / no procedure"

🔴 **No evidence:**
- A root cause is named, but without data — it's a hypothesis, not a fact
- Ask the BA to confirm: "How do we know this is actually the case?"

🟡 **Too many root causes:**
- If you have 7+ "root causes," they're probably contributing factors
- There are usually only 1–3 genuine root causes

🟡 **Causes outside our control:**
- "Competitors are cutting prices" — an external influence, not a root cause for RCA
- Such factors belong in the `external` element, not in the RCA
