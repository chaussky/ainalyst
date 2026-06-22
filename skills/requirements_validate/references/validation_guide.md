# validation_guide.md — Requirements Validation Methodology (BABOK 7.3)

## Validation vs Verification

| Aspect | 7.2 Verification | 7.3 Validation |
|--------|----------------|---------------|
| Question | Is it written correctly? | Do we need this? |
| Focus | Quality of wording | Value to the business |
| Techniques | Rule-based, checklists | BFS analysis, stakeholder review |
| Frequency | One-time pass | Iterative |
| Result | Status `verified` | Status `validated` |

**Key idea:** a requirement can pass verification with an excellent result (atomic, unambiguous, testable) but fail validation (not needed by the business, not linked to business goals).

---

## Three axes of validation

### Axis 1: Value

**Question:** Does this requirement bring benefit to stakeholders?

**Warning signs:**
- The req is not linked to any business goal (orphan)
- Stakeholders cannot explain why it's needed
- Value is not measurable (no KPI or success criteria)
- Value exists only for one stakeholder, conflicting with others

**BABOK technique — Financial Analysis:**
For critical decisions, we assess the ROI of the requirement:
- Cost of implementation vs. value to the business
- If cost > benefit → candidate for exclusion

---

### Axis 2: Future State Alignment

**Question:** Does this requirement help achieve the target state?

**Verification via BFS (automatic in `check_business_alignment`):**
```
req → links in 5.1 → BFS traversal → node of type 'business' → matches a BG?
```

**Title-matching (second method):**
If the 5.1 graph is sparse, we look for keyword overlap between the req and the BG.

**Warning signs:**
- The req describes "how it was" instead of "how it should be"
- The req documents the current process without improving it
- The req contradicts the Future State description

---

### Axis 3: Assumptions & Risks

**Question:** Have key assumptions been identified? Are the risks managed?

**When to identify assumptions:**
- The req cannot be implemented without a certain condition (technical, business-related)
- There's uncertainty in user or system behavior
- Integrations depend on third-party systems
- The project's business model is innovative (unprecedented product)

---

## BABOK techniques for validation

### 1. Acceptance and Evaluation Criteria

Measurable conditions under which the solution is considered successful:
```
Baseline: current metric
Target: target metric
Measurement method: how to measure
```

Stored in the `success_criteria` field of the req node in the 5.1 repository.

### 2. Stakeholder Review

A structured session with the customer:
- Go through each BG: "Which req help achieve this goal?"
- Present orphan req to the customer: "Why do we need this?"
- Discuss open assumptions: "Does this match your experience?"

### 3. Prototyping

Early value verification through visualization:
- A wireframe shows how the req will materialize in the interface
- A stakeholder may react with "this isn't what I need"
- Surfaces hidden assumptions

### 4. Risk Analysis

For each high-risk assumption:
- Probability: how likely is it to be refuted?
- Impact: what happens to the project if it's refuted?
- Mitigation: what do we do if it is refuted?

---

## Common validation error patterns

### Pattern 1: "Gold Plating"

**Symptom:** Many highly detailed req, orphan with respect to BGs.

**Diagnosis:**
- `check_business_alignment` reports >20% orphan
- Stakeholders cannot connect the req to a business problem

**Solution:** For each orphan, ask the customer "Why?" If there's no answer, remove it.

---

### Pattern 2: "Surrogate Goals"

**Symptom:** BGs are phrased as technical tasks rather than business outcomes.

**Example of a bad BG:** "Implement a microservices architecture"
**Example of a good BG:** "Reduce time-to-market for new features from 3 months to 3 weeks"

**Consequence:** check_business_alignment will be inaccurate — technical req will match technical BGs.

---

### Pattern 3: "Untested Assumptions"

**Symptom:** No assumptions logged anywhere in the project.

**Diagnosis:** Either the BA didn't log assumptions, or the project is trivial.

**Typical assumptions that get forgotten:**
- "Users will accept the interface change"
- "The legacy system supports the integration"
- "The migration data volume is known"
- "Approval timelines in adjacent departments fit the plan"

---

### Pattern 4: "Uncovered Goals"

**Symptom:** There are BGs with no req.

**Diagnosis:** `get_validation_report` shows an empty row in the coverage matrix.

**Possible causes:**
- The BG was added after the requirements → new req are needed
- The BG is achieved through organizational measures, not IT → mark it as out of scope
- The BG will be implemented in a later iteration → log it in the backlog

---

## Readiness for 7.5 Design Options

Criteria for moving on to 7.5:
- [ ] ≥ 80% of verified req have reached validated status
- [ ] 0 open high-risk assumptions
- [ ] 0 orphan req (or all orphans deliberately excluded)
- [ ] All BGs are covered by at least one req
- [ ] Validation Report has been created

If the criteria are not met, `get_validation_report` returns a ❌ status with an explanation.
