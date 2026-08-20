# Sandbox workflow (Phase 1)

Stand up an isolated worktree where a hookless agent builds a proof-of-concept with zero standards friction. Only two safety gates stay live: personal-data blocking and destructive-command blocking.

## Step 1 — Isolated worktree

Invoke the `fresh-branch` skill to create a worktree off `origin/main`. Keep the returned `worktree_path` and `base_commit` for the promotion phase. If `fresh-branch` is not installed, stop with the refusal line from `SKILL.md`.

## Step 2 — Minimal safety settings

Run `scripts/build_sandbox_settings.py --out <worktree>/.prototype-sandbox-settings.json`.

It reads the live `~/.claude/settings.json`, resolves each safety hook's command (the correct interpreter and absolute path for this machine), and registers it on the matchers the sandbox needs — personal-data on Write, Edit, MultiEdit, and Bash; destructive-command on Bash. The write file carries only those two gates, plus an `env` block that sets `CLAUDE_DESTRUCTIVE_DENY_MODE`, so the destructive gate hard-denies a match. A hard deny holds under `--dangerously-skip-permissions`; an `ask` there is auto-resolved.

- Exit 0 → continue with the printed settings path.
- Exit 2 → one of the two safety hooks could not be resolved from the live settings. Stop; the sandbox cannot be contained without both. Report which one is missing.

## Step 3 — Prove containment

Run `scripts/probe_sandbox_safety.py --settings <settings path>`.

It feeds each safety hook a payload the hook is proven to block and confirms a hard-deny decision — the block that holds even under `--dangerously-skip-permissions`, unlike an `ask` prompt the flag auto-resolves. It runs each hook under the settings' `env` block, so the destructive gate runs in deny mode, the same way the launched session runs it.

- Exit 0 → both gates hard-deny their probe; the sandbox is contained.
- Exit 3 → a gate allowed its probe, returned an `ask`, or errored. Stop; do not launch an uncontained sandbox. This is a runtime check, not a code read (verify-runtime-state) — do not skip it.

## Step 4 — Launch the hookless session

Run `scripts/launch_sandbox.py --worktree <worktree_path> --settings <settings path> --task-file <task file>`.

It starts a headless `claude -p --bare --dangerously-skip-permissions --settings <settings path>` session in the worktree, so every standards gate is skipped and the two safety gates from the settings file are the only containment. Write the proof-of-concept task to the task file first; the sandbox agent cannot invoke other skills, so the task must be self-contained.

## Step 5 — Judge the result

Read what the sandbox built and decide whether the proof-of-concept proves the idea. On success, move to `promotion.md`. To discard, remove the worktree with `git worktree remove --force <worktree_path>`.
