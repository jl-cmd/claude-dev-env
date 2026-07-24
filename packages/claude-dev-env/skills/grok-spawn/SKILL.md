---
name: grok-spawn
description: >-
  Spawn headless grok worker fleets via preflight and spawn_grok_batch.
  Triggers: /grok-spawn, spawn grok workers, grok worker fleet, run this with
  grok workers, headless grok batch.
---

# Grok Spawn

Orchestrator playbook for fleets of headless grok CLI workers. The scripts hold
the spawn logic; this skill names them and the order to call them. Scripts run
from `$HOME/.claude/scripts/` after install, or the package `scripts/` tree in
this repo.

## When to use

Use for a grok worker fleet, a headless grok batch, or `/grok-spawn`. Good fits:

- Fan-out read-only research across several paths or files.
- Parallel bite-sized build work where each worker owns one closed scope.

Skip this skill when the work needs live `SendMessage` coordination between
agents or Claude-only tools (Agent tool, warm session-advisor, Claude MCP
surfaces). For a single interactive Grok Build handoff paste, use `/grokify`.

**Refusal:** with no concrete worker tasks, reply `What should the grok workers
do? List each role in one line.` and stop.

## Constraints

- Workers never commit, push, or call `gh`. This session stages, verifies,
  commits, pushes, and posts to GitHub.
- Grok has no `SendMessage` and no Claude Agent tool.
- Preflight is a soft gate: a fallthrough reason means skip the fleet and use
  the next tier, not a hard failure.
- Every brief stands alone. A headless worker sees only its assembled prompt
  parts, so conversation-relative phrases ("as above") mean nothing.

## Process

Pick one fresh run-state directory for the whole fleet and reuse that path for
every step. It holds the sockets, prompts, reports, and spec.

### 1. Preflight (optional early abort)

`spawn_grok_batch.py` re-runs preflight before launch, so run this only to abort
before writing files.

```bash
python "$HOME/.claude/scripts/grok_worker_preflight.py" \
  --role bugteam --run-temp-dir "<run-dir>"
```

Add `--ping` for an opt-in live probe. Stdout is one line: `grok_preflight: ok`
(continue) or `grok_preflight: fallthrough reason=<reason>` (report the reason,
skip the fleet, fall to the next tier).

### 2. Scaffold the part files and batch-spec skeleton

Pass one `--worker role_name:profile` per worker. `profile` is `readonly` or
`build`; `role_name` is a lowercase slug.

```bash
python "$HOME/.claude/scripts/grok_batch_scaffold.py" \
  --run-temp-dir "<run-dir>" \
  --worker map-callsites:readonly --worker fix-timeout:build
```

It writes one shared `report-contract.md`, a `<role>.brief.md` and
`<role>.task.md` per worker, and `batch-spec.json` whose `prompt_parts` wire each
worker to `[brief, task, report-contract]`. Stdout JSON lists every written path.

### 3. Fill the scaffolded files

This session authors the task-specific content:

- Each `<role>.task.md`: the closed scope, exact absolute paths, and acceptance
  lines.
- Each `<role>.brief.md`: fill the bracketed fields.
- `batch-spec.json`: set each worker's `cwd` (replace
  `FILL_ME__absolute_worker_cwd`). Adjust `tool_profile`, `is_repo_only`,
  `agent_name`, `timeout_seconds`, and `max_turns` as the work needs — see
  [`reference/flag-profiles.md`](reference/flag-profiles.md).

### 4. Launch

```bash
python "$HOME/.claude/scripts/spawn_grok_batch.py" \
  --spec "<run-dir>/batch-spec.json" --run-temp-dir "<run-dir>"
```

The launcher gates preflight once, staggers worker starts, and prints one batch
summary JSON. Exit `0` only when preflight is usable and every worker is ok.

### 5. Collect reports

Read the summary JSON: `is_preflight_usable`, `preflight_reason`, and `workers`.
Each worker entry carries `role_name`, `tool_profile`, `returncode`,
`classification`, `is_ok`, `report_text`, `output_file`, `debug_file`,
`leader_socket`, and `prompt_file`.

Open each `output_file` and check the report-contract sections. For a failed
worker (`is_ok` false), route on `classification` (`usage_limit`,
`auth_failure`, `timeout`, `error`) and read its `debug_file`. A negative
`returncode` means no grok process produced it: `-1` timeout, `-2` launch
failure, `-3` the launcher raised before the process started (a missing
prompt-part file, for example).

### 6. Verify and own git / gh

Diff the worktrees the build workers touched, re-run the named tests, map each
acceptance line to evidence, then stage, commit, push, and post GitHub updates
yourself. Build workers stop at stage-ready edits and a written report.

## Composition

| Script | Role |
|---|---|
| `grok_worker_preflight.py` | Soft gate: binary, auth, install, optional ping |
| `grok_batch_scaffold.py` | Writes the part files and the wired batch-spec skeleton |
| `spawn_grok_batch.py` | Batch launch, stagger, report collect |
| `grok_headless_runner.py` | One-worker runner called by the launcher |

Sibling skill: `/grokify` for a single paste-ready interactive Grok Build
handoff.
