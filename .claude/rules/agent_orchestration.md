# Rules for the multi-agent layer

The platform ships four agents in `.claude/agents/`. This file describes how they fit
together in Claude Code; the methodology of each one lives in its own file and is not
repeated here.

| Agent | File | Owns |
|---|---|---|
| `analyst` | `.claude/agents/analyst.md` | dialogue-driven BABOK chapters, leads the BA one step at a time |
| `orchestrator` | `.claude/agents/orchestrator.md` | decomposition, routing, aggregation, serialization of writes |
| `worker_llm` | `.claude/agents/worker_llm.md` | reasoning over content → structured JSON, no file system |
| `worker_file` | `.claude/agents/worker_file.md` | reading files and calling the chapters' MCP tools |

All four are part of the platform. There is no reduced build in which the layer is
cut down to one agent.

The files are flat Markdown: the body of each agent is written in its own file, with
no shared includes and no build step. Claude Code reads these files as they are, and
a template marker left in one would be read by the agent as an instruction.

## Dispatch

- The **leading session plays `analyst`** — that is what `CLAUDE.md` already
  prescribes, and it stays true. `.claude/agents/analyst.md` is the same role packaged
  so it can also be launched in an isolated context.
- The leading session plays `orchestrator` when a task needs decomposition. The
  orchestrator is a layer to reach for, not one to route everything through: a task
  that is one reasoning step plus one tool call goes straight to the analyst.
- Worker steps are launched as subagents through the `Agent` tool. **If a subagent is
  unavailable — at the nesting limit, for instance — the caller performs the worker's
  step itself under the same contract.**
- The reasoning/writing boundary holds regardless of whether a step is its own
  subagent or a step of the leading session: reasoning and writing to disk never
  happen in the same step.

## What a subagent does and does not inherit

These are properties of the harness, and the agents' instructions depend on them:

- **Inherited:** `CLAUDE.md` at every level and the files in `.claude/rules/`. An agent
  file therefore never restates the platform rules — it would only create a second
  copy to drift out of sync.
- **Not inherited:** the conversation so far. A subagent starts with a fresh context
  and sees only the prompt it was launched with. Content to reason over, the
  `project_id`, the schema of the expected answer — all of it goes into that prompt.
- **The active phase is shared.** A subagent has no `.mcp.json` of its own: it sees the
  servers of the phase the leading session is in. Tools of other chapters are absent,
  not merely unavailable, and switching a phase requires a session restart by the BA.
- **MCP tool schemas may be deferred.** The tool name is visible while its schema is
  not loaded; calling it then fails. `ToolSearch` with `select:mcp__<server>__<tool>`
  loads it. An agent must not conclude from this that the tool does not exist.
- **A new or edited agent file is picked up only after a session restart** (`/restart`).
  Editing `.claude/agents/*.md` mid-session changes nothing until then.

## Tool grants are boundaries, not conveniences

`tools:` in an agent's frontmatter is a strict allowlist — anything absent from the
list is absent from the agent, MCP tools included. The grants are chosen for that
effect:

- `worker_llm` gets `Read` and nothing else, so it cannot write an artifact even by
  mistake. Widening this grant removes the boundary rather than adding a convenience.
- `orchestrator` gets no `Write`, no `Bash` and no MCP tools: it routes, it does not
  save.
- `analyst` and `worker_file` get the MCP servers by pattern (`mcp__babok-ch3`, …), so
  the grant follows the servers in `phase.py` instead of listing 114 tool names.

## Return and error contract

- `worker_llm` returns structured JSON matching the requested schema, or a typed
  failure with a reason and a repeatable/not marker.
- `worker_file` returns the tool's message as it came, plus whether a retry could help.
- Chapter tools answer with readable text (`✅` / `❌`), not exit codes. Nothing in this
  platform returns a status number, and an agent must not invent one.
- The orchestrator serializes writes to the same artifact. The single JSON writer makes
  each write atomic and keeps the previous versions in `.history/`, but it does not
  merge: two parallel writes to one name lose one of them.
- Platform rule, unchanged here: warn, don't block. Partial success is returned with
  the list of what is unfinished, not turned into a hard stop.

## Anti-patterns

- ❌ Restating `CLAUDE.md` or the other rules inside an agent file — they are inherited.
- ❌ Widening `worker_llm`'s grant, or letting `worker_file` reason over content.
- ❌ Writing into `governance_plans/` with `Write` or `Bash` instead of a chapter tool.
- ❌ Two workers writing the same artifact in parallel without serialization.
- ❌ Inserting the orchestrator into a task that is one step.
- ❌ Assuming a worker can switch the phase, or that a tool from another chapter is
  reachable from inside a subagent.
