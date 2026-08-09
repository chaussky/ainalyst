# AInalyst: AI assistant for business analysts (BABOK v3)

**🇷🇺 Русскоязычная версия в ветке [`ru`](../../tree/ru).**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-1556%20passed-brightgreen.svg)](tests/)
[![Claude Code](https://img.shields.io/badge/Claude_Code-required-orange.svg)](https://claude.ai)
![Status: Beta](https://img.shields.io/badge/status-beta-orange)

**AInalyst** is an AI assistant that works alongside you like a seasoned analyst colleague. It knows the BABOK v3 methodology, runs interviews, builds stakeholder maps, traces requirements, and produces artifacts. You describe the task in your own words, and AInalyst proposes the next step, asks clarifying questions, and gets the work done.

---
> ⚠️ **Note:** The project is in **Public Beta**. We are actively testing the BABOK working logic on real projects.
---

## How it works

At the core of the platform is Anthropic's Claude large language model. One level up is Claude Code, an AI agent that doesn't just answer but acts: it reads files, runs tools, and guides you through the process. One level higher still is a set of 21 skills and 22 MCP servers with 114 tools that cover every task in BABOK chapters 3, 4, 5, 6, and 7.

Each skill is written to a strict specification and includes a YAML header with triggers: semantic patterns that describe exactly when that skill should fire. When a business analyst types something into the chat, AInalyst analyzes the request, matches it against the triggers, activates the right skill, and that skill calls the corresponding tools from the MCP servers. The business analyst doesn't know exactly what happened under the hood. And they don't need to: they see the result.

### What this means in practice

**Reduced cognitive load.** A project may run for months, with stakeholders, decisions, requirements, and change history piling up. Holding it all in your head is impossible. AInalyst records every step in structured artifacts. At any moment you can ask "what approvals are open right now" or "why was this decision made," and get an answer immediately.

**Methodological safety net.** BABOK is 500 pages of structured expertise. AInalyst builds it into the process: it won't let you skip an important step, warns about risks, and suggests the next action. A BA who isn't well versed in the methodology works with the platform just as confidently as a seasoned specialist.

---

## Who it's built for

**The experienced business analyst** gets a tool that takes the routine off their plate: it structures transcripts, builds traceability matrices, and generates communication packages for different audiences, freeing up time for analysis, interpretation, and decision-making.

**The junior BA** gets a dependable guide. The platform doesn't judge you for not knowing BABOK; it helps you do it right: it asks the right questions, explains why a wording failed validation, and shows what a good requirement should look like.

**A product or project manager** with no dedicated BA gains the ability to work to a professional methodology without having to study it specifically. The platform adapts its language to the person it's talking to and takes on the role of methodologist.

**A startup or small team** with no budget for an in-house analyst gets a structured environment for working with requirements from day one, instead of chaos across Notion and messaging apps.

---

## Use cases for AInalyst

The platform covers a broad range of business analysis tasks, from preparing for interviews and prioritizing requirements to strategy analysis and preparing recommendations for leadership. Here are a few examples of how it works in practice.

### Impact analysis for a sudden change request

> **For:** Business analysts on active projects
> **Pain:** A change request "sounds simple," but half the project's artifacts hang off it

A BA receives a request from the commercial director: add real-time CO₂ emissions calculation for routes. Sounds straightforward. The business analyst opens AInalyst:

> "Open a change request: the commercial director wants to add real-time CO₂ emissions calculation."

AInalyst runs a BFS traversal of the traceability graph and, in seconds, finds 11 affected artifacts, including a conflict with NFR-003 (API response time). It produces an assessment: accept on the condition that the "real-time" requirement is dropped. It prepares the arguments for the meeting with the director.

The BA shows up not with a refusal, but with data and an alternative. The CR is accepted in a form that doesn't create technical debt. And nobody "forgot" about three test cases and the architectural decision on caching.

---

### Four prioritization methods for different contexts

> **For:** Business analysts on projects with competing requirements
> **Pain:** Prioritization is done "by gut feeling," with no defensible result

A BA is running four projects at once, each with a different context. AInalyst picks the right method for each:

- **HR tool, deadline in two weeks** → MoSCoW in 20 minutes. Fast, clear to stakeholders.
- **Agile team, 60 requirements in the backlog** → WSJF with a numeric score for each requirement, ready to load into Jira.
- **Workshop with three non-technical directors** → Impact/Effort Matrix. Visual, no formulas, engages everyone in the room.
- **Everything came back "Must", and the sprint holds 40 points** → Time Boxing/Budgeting. The capacity does the cutting, and the report names what was left out and what it would have cost.

In the third case, AInalyst spots a dependency violation right there in the workshop, while the directors are still in the room, rather than at sprint planning, when changing anything is already painful.

---

### Requirements verification: a junior BA performing like a senior

> **For:** Junior BAs, team leads, heads of the business analysis practice
> **Pain:** Requirements go into development "raw," and wording problems only surface during testing

A business analyst wrote 40 requirements for a credit scoring module, reread them several times, and was satisfied. Before handing them off to development, they run them through AInalyst:

> "Check the quality of the requirements for the credit scoring module. All 40 of them, file requirements_credit_v3.md."

AInalyst checks them against the 9 BABOK characteristics: of the 40 requirements, 29 are sound and 11 have issues. It finds 6 cases of ambiguity, 3 non-atomic requirements, and 2 requirements with no acceptance criteria. For each case it shows how to reword it, explaining why the original version doesn't work.

The 11 problems are found minutes before handoff, not after. And for a junior BA this isn't just a document fix; it's learning on real material: after ten sessions like this, requirement quality shifts to the level of habit.

---

You can find more use cases in the [`use-cases.md`](docs/use-cases/use-cases.md) file.

---

## What you'll need

Before installing, make sure your machine has:

- **Python 3.10 or newer.** If you're not sure, check with `python --version` in the terminal
- **VS Code.** Download it at [code.visualstudio.com](https://code.visualstudio.com)
- **An Anthropic account.** A Pro plan or higher, available at [claude.ai](https://claude.ai)

---

## Installation

Download the project and install the dependencies:

```bash
git clone https://github.com/chaussky/ainalyst.git
cd ainalyst
pip install -r requirements.txt
```

If you have access to Confluence, set up the connection:

```bash
cp .env.example .env
```

Open `.env` in any editor and paste in your Confluence URL, login, and API token. Instructions for obtaining a token are right there in the comments in `.env.example`.

---

## First run via VS Code

The most convenient way to work with AInalyst is through VS Code: the chat with Claude opens right inside the editor, next to your project files.

**Step 1. Install the Claude Code extension.**

Open VS Code, go to the Extensions tab (`Ctrl+Shift+X`), search for **Claude Code**, and click Install. After installation, VS Code will prompt you to sign in to your Anthropic account; follow the on-screen instructions.

**Step 2. Open the project folder.**

`File → Open Folder` → select the `ainalyst` folder. This matters: Claude Code needs to see the project root, otherwise it won't pick up the settings.

**Step 3. Launch Claude Code.**

Press `Ctrl+Shift+P`, type **Claude Code: Open**, and press Enter. The chat panel will open on the right.

**Step 4. Get started.**

Just type what you need to do, for example:

> *"We're starting a new project. The client is Acme Corp; we need to automate the contract approval process."*

Claude will ask clarifying questions and suggest where to begin.

---

## How phases work

AInalyst is built so that, at any given moment, only the tools for the relevant BABOK chapter are loaded. This is by design: if everything were loaded at once, Claude would spend a lot of "memory" on tools it doesn't currently need and would perform worse.

At the start of a new project, the `planning` phase is active: the Chapter 3 tools. AInalyst will tell you when it's time to switch.

Switching is done through the VS Code integrated terminal (`` Ctrl+` ``):

```bash
python phase.py elicitation
```

After that, AInalyst will ask you to enter `/restart`, which it needs in order to reload with the new tools. Your entire conversation history is preserved.

Here are all the available phases:

| Phase | BABOK chapter | When to use |
|------|-------------|-------------------|
| `planning` | Ch. 3 | New project, BA plan, stakeholder map |
| `elicitation` | Ch. 4 | Interviews, workshops, meeting minutes |
| `lifecycle` | Ch. 5 | Traceability, prioritization, CRs, approval |
| `analysis` | Ch. 6 | As-is / to-be analysis, gap, risks, strategy |
| `design` | Ch. 7 | Specification, verification, validation, design |
| `full` | All | Only when you need tools from different chapters |

To see which phase is active right now:

```bash
python phase.py
```

---

## Input materials

Drop any input file into the `inputs/` folder and tell AInalyst:

> *"Process this material. File: inputs/ivanov_21mar.txt"*

AInalyst will read the file, extract requirements, risks, and open questions, and save the result as an artifact. Any kind of source works: interview and workshop transcripts, business rules, regulations, technical specifications. The supported formats are `.txt`, `.md`, `.pdf`, and `.docx`.

---

## Deliverables and publishing artifacts

All the artifacts AInalyst creates as it works are saved in the `governance_plans/reports/` folder in Markdown format. These are official project documents: BA plans, stakeholder maps, interview minutes, requirements specifications.

The most convenient way to share them with the team is to publish them directly to Confluence. AInalyst can do this itself: just tell it "publish this artifact to Confluence," and the document will appear on the right page in your space. The Confluence integration is always available, in any phase; just fill in the `.env` file with your details.

If you don't have Confluence, send the `.md` file from `reports/` to a colleague directly, or open it in VS Code and copy the contents wherever you like.

**Need a PDF?** AInalyst produces Markdown artifacts. To get a PDF, use any tool you like: `pandoc`, the "Print to PDF" option in a Markdown editor such as VS Code, or simply ask the assistant to convert a file.

The `governance_plans/data/` folder holds internal data in JSON format. This is the system's "memory" between sessions: the requirements graph, prioritization data, assessment results. There's no need to edit these by hand.

Those files are replaced in a single step, so an interrupted write leaves the previous version whole instead of a truncated one, and the **last five versions of each are kept in `governance_plans/.history/`**. If a tool ever reports that a file cannot be read, its message names both the file and that folder — the newest copy there is the project as it stood before the most recent change.

---

## If something goes wrong

If Claude is responding oddly or can't see the tools you need, the wrong phase is probably active. Check it:

```bash
python phase.py
```

And switch to the one you need. After `/restart`, everything will fall back into place.

---

## The business analyst's responsibilities

The platform takes on the methodology, tool selection, and artifact creation. A few simple but important things remain with the business analyst.

**Managing phases.** Keep an eye on which phase is currently active and switch it as the project progresses. You can do this manually in the terminal (`python phase.py <phase>`) or just ask AInalyst, and it will run the command for you.

**Talking to AInalyst.** Phrase your tasks freely in the chat: describe the context, ask questions, clarify details. You don't need to know tool names or commands; it's enough to explain what needs to be done.

**Answering clarifying questions.** AInalyst will ask follow-up questions at key moments: when it's time to choose a methodology, set priorities, or confirm a decision. Answer them: the quality of your answers determines the quality of the result.

**Input materials.** Put all your working documents (interview transcripts, regulations, business rules, specifications) into the `inputs/` folder before processing.

**Deliverables.** Collect finished artifacts from the `governance_plans/reports/` folder. That's where all the official project documents live: plans, registries, minutes, specifications.

**Decision-making.** AInalyst gives recommendations, warns about risks, and offers options, but the final decision is always yours. The platform helps you make a good decision; it doesn't make it for you.

---

## For developers

Run the tests:

```bash
pip install -r requirements-dev.txt
pytest tests/
```

The project structure is described in `CLAUDE.md`, which also contains instructions for Claude on working with the platform.

Project documentation:
- `docs/user-guide/`: user guide covering all BABOK chapters
- `docs/use-cases/use-cases.md`: real-world scenarios for using the platform
- `docs/developer-guide/developer-guide.md`: technical architecture and the inner workings of the MCP servers, skills, and hooks

---

## Contributing

We welcome contributions from the community! Before submitting a pull request, please:

1. Read [CLA.md](CLA.md), the Contributor License Agreement. By submitting a PR, you automatically accept its terms.
2. Make sure all tests pass: `pytest tests/`
3. If you're adding a new MCP server or skill, add the corresponding tests to `tests/`.
4. For larger changes, we recommend opening an Issue first to discuss the approach.

For questions, issues, and feature requests, use [GitHub Issues](../../issues). For other inquiries, email chaussky@gmail.com.

---

## License and commercial use
Copyright (c) 2026 Anatoly Chaussky

AInalyst is distributed under the **GNU AGPL v3** license.

**Free for:**
- Business analysts using the platform locally for their own work
- Companies deploying the platform within their own infrastructure for their own analysts

**A commercial license is required for:**
- Building SaaS services on top of the platform
- Embedding the code in closed-source commercial products
- Developing paid graphical interfaces on top of the platform
- Enterprise agreements with guarantees and support

For production, SaaS, or proprietary use, see [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) (commercial license; contact chaussky@gmail.com).

The change history is in [CHANGELOG.md](CHANGELOG.md).

For questions about commercial licensing, custom development (additional MCP servers), or deployment in a closed/air-gapped environment with local models:

**Anatoly Chaussky**  
Email: chaussky@gmail.com  
LinkedIn: https://www.linkedin.com/in/anatole-tchaoussky-82957a40b/
