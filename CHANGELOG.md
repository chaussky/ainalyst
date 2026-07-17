# Changelog — AInalyst

All notable changes to the project are documented here.  
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
The project follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Changed
- The flagship version of the project is now in English. The Russian version is kept on the `ru` branch.

### Removed
- PDF export (`export_pdf.py`) and the `reportlab` dependency. Artifacts are produced as Markdown; convert them to PDF with a tool of your choice (for example `pandoc` or a Markdown editor's "Print to PDF").

---

## [1.0.0-beta] — 2026-04-07

> [!IMPORTANT]
> **Status: Public Beta.** First public release for open testing.
> We are actively validating the tools' logic under real-world production conditions.

### Added

**Platform architecture**
- BABOK phase system: `planning`, `elicitation`, `lifecycle`, `analysis`, `design`, `full`
- Phase switcher `phase.py` with a token-savings display
- SessionStart and PostToolUse hooks for automatic context and artifact notifications
- Rules for Claude Code: `artifacts.md`, `babok_process.md`
- PDF export utility `export_pdf.py`
- Integration with Confluence Cloud and Server/Data Center

**21 skills and 22 MCP servers (111 tools)**

| Chapter | Skill / MCP server |
|-------|-------------------|
| 3 | Business analysis planning (`planning_mcp.py`) |
| 4.1 | Prepare for elicitation (`elicitation_mcp.py`) |
| 4.2 | Conduct elicitation (`elicitation_conduct_mcp.py`) |
| 4.3 | Confirm elicitation results (`elicitation_confirm_mcp.py`) |
| 4.4 | Communicate elicitation results (`elicitation_communicate_mcp.py`) |
| 4.5 | Manage stakeholder collaboration (`elicitation_collaborate_mcp.py`) |
| 5.1 | Trace requirements (`requirements_traceability_mcp.py`) |
| 5.2 | Maintain requirements (`requirements_maintain_mcp.py`) |
| 5.3 | Prioritize requirements (`requirements_prioritize_mcp.py`) |
| 5.4 | Assess changes — CR (`requirements_assess_changes_mcp.py`) |
| 5.5 | Approve requirements (`requirements_approve_mcp.py`) |
| 6.1 | Analyze current state (`current_state_mcp.py`) |
| 6.2 | Define future state (`future_state_mcp.py`) |
| 6.3 | Assess risks (`risk_assessment_mcp.py`) |
| 6.4 | Change strategy (`change_strategy_mcp.py`) |
| 7.1 | Specify requirements (`requirements_spec_mcp.py`) |
| 7.2 | Verify requirements (`requirements_verify_mcp.py`) |
| 7.3 | Validate requirements (`requirements_validate_mcp.py`) |
| 7.4 | Requirements architecture (`requirements_architecture_mcp.py`) |
| 7.5 | Design options (`design_options_mcp.py`) |
| 7.6 | Value assessment and recommendation (`value_recommend_mcp.py`) |

**Documentation**
- User guide covering all BABOK chapters (`docs/user-guide/`)
- Platform use cases (`docs/use-cases/use-cases.md`)
- Developer guide (`docs/developer-guide/developer-guide.md`)

**Test coverage**
- 1,556 tests across 24 files — 100% passing
- Full coverage of all 21 BABOK MCP servers
- Integration pipeline tests for every BABOK chapter

**Licensing**
- GNU AGPL v3 for open use
- Commercial license for SaaS and proprietary integrations (`COMMERCIAL_LICENSE.md`)
- Contributor License Agreement (`CLA.md`)

---

## How to read this file

Each release contains the following sections:

- **Added** — new features
- **Changed** — changes to existing functionality
- **Fixed** — bug fixes
- **Removed** — removed features
- **Deprecated** — features that will be removed in an upcoming version
- **Security** — vulnerability fixes

---

[1.0.0]: https://github.com/chaussky/ainalyst/releases/tag/v1.0.0
