---
name: prototype
description: >-
  Isolated hookless worktree sandbox for zero-friction proof-of-concept builds, then a clean-room re-verification that promotes a successful POC into a real deploy. Triggers: prototype, /prototype, proof of concept, POC, spike, throwaway build, build without hooks, sandbox this idea, hookless worktree, prototype then ship, promote the prototype.
---

# Prototype

## Principle

Give a build the freedom to move fast, then make it earn the right to ship. Two phases, one hard wall between them:

- **Sandbox** — an isolated worktree where an agent runs under `claude --bare`, so none of the standards gates (TDD, code rules, verified-commit, plain-language, stage) fire. The agent builds a proof-of-concept with zero friction.
- **Promotion** — back in the normal, fully-hooked session, the successful POC goes through a clean-room re-verification before it becomes a commit and a pull request. Nothing from the sandbox rides along un-checked.

Two safety gates stay live even in the sandbox: personal-data blocking and destructive-command blocking. A worktree shares the real repo's `.git` store and `rm` reaches the whole disk, so these are containment, not the "delays" the sandbox is meant to shed.

## Gotchas

Highest-signal content. Append a bullet each time a run fails in a new way.

- A `--settings` file's hooks still load under `--bare` (the file is passed explicitly). That is the mechanism for keeping the two safety gates, not a bug.
- The two safety hooks must point at the real installed scripts and import their `*_constants` packages at runtime. `scripts/build_sandbox_settings.py` resolves each hook's command from the live `~/.claude/settings.json` and registers it on the matchers the sandbox needs — personal-data on Write, Edit, MultiEdit, and Bash; destructive-command on Bash — so the paths stay correct on any machine and both gates cover the write surface. Do not hand-write the hook paths or matchers, and do not inherit whatever matcher the live config happens to use (a personal-data gate wired only to a narrow tool leaves disk writes ungated).
- Under `--dangerously-skip-permissions` an `ask` decision is auto-resolved, so only a hard `deny` blocks a destructive command. The settings file carries an `env` block that sets `CLAUDE_DESTRUCTIVE_DENY_MODE`, which turns the destructive gate's terminal `ask` into a `deny`. The probe runs the gate under that env block and passes only on the hard deny.

**Refusal cases — first match wins:**

- **Not in a git repository.** Respond: `Prototype needs a git repo to branch a worktree from. Run this from inside one.`
- **The `fresh-branch` skill is not installed.** Respond: `Prototype composes fresh-branch to make the sandbox worktree, and it is not installed. Install claude-dev-env first.`
- **The `claude` CLI is not on PATH.** Respond: `The sandbox launches a headless claude session, and the claude CLI is not on PATH.`

## Process

Two phases. Run the sandbox phase first; run the promotion phase only when the POC succeeds and the user wants it shipped.

### Phase 1 — Sandbox

Follow `workflows/sandbox.md`. In short:

1. Invoke the `fresh-branch` skill to create an isolated worktree off `origin/main`. Keep its returned `worktree_path` and `base_commit`.
2. Run `scripts/build_sandbox_settings.py` to emit the minimal safety settings (personal-data and destructive-command gates only).
3. Run `scripts/probe_sandbox_safety.py --settings <path>` and confirm both gates block. Do not continue on a non-zero exit.
4. Run `scripts/launch_sandbox.py` to start the hookless `claude -p --bare` session in the worktree with those settings and the POC task.
5. Read what the sandbox built. Decide whether the POC proves the idea.

### Phase 2 — Promotion

Run only in the normal, fully-hooked session — never inside the sandbox. Follow `workflows/promotion.md`, which drives the clean-room task seeds in `reference/promotion-tasks.md`: fresh branch off live `origin/main`, POC content as an uncommitted diff, cleanup and privacy sweep, `code-verifier` in a fresh context, then `/commit` and a draft PR handed to a PR-loop skill. State the two honest limitations from `reference/honest-limitations.md`.

## Task seeding

At the start of Phase 2, register every item in `reference/promotion-tasks.md` as a session task (`TaskCreate`, or `TodoWrite` if that is the host tool). Work only from the task list. Mark each complete with evidence. Do not track promotion as a markdown checklist.

## Sub-skills

| Skill / agent | When | Produces | If missing |
|---|---|---|---|
| `fresh-branch` | Sandbox step 1; Promotion step 2 | isolated worktree JSON (`worktree_path`, `base_commit`, `repo_root`) | Refuse — see refusal cases |
| `privacy-hygiene` | Promotion step 5 | personal-data and secret sweep of the diff | Warn; do a manual review before continuing |
| `code-verifier` (agent) | Promotion step 6 | fresh-context verdict against the real diff; mints the commit-gate verdict | Stop; the commit gate will block anyway |
| `/commit` (command) | Promotion step 7 | conventional commit + push | Commit and push by hand per `git-workflow` |
| `autoconverge` (default; `pr-converge` or `bugteam` as alternatives) | Promotion step 9 | the PR converged to ready | Stop after the draft PR; tell the user to converge manually |

## Degree of freedom

Low on the skill's own mechanics — the launch flags and the promotion order are fragile with cliffs, so they live in scripts and a fixed task list, not in prose the agent reconstructs. High inside the sandbox — the sandboxed agent's build freedom is the whole point.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This hub — principle, gotchas, when-applies, process, sub-skills, file index |
| `workflows/sandbox.md` | Phase 1 steps: worktree, safety settings, probe, hookless launch |
| `workflows/promotion.md` | Phase 2 steps: the clean-room re-verification that drives the promotion task seeds |
| `reference/promotion-tasks.md` | Task-seed catalog for the clean-room protocol (register via the task tool) |
| `reference/honest-limitations.md` | The two fixed statements to make on every promotion |
| `scripts/build_sandbox_settings.py` | Emit the minimal safety `--settings`: resolve each hook's command from live settings, register it on the required matchers |
| `scripts/launch_sandbox.py` | Launch the hookless `claude -p --bare` sandbox session in the worktree |
| `scripts/probe_sandbox_safety.py` | Prove both safety gates block before trusting the sandbox |

## Folder map

- `SKILL.md` — hub.
- `workflows/` — the two phase workflows.
- `reference/` — promotion task seeds and the honest-limitation statements.
- `scripts/` — the settings builder, the launcher, the safety probe, their `prototype_scripts_constants` package, and paired tests.
