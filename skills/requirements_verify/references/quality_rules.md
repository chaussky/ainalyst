# quality_rules.md — Rule-Based Requirements Verification Rules

Source: BABOK v3, section 7.2 (Verify Requirements).
Used by: `check_req_quality` in `requirements_verify_mcp.py`.

---

## BABOK's 9 quality characteristics

BABOK v3 defines 9 requirements quality characteristics:

| # | Characteristic | BABOK term | Group |
|---|---------------|-------------|--------|
| 1 | Atomic | Atomic | A (rule-based) |
| 2 | Unambiguous | Unambiguous | A (rule-based) |
| 3 | Testable | Testable | A (rule-based) |
| 4 | Prioritized | Prioritized | A (rule-based) |
| 5 | Concise | Concise | A (rule-based) |
| 6 | Consistent | Consistent | B (repository) |
| 7 | Complete | Complete | B (repository) |
| 8 | Feasible | Feasible | C (expert) |
| 9 | Understandable | Understandable | C (expert) |

---

## Group A — Rule-Based (automatic via MCP)

### 1. Atomic

**Definition:** A single requirement describes exactly one capability or characteristic of the system.

**Note:** The platform's requirements text is written in Russian by the BA, so the detection lists below operate on Russian-language signal words. They are reproduced here exactly as implemented in `requirements_verify_mcp.py` — do not alter them when updating this document.

**Violation signals (atomicity stop words):**
```python
ATOMICITY_SIGNALS = [
    " и ", " и\n", " а также ", " а так же ",
    " а ещё ", " а еще ", " плюс ", " кроме того ",
    " помимо этого ", " вдобавок ", " одновременно с ",
]
```

**Rule:** If the requirement text (title + description) contains 2+ stop words — flag `not_atomic`. A single stop word — a warning (it may be part of a single condition).

**Exceptions:** The conjunction "и" ("and") in a list of field values (e.g., "fields First Name and Last Name") is not an atomicity violation if it doesn't describe two distinct system actions. MCP does not do semantic parsing — Claude Code interprets it.

---

### 2. Unambiguous

**Definition:** The requirement allows only one interpretation.

**Ambiguity signal words:**
```python
AMBIGUITY_SIGNALS = [
    # Speed/quality without a metric
    "быстро", "быстрый", "быстрая", "быстрое",
    "медленно", "медленный",
    "удобно", "удобный", "удобная", "удобное", "удобен",
    "легко", "легкий", "лёгкий", "легкая", "лёгкая",
    "хорошо", "хороший", "хорошая", "хорошее",
    "качественно", "качественный",
    "эффективно", "эффективный",
    "оптимально", "оптимальный",
    # Frequency without a value
    "часто", "редко", "периодически", "иногда", "регулярно",
    "обычно", "как правило", "как правило,", "в большинстве случаев",
    "как правило", "зачастую", "нередко",
    # Vague obligations
    "должен стараться", "по возможности", "по мере возможности",
    "в разумные сроки", "в кратчайшие сроки", "максимально быстро",
    "при необходимости", "в случае необходимости", "при наличии",
    "желательно", "предпочтительно", "рекомендуется",
    "допустимо", "допускается",
    # Relative assessments
    "небольшой", "большой", "крупный", "значительный", "существенный",
    "достаточно", "достаточный", "адекватный", "приемлемый",
    "минимальный", "максимальный",  # without a specific value
    # Vague time references
    "вовремя", "своевременно", "без задержек", "оперативно",
    # Technical ambiguities
    "и/или", "и / или",
    "современный", "актуальный", "последний",
    "стандартный", "типовой", "обычный",
]
```

**Rule:** If the requirement text contains at least one signal word — flag `ambiguous`. For every signal found — indicate exactly where (so Claude Code can give a specific recommendation).

---

### 3. Testable

**Definition:** A test with an unambiguous pass/fail result can be written for the requirement.

**Rules by requirement type:**

#### User Story (type: user_story)
- **Critical:** Presence of Acceptance Criteria (AC) — at least 2 AC.
- **Flag:** `missing_ac` if AC are absent or fewer than 2.
- **Warning:** If the AC text contains ambiguity signal words from the list above.

#### Functional Requirement (type: functional)
- **Critical:** Presence of a measurable criterion — a number or a clear binary condition.
- **Measurability presence signals:**
  ```
  MEASURABILITY_PATTERNS = [
      r'\d+\s*(?:мс|с|сек|мин|час|%|мб|гб|тб|rpm|rps|tps|запрос)',
      r'не более \d+', r'не менее \d+', r'до \d+', r'от \d+',
      r'\d+ секунд', r'\d+ минут', r'\d+ пользовател',
      r'100%', r'0 ошибок', r'нулевой', r'полностью',
  ]
  ```
- **Flag:** `not_testable` if no pattern is found in the description.

#### Non-Functional Requirement (type: non_functional)
- **Critical:** Must have a metric + a numeric value + a measurement condition.
- **Flag:** `not_testable` if there is no numeric value.

#### Business Rule (type: business_rule)
- **Looser:** A rule is considered testable if it contains a clear condition (если/when/при/в случае).
- **Warning** if there is no condition.

#### Use Case (type: use_case)
- **Critical:** Presence of at least one exception/alternative scenario.
- **Flag:** `not_testable` if exc_scenarios is empty (meaning the UC has no boundary conditions).

---

### 4. Prioritized

**Definition:** Every requirement has a priority for scope decisions.

**Rule:** We check the `priority` field in the 5.1 repository.
- Values `High | Medium | Low` — OK.
- An empty value `""` or a missing field — flag `not_prioritized`.

**Additionally:** If task 5.3 (Prioritize) has been run, the requirement may have a priority from MoSCoW or WSJF. The flag is cleared by any non-empty priority.

---

### 5. Concise

**Definition:** The requirement contains no extraneous information, implementation explanations, change history, or duplicate wording.

**Rules (heuristics):**

**Length:** Too long — a possible sign of an atomicity violation or extraneous content.
- User Story title: recommended ≤ 100 characters (warning if exceeded).
- Functional Requirement description: recommended ≤ 500 characters (warning).

**Conciseness violation signals:**
```python
CONCISENESS_SIGNALS = [
    # Explaining the solution instead of the need
    "реализовать через", "реализовать с помощью", "использовать технологию",
    "использовать фреймворк", "написать код", "создать таблицу в базе",
    "использовать REST", "использовать API", "вызвать метод",
    # Historical background (not needed in a requirement)
    "ранее", "до этого", "исторически", "изначально было",
    "в предыдущей версии",
    # Duplicating the obvious
    "система должна быть системой", "функция функционирует",
]
```

**Rule:** A warning (not a blocker) when signals are found or the length is exceeded. Conciseness is the only characteristic without a blocking flag (it's subjective — Claude Code interprets it).

---

## Group B — Analysis of the 5.1 Repository (via MCP)

### 6. Consistent

**Definition:** The requirement does not contradict other requirements in the project.

**What MCP checks:**
- Presence of requirements with a `conflict` status in the 5.1 repository (if the BA has already flagged it).
- Presence of `conflict`-type links (a non-standard type — if the BA added it manually).
- Presence of `rejected` requirements flagged as conflicting.

**What Claude Code checks (semantics):**
- Claude Code reads the full list of reqs and identifies logical contradictions by meaning.
- Example: "The system shall retain all data forever" + "Data is deleted after 90 days" — an explicit conflict.

**What MCP returns:**
- A list of requirements with suspicious statuses.
- The link graph — neighboring nodes via `depends`/`derives` for Claude Code to analyze.

---

### 7. Complete

**Definition:** The requirement contains all the information necessary for understanding and implementation.

**What MCP checks (coverage):**
- % of requirements without a source_artifact (not traced to 4.3).
- % of requirements without links in the 5.1 graph (isolated nodes).
- List of `draft`-status reqs without an owner.

**Complement to the 7.1 coverage matrix:**
- `build_coverage_matrix` (7.1) checks coverage of business objectives.
- `check_req_quality` (7.2) checks the internal completeness of each req.
- No duplication — these are different levels of analysis.

---

## Group C — Expert Checks (checklists, Claude Code)

### 8. Feasible

**Definition:** The requirement is achievable within known constraints (budget, schedule, technology).

**Why it isn't automated:**
- Requires knowledge of the project's budget and technical constraints.
- Requires expert assessment of implementation complexity.
- The BA consults with the development team.

**Hints for the BA (in SKILL.md and checklist_templates.md):**
- Has this type of functionality been implemented in the team's past projects?
- Are there ready-made libraries/solutions?
- Complexity estimate: S/M/L/XL.
- Does it fit the technology stack?

---

### 9. Understandable

**Definition:** The requirement is understandable to the target audience without additional explanation.

**Why it isn't automated:**
- Depends on the audience (developer ≠ business sponsor).
- Requires a reader's judgment, not pattern matching.

**Hints for the BA:**
- Read the requirement to someone unfamiliar with it — do they have questions?
- Is there any jargon specific to a single department?
- Are all abbreviations defined on first use?

---

## Severity matrix by characteristic

| Characteristic | Violation | Severity | Recommended issue_type |
|---------------|-----------|---------|--------------------------|
| Atomic | 2+ stop words | major | not_atomic |
| Unambiguous | 1+ signal | major | ambiguity |
| Testable (US without AC) | 0-1 AC | blocker | missing_ac |
| Testable (FR without a metric) | no number | major | not_testable |
| Prioritized | no priority | minor | other |
| Concise | length exceeded | minor | other |
| Consistent | conflicting statuses | major | other |
| Complete | no source_artifact | minor | other |
| Feasible | checklist | — | BA checklist |
| Understandable | checklist | — | BA checklist |

---

## Result aggregation rules

`check_req_quality` returns the following for each req:

```json
{
  "req_id": "US-001",
  "req_type": "user_story",
  "title": "...",
  "checks": {
    "atomic": {"passed": true, "signals_found": [], "warning": null},
    "unambiguous": {"passed": false, "signals_found": ["быстро", "удобно"], "warning": null},
    "testable": {"passed": false, "issue": "missing_ac", "ac_count": 1},
    "prioritized": {"passed": true, "priority": "High"},
    "concise": {"passed": true, "warning": "title length 110 characters"}
  },
  "group_b": {
    "consistent": {"status": "needs_review", "notes": ""},
    "complete": {"has_source": true, "has_links": false, "has_owner": false}
  },
  "group_c_checklist": "see checklist_templates.md",
  "overall": "issues_found",
  "blockers": ["missing_ac"],
  "majors": ["ambiguity"],
  "minors": []
}
```

**`overall` statuses:**
- `passed` — all checks OK
- `warnings_only` — only minor/warnings
- `issues_found` — there are majors or blockers
