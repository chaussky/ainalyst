# Contributing to AInalyst

Thanks for your interest in the project! We welcome contributions from the community.

---

## Before you start

Please review [CLA.md](CLA.md) — the Contributor License Agreement.
By submitting a Pull Request, you automatically agree to its terms.

---

## How to contribute

### Report a bug

Open an [Issue](https://github.com/chaussky/ainalyst/issues) describing:
- What you were doing
- What you expected to happen
- What actually happened
- Python version, OS

### Suggest an improvement

Open an Issue tagged `enhancement` — describe the idea and why it's needed.
For larger changes, it's best to discuss the approach before writing code.

### Submit a Pull Request

1. Fork the repository
2. Create a branch: `git checkout -b feature/my-improvement`
3. Make your changes
4. Make sure the tests pass:
   ```bash
   pip install -r requirements-dev.txt
   pytest tests/
   ```
5. If you're adding a new MCP server or skill, add tests under `tests/`
6. Submit a PR describing your changes

---

## Project structure

Before working with the code, we recommend reviewing:

- `CLAUDE.md` — the main instruction file for Claude Code, platform architecture
- `docs/developer-guide/developer-guide.md` — detailed technical guide
- `skills/` — MCP servers and skills organized by BABOK chapter
- `tests/` — tests (unittest, no external dependencies required to run)

---

## Commercial development

If you need custom MCP servers, integrations, or a deployment in a closed
environment, reach out directly:

**Anatoly Chaussky**
Email: chaussky@gmail.com
LinkedIn: https://www.linkedin.com/in/anatole-tchaoussky-82957a40b/
