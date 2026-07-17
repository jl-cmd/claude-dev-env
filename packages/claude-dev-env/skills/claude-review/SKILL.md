---
name: claude-review
description: >-
  Thorough built-in Claude Code full-diff review; `/code-review xhigh --fix` on
  opus; host-aware invoker and claude_chain_runner. Triggers: claude-review,
  /claude-review, code-review xhigh --fix, thorough review on opus, chain runner
  review, ultra-review, invoke_code_review, full-diff local code review.
---

# Claude Review

Runs the thorough built-in Claude Code review on the full `origin/main...HEAD`
diff: static sweep first when a converge loop calls this skill, then
`/code-review xhigh --fix` pinned to **opus**, host-aware in-session or chain
via `invoke_code_review.py` / `claude_chain_runner`.

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

### Step 2 — Invoke host-aware review

**Execute** the package invoker (do not reimplement host detect, empty stdin,
dirty-tree, or JSON outcome):

```bash
python "$HOME/.claude/scripts/invoke_code_review.py" \
  --cwd "$(git rev-parse --show-toplevel)" \
  --session-model <session-model-alias>
```

- Prompt constant: `/code-review xhigh --fix`
- Model pin: `opus`
- Chain path: `claude_chain_runner.run_claude` with `-p`, that prompt, `--model opus`,
  JSON output, `bypassPermissions`
- Stdin: empty stream; cwd: PR worktree
- Chain never commits and never pushes

Stdout is one JSON object only:
`{mode, served_command, returncode, dirty_tree}`.

Mode decision (first match):

| Mode | When | Action |
|---|---|---|
| `in_session` | Claude host and session model is opus | Run `/code-review xhigh --fix` in this session with no path args (full branch diff vs `origin/main`) |
| `chain` | Third-party host, or Claude on any non-opus model | Helper already ran the headless spawn; read JSON fields |

Third-party hosts **always** chain.

### Step 3 — Interpret outcome

Full-diff rule and clean-stamp contract:
[reference/full-diff-and-clean-stamp.md](reference/full-diff-and-clean-stamp.md).

| Outcome | Predicate | Next |
|---|---|---|
| Failed review | `returncode != 0`, or chain with null `served_command` | Do not stamp clean; report failure |
| Fixes applied | Successful serve and `dirty_tree` true | Invoke `pr-fix-protocol` (converge) or report dirty tree |
| Clean | Successful serve and `dirty_tree` false | Stamp clean when the caller uses `code_review_clean_at` |

Helper predicate: `is_code_review_clean_stamp_allowed` is true only for the clean
row. `dirty_tree` false on a failed serve is **not** clean.

## Ground rules

- **One capability:** thorough built-in `/code-review xhigh --fix` on opus over the
  full diff, via the host-aware invoker.
- **Full diff only:** never delta-scope, single-file scope, or bugbot-flagged paths.
- **Compose:** static sweep scripts and `pr-fix-protocol` stay external.
- **Effort token is `xhigh`:** not `high`, not `max`.
- **Reuse invoker:** `scripts/invoke_code_review.py` + `code_review_constants.py`;
  do not clone host-detect / chain / dirty-tree logic into this skill folder.

## Examples

<example>
User: `/claude-review`
Claude: [confirms clean worktree; runs invoke_code_review.py with session model;
on chain mode reads JSON; reports clean or dirty_tree / failure]
</example>

<example>
User: "thorough review on opus" / "ultra-review this branch"
Claude: [same procedure; colloquial ultra-review maps to this skill]
</example>

<example>
pr-converge CODE_REVIEW phase
Claude: [static sweep first; then this skill's invoker path; on dirty_tree runs
pr-fix-protocol, push, re-enter CODE_REVIEW; on clean stamps code_review_clean_at]
</example>

## Gotchas

- **`xhigh` vs `high`:** Docs and the invoker must both say `xhigh`. Older copy and
  constants used `high`; the locked prompt is `/code-review xhigh --fix`.
- **Chain needs a trusted workspace:** Headless `bypassPermissions` only works when
  the worktree is trusted for unattended tool use.
- **`session_id` is cwd-scoped:** Chain spawns do not share the parent session id;
  each run is a fresh headless turn in the PR worktree.
- **`dirty_tree` false on failed serve is not clean:** A failed chain often leaves
  the tree clean. Stamp only when serve succeeded **and** the tree is clean.
- **In-session still needs porcelain check:** After in-session `/code-review`, treat
  non-empty `git status --porcelain` as fixes applied (`dirty_tree` equivalent).
- **No GitHub review threads:** Built-in `/code-review` does not post PR review
  threads; reply-and-resolve is N/A for this surface.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Hub: when, refusals, sub-skills, process, gotchas |
| `CLAUDE.md` | Package map for agents opening this skill |
| `reference/full-diff-and-clean-stamp.md` | Full-diff rule, JSON outcome shape, clean-stamp contract |
| `reference/process-tasks.md` | Task-seed catalog for a full review pass |

## Folder map

- `SKILL.md` — orchestration and invoker contract.
- `CLAUDE.md` — purpose, trigger, key files.
- `reference/` — full-diff / clean-stamp detail and process task seeds.
- Invoker lives in package `scripts/invoke_code_review.py` (not under this skill).
