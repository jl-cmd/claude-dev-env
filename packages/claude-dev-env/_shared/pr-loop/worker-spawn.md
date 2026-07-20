# Worker-spawn protocol

Single home for the worker-spawn dispatcher contract and for Claude-only
slash-step host routing. Skills that need a role-bound headless worker call
[`scripts/resolve_worker_spawn.py`](../../scripts/resolve_worker_spawn.py)
(or import `resolve_worker_spawn`) and read this page for the tier walk, inputs,
JSON result shape, host rules, and setup. Skills that run a Claude-only slash
step (for example `/code-review`) read the code-review host-routing section.

Composed helpers (preflight, headless runners, and the code-review invoker)
stay documented at their own modules; this page states how callers use them.

## Three tiers

Walk order is fixed: soft-gate preflight for tier 1, then tier 1, then host
branching for tiers 2 and 3.

| Tier | Name | Who runs it |
|---|---|---|
| 1 | Grok headless | Python helper: `grok_worker_preflight` then `grok_headless_runner.run_headless_worker` |
| 2 | `claude_agent_required` | **Not** the Python helper. A stop signal so the **calling skill / harness** runs the Claude Code Agent tool itself |
| 3 | Claude headless | Python helper: `claude_chain_runner.run_claude` with `-p --output-format json --agent <stem>`, prompt body on stdin from the prompt file, and subprocess `cwd` set to the caller's working directory |

### `claude_agent_required` boundary

A Python helper cannot spawn Claude Code Agent-tool subagents. On a **Claude**
host, when the claude headless tier is **not** enabled (`--enable-claude-tier`
absent / `is_claude_tier_enabled=False`), a grok fallthrough records tier 2 with
reason `claude_agent_required`, leaves `tier_used` null, and returns. The
calling skill must then run the Agent tool in-process.

On a **ThirdParty** host, or when the claude tier is enabled on a Claude host,
the dispatcher continues to tier 3.

## Tier-1 fleets via grok-spawn

For a fleet of tier-1 grok workers (batch spec in, reports out), use the
**grok-spawn** skill when that skill is installed on the host (it ships on a
sibling stack and is not part of this dispatcher page). When present, that
skill owns the batch playbook and flag profiles under its reference docs.
This page stays the single-worker dispatcher contract (`resolve_worker_spawn`).

The calling session owns verification and every commit, push, or GitHub post.
Workers never commit or post.

## Required inputs

### CLI

```
python resolve_worker_spawn.py \
  --role <role> \
  --prompt-file <path> \
  --cwd <dir> \
  --run-temp-dir <dir> \
  [--timeout-seconds N] \
  [--enable-claude-tier]
```

| Flag | Required | Meaning |
|---|---|---|
| `--role` | no (default `bugteam`) | Role name for preflight agent-set checks; mapped to the primary agent stem for headless `--agent` (for example `bugteam` → `code-quality-agent`, `clean-coder` → `clean-coder`; unknown roles fall back to the raw role string) |
| `--prompt-file` | yes | Prompt file path for headless workers |
| `--cwd` | yes | Working directory for headless grok and claude workers |
| `--run-temp-dir` | yes | Run-scoped directory for leader sockets and preflight cache (created if missing) |
| `--timeout-seconds` | no (default `600`) | Per-tier timeout in seconds |
| `--enable-claude-tier` | no | Allow tier 3 on a Claude host |

There is no separate outcome-file flag. The result surface is **stdout JSON**
plus the process exit code.

### Import API

`resolve_worker_spawn(...)` takes keyword-only arguments:
`role`, `prompt_file`, `working_directory`, `timeout_seconds`,
`is_claude_tier_enabled`, `run_state_directory`, `max_turns`.
`encode_spawn_outcome` turns a `SpawnOutcome` into the same JSON shape the CLI
prints.

## JSON result shape

Stdout is one JSON object:

```json
{
  "tier_used": 1,
  "ok": true,
  "attempts": [
    {"tier": 1, "ok": true, "reason": null}
  ],
  "output": "<serving tier stdout>",
  "returncode": 0
}
```

| Key | Meaning |
|---|---|
| `tier_used` | Serving tier number (`1` or `3`), or `null` when no tier served |
| `ok` | Whether the serving call completed successfully |
| `attempts` | Ordered list of tries: each `{tier, ok, reason}` |
| `output` | Captured stdout from the serving tier (empty when none) |
| `returncode` | Process return code from the last tier run (or config-error code) |

`attempts` is in tried order. A Claude-host stop records tier `2` with
`reason: "claude_agent_required"`. Preflight or grok fallthrough reasons use the
preflight/runner classification strings (for example `grok_binary_missing`,
`usage_limit`).

### Exit codes

| Code | Meaning |
|---|---|
| `0` | A tier served (`tier_used` is not null) |
| `2` | Exhausted — no tier served |
| `3` | Config error: the `--prompt-file` path is not an existing file (`output` = `prompt_file_missing`) or claude chain configuration missing or invalid |

## Host detection

After a grok fallthrough the dispatcher calls `detect_host_profile()` from
`tier_model_ids` (advisor scripts). Detection order:

1. `ADVISOR_HOST_PROFILE` when set — must be `Claude` or `ThirdParty` (any letter case).
2. `THIRD_PARTY` when truthy — `1`, `true`, `yes`, or `on`.
3. Default: `Claude`.

Profiles are the real names `Claude` and `ThirdParty` (not a separate Grok host
profile). Grok is tier 1 on every host; host profile only chooses the post-grok
branch (Agent-tool handoff vs headless claude chain).

## Code-review host routing

Claude-only slash steps need a Claude Code harness. The built-in
`/code-review` command is the main case. The host-routing pair is:

- `detect_host_profile()` from `tier_model_ids` — same host detection as the
  worker-spawn dispatcher above
- `invoke_code_review` — host-aware invoker for `/code-review` (lives next to
  `resolve_worker_spawn` under the package scripts tree)

Mode decision:

| Host profile | Session model | Mode | Who runs `/code-review` |
|---|---|---|---|
| `Claude` | `opus` | `in_session` | The calling skill runs the slash command in-process |
| `Claude` | any other alias | `chain` | Headless spawn through `claude_chain_runner` |
| `ThirdParty` | any | `chain` | Headless spawn through `claude_chain_runner` |

The review always runs at effort **xhigh** on model **opus**. Chain mode builds
a single-turn prompt `/code-review xhigh --fix`, pins `--model opus`, sets
subprocess `cwd` to the PR working tree, and reads stdin from the empty stream
so the spawn does not wait for input.

After a chain run, a non-empty `git status --porcelain` means the review
applied fixes. The calling host commits and pushes those fixes per the fix
protocol. The chain process never commits or posts. A clean stamp requires
`returncode == 0` and a non-null `served_command` plus a clean tree —
`dirty_tree` false alone is not enough when the chain failed or never served.

GitHub transport (`pr-loop-cloud-transport`) is a separate axis from this
harness branch. That skill routes `gh` vs MCP; it does not change which host
can run Claude-only slash commands.

## Leader-socket rule

Every concurrent grok process gets its own `--leader-socket` path under the
caller-supplied run temp directory. The headless runner mints a unique
`grok-leader-<uuid>.sock` per invocation. Preflight auth and ping probes use
their own fixed socket filenames under the same directory so they never share a
socket with a live worker.

## Cloud setup

Unattended grok auth uses the `XAI_API_KEY` environment variable. Install the
CLI via the vendor curl installer or the `@xai-official/grok` package. Keep
agent definitions and hook config in parity with `npx claude-dev-env` so the
preflight role-agent check and local `~/.claude` layout match what the worker
expects.

Use placeholders for account-specific values; do not hardcode personal paths or
keys in skills or docs.

## GitHub transport

`pr-loop-cloud-transport` is a separate axis. This utility never posts reviews,
opens PRs, or substitutes `gh` for MCP. GitHub reachability and cloud session
routing stay outside the worker-spawn contract.
