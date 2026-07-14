# Grok capability evals (opt-in only)

Live measurements of Grok Build capabilities used by the `grokify` skill wording.

**Manual / opt-in only.** These evals never gate default `npm test`, pr-check, or CI.

## Requirements

- `grok` on `PATH` and authenticated (`grok models` exits 0). The runner calls `grok` by default; set `GROK_BIN` to point it at another binary.
- Network access for the Grok API
- A writable platform temp directory (`$env:TEMP` on Windows, `$TMPDIR` / `/tmp` elsewhere)
- For E3, an agent `grok` can load under `--agent`. The runner passes the agent named by `GROK_CAPABILITY_EVAL_AGENT` (default `Explore`); set that variable to an agent your `grok` resolves when the default does not exist for you.

## Run

From the package root (`packages/claude-dev-env`):

```powershell
# Windows PowerShell
$env:GROK_CAPABILITY_EVALS = "1"
node skills/grokify/evals/run-capability-evals.mjs
```

```bash
# POSIX
GROK_CAPABILITY_EVALS=1 node skills/grokify/evals/run-capability-evals.mjs
```

From this skill folder (`packages/claude-dev-env/skills/grokify`):

```powershell
# Windows PowerShell
$env:GROK_CAPABILITY_EVALS = "1"
node evals/run-capability-evals.mjs
```

```bash
# POSIX
GROK_CAPABILITY_EVALS=1 node evals/run-capability-evals.mjs
```

Or pass `--run` without the env var (paths match the cwd above):

```powershell
# from package root
node skills/grokify/evals/run-capability-evals.mjs --run
# from this skill folder
node evals/run-capability-evals.mjs --run
```

Without `GROK_CAPABILITY_EVALS=1` or `--run`, the script prints how to opt in and exits 0 (no live calls).

## What it measures

| Eval | Assertion |
|------|-----------|
| E1 | `can_spawn_subagent_tool === true` and tool list includes `spawn_subagent` |
| E2 | `spawn_succeeded === true` (child reports `SPAWN_OK`) |
| E3 | `skill_read_ok === true` and `agent_definition_loaded === true` (skill file read under `--agent`) |
| E4 | Probe write under the eval cwd succeeds (soft: hooks log may show `global/settings` + `pre_tool_use`) |
| E5 | `has_workflow_tool === false` and `result === "no_tool"` (both fields agree on absence) |

Each live `grok` call uses a unique `--leader-socket` under a fresh temp directory so concurrent runs do not share a socket.

## Offline static guard

`../capability-claims.test.mjs` runs under package `npm test` (no live `grok`):

- `SKILL.md` must not contain `cannot spawn Claude subagents`
- `SKILL.md` and the handoff template must still mention `claude -p` for the advisor path

`parse-payload.test.mjs` also runs under package `npm test` (no live `grok`): it unit-tests the runner's output parser (`tryParseJsonObject`, `extractResultText`, `parsePayload`, `isWorkflowToolAbsent`).
