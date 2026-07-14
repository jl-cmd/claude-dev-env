# Flag profiles

Exact flag sets used by `spawn_grok_batch.py` and `grok_headless_runner.py`.
Constants live in `scripts/dev_env_scripts_constants/grok_worker_constants.py`
and `scripts/dev_env_scripts_constants/timing.py`.

You choose a profile per worker via `tool_profile` on the batch spec. The
launcher builds the argv; do not hand-roll a parallel flag set unless you are
debugging outside the batch launcher.

---

## Shared base flags (every worker)

The headless runner always passes:

| Flag | Value / source |
|---|---|
| `--prompt-file` | Assembled per-worker prompt path under the run state dir |
| `--cwd` | Worker `cwd` from the batch spec |
| `--output-format` | `json` |
| `--always-approve` | present (auto-approve tool runs) |
| `--max-turns` | Worker `max_turns` (default `8`) |
| `--leader-socket` | Unique per-worker socket path under the run state dir |
| `--debug-file` | Unique per-worker debug log (batch launcher adds this) |

Optional:

| Flag | When |
|---|---|
| `--agent <name>` | Worker `agent_name` is a non-null string |
| `--model <id>` | Only when `GROK_MODEL_PIN` in constants is non-empty |

The runner does not pass `--permission-mode` or `--reasoning-effort`. If you
invoke `grok` by hand outside the launcher, those CLI flags stay available on
the binary; the batch path does not set them.

---

## Profile: `readonly`

Batch field: `"tool_profile": "readonly"`.

Extra flags the batch launcher appends:

```
--disallowed-tools Write,Edit,Bash
```

When `"is_repo_only": true`, also:

```
--disable-web-search
```

Prompt header prepended by the launcher:

```
Tool profile: readonly. Do not write, edit, or run shell commands.
```

Use for investigation, file:line mapping, and plan input. Pair with the
read-only brief in `worker-briefs.md`.

---

## Profile: `build`

Batch field: `"tool_profile": "build"`.

Extra tool-restriction flags: none (full tool surface).

Prompt header prepended by the launcher:

```
Tool profile: build. Never commit, push, or call gh.
```

Use for edits and tests inside a closed file allow list. Pair with the build
brief in `worker-briefs.md`. The lead session owns git and `gh`.

---

## Leader socket rule

Every process — preflight probes, live ping, and each worker — gets its own
`--leader-socket` path under the run state directory.

- Batch workers: `grok-leader-<uuid>.sock` (minted per launch)
- Preflight auth probe: `grok-preflight-auth.sock`
- Preflight ping: `grok-preflight-ping.sock`

Never point two live processes at the same socket path.

---

## Stagger

`WORKER_STAGGER_SECONDS` is `15`. Worker index `i` sleeps `i * 15` seconds
before start (index 0 starts at once, index 1 after 15s, index 2 after 30s).
The batch launcher applies this; you do not sleep in the skill.

---

## `--agent` and user-level Claude config

When `agent_name` is set, the runner passes `--agent <name>`. Grok loads the
named agent charter from the **user-level** Claude config home (`~/.claude/`):

- `agents/` — agent definition files (for example `code-quality-agent.md`,
  `clean-coder.md`)
- `skills/`, `rules/`, `hooks/` — the rest of the installed Claude config the
  grok CLI reads for that run

Preflight role `bugteam` checks that `code-quality-agent.md` and
`clean-coder.md` exist under `~/.claude/agents/` and that the
`claude-dev-env` install manifest is present. Install or reinstall
`claude-dev-env` before a fleet that relies on those agents.

Pass `agent_name: null` (or omit the field) when the worker should run without
a named agent charter.

---

## Profile choice cheat sheet

| Work | `tool_profile` | `is_repo_only` | `agent_name` |
|---|---|---|---|
| Map call sites in-repo only | `readonly` | `true` | `null` or an audit agent |
| Research that may need the web | `readonly` | `false` | `null` |
| Closed edit + tests | `build` | ignored | often `clean-coder` |
| Audit-style read under a charter | `readonly` | as needed | `code-quality-agent` |
