# User Guide
## AI-powered Platform AInalyst
**Download:** https://github.com/chaussky/ainalyst.git

**LinkedIn:** https://www.linkedin.com/in/anatole-tchaoussky-82957a40b/

---

# Introduction

---

## Why This Exists

Picture two business analysts. The first has five years of experience, knows BABOK by heart, and intuitively senses what to do at every stage of a project. The second is just starting out, or has spent years working "by feel," without a rigorous methodology. Both face the same challenges: stakeholders say different things, requirements keep changing, there's never enough time, and documentation piles up faster than anyone can make sense of it.

**AInalyst is built for everyone who works with requirements.**

The platform helps business analysts work according to the BABOK v3 methodology: thoroughly, consistently, and without wasted effort. For those who know BABOK well, it removes the routine work and speeds things up. For those less familiar with it, the platform becomes a reliable guide: step by step, task by task, with no risk of missing something important.

But business analysts aren't the platform's only audience.

**Product managers, project managers, and CTOs.** Sometimes a project has no dedicated business analyst, and a product manager, project manager, or technical director takes on those responsibilities instead. They usually have a high-level understanding of the product and the business processes, but not deep expertise in requirements analysis methodology. AInalyst steps in to help: it guides them through the process, asks the right questions at the right moment, points out what's important not to miss, and generates the necessary artifacts.

**Startup founders and new-product owners.** When budgets are tight, hiring a business analyst isn't always an option. But well-gathered requirements are the difference between a product that works and a product that has to be rebuilt. AInalyst helps gather requirements in a structured way and hand them off to the development team in a form they can actually work with.

The platform covers four key areas of business analyst work:
- **Business analysis planning** (BABOK Chapter 3)
- **Elicitation and collaboration** with stakeholders (Chapter 4)
- **Requirements life cycle management** (Chapter 5)
- **Strategy analysis** of current and future state (Chapter 6)
- **Requirements analysis and design** (Chapter 7)

You're not just getting an AI assistant that answers questions. You're getting a structured environment that walks you through BABOK best practices, tells you what to do next, warns you about risks, and takes on all the technical work with artifacts.

---

## How It Works

At the core of the platform is Claude, a large language model (LLM) from Anthropic. Of course, you could simply open a regular chat with Claude and ask it questions. That works. But this approach has a fundamental limitation: if you don't know what to ask and in what order, the chat becomes a smart but unstructured conversation partner. It will answer your question, but it won't tell you whether that's the right question for this point in the project.

AInalyst solves this problem through three layers:

**Claude Code**, an AI agent that doesn't just respond but acts: it reads files, runs commands, manages the project, and guides you through the process. It's the entry point for all your work with the platform.

**Skills**, 21 specialized modules, each of which deeply "knows" a specific BABOK task: how to carry it out correctly, what to pay attention to, which artifacts to create. This is built-in methodology expertise.

**MCP tools**, 22 servers with 111 tools that perform specific analytical operations: building stakeholder registries, analyzing interview transcripts, creating traceability matrices, assessing risks, drafting requirements specifications.

Together, these three layers create something a regular chat can't offer: a clear working framework that carries you from the start of the project to the final artifact. The platform knows the methodology; you just need to know your project.

---

## You Don't Need to Memorize Anything

This is, perhaps, the most important thing to understand about AInalyst.

**You don't need to know the names of the skills. You don't need to know the names of the MCP tools. You don't need to remember any commands.**

Just talk to AInalyst in plain language:

> *"I need to get ready for an interview with the CFO"*

> *"I have a meeting transcript, I need to elicit requirements from it"*

> *"A change request just came in, help me assess it"*

AInalyst will figure out on its own which skill and which tools are needed, and run them. You talk, the platform works.

---

## Your Area of Responsibility

The platform takes care of the methodology and the technical work. But three things remain your responsibility.

### Inputs and Results

All input information (interview transcripts, meeting minutes, business documents, regulations) goes into the **`inputs/`** folder. Just copy the files there and tell AInalyst what to process.

The platform saves all its output to the **`governance_plans/reports/`** folder in Markdown format. These are your working artifacts: plans, registries, specifications, minutes. If you need a PDF, convert the Markdown file with any tool you like (for example, the "Print to PDF" option in VS Code), or just ask AInalyst to convert it.

The **`governance_plans/data/`** folder is internal. It holds the JSON files the platform uses internally: the requirements graph, prioritization data, assessment results. You don't need to go in there; it's the platform's internal "memory" of the project.

### Context and Decisions

AInalyst will ask you questions at key moments: when you need to choose a methodology, set priorities, approve requirements, or assess risks. It will give recommendations and warn you about the consequences, but the final decision is always yours. That's how it should be: methodology helps you make a good decision, but it doesn't make the decision for you.

### Phase Management

The platform runs in **active-phase mode**: at any given moment, only the MCP tools needed for the current stage of the project are loaded. This matters a great deal: LLMs have a limited context window, and loading all 22 MCP servers at once would degrade the quality of the platform's work.

Five phases are available:

| Phase | When to use |
|------|-------------------|
| `planning` | New project, BA plan, stakeholder map |
| `elicitation` | Interviews, workshops, meeting minutes |
| `lifecycle` | Traceability, prioritization, CRs, requirements approval |
| `analysis` | as-is / to-be analysis, gap analysis, risks, change strategy |
| `design` | Specification, verification, validation, design options |

AInalyst keeps track of phases and will tell you when it's time to switch. But you can also do it yourself; the simplest way is to just tell it:

> *"Switch to the analysis phase"*

AInalyst will run the command itself. If you'd rather do it manually in the terminal:

```bash
python phase.py <phase_name>
```

For example: `python phase.py elicitation`

After switching phases, you'll need to restart the session with the `/restart` command. AInalyst will remind you to do this.

---

## Installing the Platform

To work with AInalyst you'll need:

1. **Python 3.10+**: make sure it's installed on your computer
2. **pip**: the Python package manager (usually comes bundled with Python)

Installation:

```bash
# 1. Clone the repository
git clone https://github.com/chaussky/ainalyst.git
cd ainalyst

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Open .env and fill in the API keys
```

After that, open the project folder in AInalyst and start talking. The platform is ready to go.

---

*Further in this guide, you'll find a detailed description of each BABOK chapter the platform covers: what tasks it solves, what artifacts it creates, and how to work with it at every stage of the project.*
