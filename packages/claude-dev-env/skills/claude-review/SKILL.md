---
name: claude-review
description: >-
  Thorough built-in Claude Code full-diff review; `/code-review xhigh --fix` on
  opus; usage probe + host-aware invoker and claude_chain_runner. Triggers:
  claude-review, /claude-review, code-review xhigh --fix, thorough review on
  opus, chain runner review, ultra-review, invoke_code_review, full-diff local
  code review.
---

# Claude Review

Runs the thorough built-in Claude Code review on the full `origin/main...HEAD`
diff: static sweep first when a converge loop calls this skill, then a usage
probe, then `/code-review xhigh --fix` pinned to **opus**, host-aware
in-session or chain via `invoke_code_review.py` / `claude_chain_runner`.

## When this skill applies

- The user or a converge loop wants the thorough local built-in review on the
  full branch diff at effort **xhigh** on **opus**.
- A third-party host needs a headless chain spawn of that slash command.
- Callers name `claude-review`, `/claude-review`, or colloquial **ultra-review**
  for this path (folder name stays `claude-review`).

## Refusals

Respond with the quoted line exactly and stop:

- No PR worktree / not a git checkout: `/claude-review needs a git worktree as cwd.`
- Working tree has uncommitted edits before the review starts (standalone run):
  `/claude-review refuses a dirty tree; commit or stash first.`
- Host task tool missing when a multi-step process list must be tracked:
  `/claude-review needs a host task tool (TaskCreate / TodoWrite).`

## Sub-skills

| Skill | When | Produces |
|---|---|---|
| `pr-fix-protocol` | After a successful review leaves a dirty tree (converge callers) | Fix sequence, commit, push when the caller requires it |

If `pr-fix-protocol` is missing when fixes applied, stop with:
`/claude-review needs the pr-fix-protocol skill to apply review fixes.`

Static sweep uses existing shared scripts
(`code_rules_gate.py`, ruff, mypy, stem-matched pytest). This skill does not
reimplement those gates.

## Task seeding

Before Step 1, register every item in
[reference/process-tasks.md](reference/process-tasks.md) as a session task
(`TaskCreate` / `TodoWrite`). Work only from the task list. Mark complete with
evidence (PASS / FAIL+path / N/A+reason / exit code / JSON fields).

## Process

### Step 0 — Confirm worktree

Cwd must be the PR worktree (or the branch under review).

```bash
git rev-parse --show-toplevel
git rev-parse HEAD
git status --porcelain
```

Standalone runs require an empty porcelain status before the review. Converge
callers own re-entry after mid-flight fixes.

### Step 1 — Static sweep (converge callers)

When used from pr-converge / portable autoconverge, run the deterministic static
sweep **before** the built-in review:

```bash
python "$HOME/.claude/_shared/pr-loop/scripts/code_rules_gate.py" --base origin/main
```

Then ruff, mypy, and stem-matched pytest over the full `origin/main...HEAD`
changed set (same contract as pr-converge CODE_REVIEW). On any failure, hand off
to `pr-fix-protocol` (or the caller's fix path), commit and push, and re-run the
sweep. Do not start Step 2 until the sweep is clean.

Standalone `/claude-review` may skip the sweep when the user asked only for the
built-in review.

### Step 2 — Usage probe (Layer A)

The invoker auto-runs the session usage probe when
`--session-has-usage-left` is omitted or `unknown` (portable converge paths
rely on that chokepoint). A skill-side probe is optional redundancy when the
host can surface meters to the user. Compose the usage-pause resolver; do not
reimplement OAuth.

```bash
python "$HOME/.claude/scripts/claude_usage_probe.py"
```

Checkout path (from this monorepo): package `scripts/claude_usage_probe`
plus `scripts/dev_env_scripts_constants/claude_usage_probe_constants` (wraps
usage-pause `skills/usage-pause/scripts/resolve_usage_window.py`).

Stdout is one JSON object:
`{session_utilization, weekly_utilization, weekly_near_cap,
session_has_usage_left, source, probe_ok}`.

| Reading | Action |
|---|---|
| Probe succeeds, `session_utilization` is null | Proceed; note unknown session meter (`session_has_usage_left` null) |
| Probe succeeds, `session_utilization` ≥ threshold (`SESSION_UTILIZATION_NO_USAGE_THRESHOLD`, default **100**) | Primary session has **no usage left**; still run review **only through chain runner** — pass `--session-has-usage-left false` so Claude+opus does not take the in-session path |
| `weekly_near_cap` true | WARN only; do not block the review solely on weekly (same WARN posture as usage-pause) |
| Probe unavailable (`probe_ok` false / `source` unavailable) | Proceed; report `usage_probe: unavailable` — **never** block the whole skill on probe failure |

`session_has_usage_left` is true only when utilization is known and strictly
below the threshold; false at/above; null when unknown.

### Step 3 — Invoke host-aware review (Layer B)

**Execute** the package invoker (do not reimplement host detect, empty stdin,
dirty-tree, or JSON outcome). Omit the usage flag to auto-probe, or pass an
explicit decision:

```bash
python "$HOME/.claude/scripts/invoke_code_review.py" \
  --cwd "$(git rev-parse --show-toplevel)" \
  --session-model <session-model-alias> \
  [--session-has-usage-left <true|false|unknown>]
```

When the skill already probed, map into `--session-has-usage-left`:

| Probe `session_has_usage_left` | Flag value |
|---|---|
| true | `true` |
| false | `false` |
| null / probe unavailable | `unknown` (invoker re-probes or treats as unknown) |

- Prompt constant: `/code-review xhigh --fix`
- Model pin: `opus`
- **Headless path always uses** `claude_chain_runner.run_claude` (installed at
  `$HOME/.claude/scripts/claude_chain_runner.py`; package source
  `packages/claude-dev-env/scripts/claude_chain_runner.py`). The runner walks
  `~/.claude/claude-chain.json` and fails over **only** on usage-limit
  signatures (see `ALL_USAGE_LIMIT_SIGNATURES` in chain constants).
- Chain argv: `-p`, that prompt, `--model opus`, JSON output, `bypassPermissions`
- Stdin: empty stream; cwd: PR worktree
- Chain never commits and never pushes

Stdout is one JSON object only:
`{mode, served_command, returncode, dirty_tree}`.

Mode decision (first match):

| Mode | When | Action |
|---|---|---|
| `chain` | `session_has_usage_left` is false (primary drained) | Force headless chain even on Claude+opus |
| `in_session` | Claude host, session model is opus, usage left true/unknown | Run `/code-review xhigh --fix` in this session with no path args (full branch diff vs `origin/main`) |
| `chain` | Third-party host, or Claude on any non-opus model | Helper already ran the headless spawn; read JSON fields |

Third-party hosts **always** chain. Headless serves **must** go through
`claude_chain_runner` — that is the redundancy when the primary claude binary
is usage-limited mid-call.

### Step 4 — Interpret outcome

Full-diff rule and clean-stamp contract:
[reference/full-diff-and-clean-stamp.md](reference/full-diff-and-clean-stamp.md).

| Outcome | Predicate | Next |
|---|---|---|
| Failed review | `returncode != 0`, or chain with null `served_command` | Do not stamp clean; report failure |
| Fixes applied | Successful serve and `dirty_tree` true | Invoke `pr-fix-protocol` (converge) or report dirty tree |
| Clean | Successful serve and `dirty_tree` false | Stamp clean when the caller uses `code_review_clean_at`; then **Execute** the clean-comment poster script |

Helper predicate: `is_code_review_clean_stamp_allowed` is true only for the clean
row. `dirty_tree` false on a failed serve is **not** clean.

On the clean row, after the stamp path (or when standalone has a clean outcome):

```bash
python "$HOME/.claude/scripts/post_claude_review_clean_comment.py" \
  --cwd "$(git rev-parse --show-toplevel)" \
  --head-sha "$(git rev-parse HEAD)" \
  [--mode chain|in_session] \
  [--served-command <name>]
```

Portable converge emits this argv in `commands` from `after-code-review` when
the clean path stamps. Soft-fail: a post flake prints JSON with `posted=false`
and still leaves the clean stamp intact. Constants:
`dev_env_scripts_constants/post_claude_review_clean_comment_constants.py`.

## Ground rules

- **One capability:** thorough built-in `/code-review xhigh --fix` on opus over the
  full diff, via the host-aware invoker.
- **Two-layer redundancy:** (A) usage probe before invoke; (B) headless always via
  `claude_chain_runner`.
- **Full diff only:** never delta-scope, single-file scope, or bugbot-flagged paths.
- **Compose:** static sweep scripts, usage-pause resolver, and `pr-fix-protocol`
  stay external — no second OAuth client in this skill.
- **Effort token is `xhigh`:** not `high`, not `max`.
- **Reuse invoker:** `scripts/invoke_code_review.py` + `code_review_constants.py`;
  do not clone host-detect / chain / dirty-tree logic into this skill folder.

## Examples

<example>
User: `/claude-review`
Claude: [confirms clean worktree; runs Layer A probe
(`claude_usage_probe` / `claude_usage_probe_constants`); runs
`invoke_code_review` with session model and session-has-usage-left; on chain
mode reads JSON; reports clean or dirty_tree / failure]
</example>

<example>
User: "thorough review on opus" / "ultra-review this branch"
Claude: [same procedure; colloquial ultra-review maps to this skill]
</example>

<example>
pr-converge CODE_REVIEW phase
Claude: [static sweep first; usage probe; invoker path; on dirty_tree runs
pr-fix-protocol, push, re-enter CODE_REVIEW; on clean stamps code_review_clean_at]
</example>

## Gotchas

- **`xhigh` vs `high`:** Docs and the invoker must both say `xhigh`. Older copy and
  constants used `high`; the locked prompt is `/code-review xhigh --fix`.
- **Probe unavailable ≠ fail:** `probe_ok` false means report
  `usage_probe: unavailable` and continue with `--session-has-usage-left unknown`.
- **Primary drained → force chain:** When `session_has_usage_left` is false, pass
  `--session-has-usage-left false` so in-session Claude+opus is not used against
  a drained account; chain binaries still try to serve.
- **Chain failover only on usage-limit signatures:** `claude_chain_runner` walks
  `~/.claude/claude-chain.json` and advances only when a binary fails with a
  usage-limit signature; other failures stop the chain.
- **Chain needs a trusted workspace:** Headless `bypassPermissions` only works when
  the worktree is trusted for unattended tool use.
- **`session_id` is cwd-scoped:** Chain spawns do not share the parent session id;
  each run is a fresh headless turn in the PR worktree.
- **`dirty_tree` false on failed serve is not clean:** A failed chain often leaves
  the tree clean. Stamp only when serve succeeded **and** the tree is clean.
- **In-session still needs porcelain check:** After in-session `/code-review`, treat
  non-empty `git status --porcelain` as fixes applied (`dirty_tree` equivalent).
- **No GitHub review threads:** Built-in `/code-review` does not post PR review
  threads; reply-and-resolve is N/A for this surface. The clean-pass note is a
  single **issue comment** via the clean-comment poster script, not a review
  thread.
- **Clean comment is best-effort:** Post failure must not undo or block the
  clean stamp. The helper always exits `0` and is idempotent per HEAD SHA.
- **Weekly near-cap is WARN only:** Do not block the review solely on
  `weekly_near_cap` true.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Hub: when, refusals, sub-skills, process, gotchas |
| `CLAUDE.md` | Package map for agents opening this skill |
| `reference/full-diff-and-clean-stamp.md` | Full-diff rule, JSON outcome shape, clean-stamp contract |
| `reference/process-tasks.md` | Task-seed catalog for a full review pass |

## Folder map

- `SKILL.md` — orchestration, usage probe, and invoker contract.
- `CLAUDE.md` — purpose, trigger, key files.
- `reference/` — full-diff / clean-stamp detail and process task seeds.
- Runtime lives in package `scripts/` (not under this skill): usage probe,
  invoker, chain runner, and clean-comment poster.
