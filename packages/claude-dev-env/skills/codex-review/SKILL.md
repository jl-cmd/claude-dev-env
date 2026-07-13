---
name: codex-review
description: >-
  Runs OpenAI Codex as a local PR or uncommitted-diff reviewer and routes
  findings into the shared fix protocol. Triggers: '/codex-review', 'codex
  review', 'run codex review', 'babysit codex review', 'codex as a PR reviewer'.
---

# Codex Review

Runs one Codex review pass against a chosen target, classifies the outcome, and hands findings to the shared fix protocol. Does not reimplement opt-out parsing or the fix sequence.

## When this skill applies

- The user wants Codex (the OpenAI Codex CLI) as a reviewer on the current PR branch, or on uncommitted work when no PR loop is active.
- The user asks to babysit or re-run Codex review after fixes.

## Refusals

Respond with the quoted line exactly and stop:

- Opt-out gate exit 0: `/codex-review is disabled via CLAUDE_REVIEWS_DISABLED.`
- Version or shape probe reports Codex unavailable: `/codex-review cannot run: Codex CLI is missing or the shape probe failed.`
- Wrapper classifies `down`: `/codex-review cannot complete: Codex reviewer is down.`

Gate exits other than 0 or 1 (including the shared gate rejecting `--reviewer codex`) are blockers: stop without a probe or wrapper call. Do not invent an opt-out refusal for a parse failure.

## Sub-skills

| Skill | When | Produces |
|---|---|---|
| `reviewer-gates` | Step 0 — opt-out semantics for external reviewers | Gate contract for `reviews_disabled.py`; refusal line shape |
| `pr-fix-protocol` | Step 5 — classification is `findings` | Fix sequence, reply-and-resolve unit, unresolved-thread sweep |

If `pr-fix-protocol` is not installed when findings exist, stop with: `/codex-review needs the pr-fix-protocol skill to apply findings.`

## Process checklist

```
- [ ] Step 0 — Opt-out gate
- [ ] Step 1 — Version and shape probe
- [ ] Step 2 — Target pick
- [ ] Step 3 — Invoke wrapper
- [ ] Step 4 — Classify outcome
- [ ] Step 5 — Route findings (or stop on clean / down)
```

### Step 0: Opt-out gate

Before any other work, run:

```bash
python "$HOME/.claude/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer codex
```

- **Exit 0** — Codex reviews are disabled: refuse with the opt-out line above. Do not probe, wrap, or fix.
- **Exit 1** — continue.
- **Any other exit** — the shared gate rejects the `--reviewer` argument. Known tokens are `bugbot`, `bugteam`, and `copilot`; `codex` is not among them, so this invocation exits with a parse failure (exit 2). Treat that parse failure as a blocker and stop; do not skip the gate or continue as if it exited 1. Do not report the opt-out refusal line for a parse failure.

Gate semantics live in `reviewer-gates` ([../reviewer-gates/SKILL.md](../reviewer-gates/SKILL.md)). The shared script owns the token parse; this skill does not re-parse `CLAUDE_REVIEWS_DISABLED`.

### Step 1: Version and shape probe

Probe the local Codex CLI so the run fails closed when the binary is missing or the installed shape does not match the contract.

- **Contract owner:** [reference/cli-contract.md](reference/cli-contract.md) — probe command (`codex exec review --help`), minimum shape signals, and fail-as-`codex_down` rule.
- **Probe outcome:** continue only when the probe reports a supported shape. On failure, refuse with the probe refusal line above (skill class `down`).

### Step 2: Target pick

Choose what Codex reviews:

| Context | Target |
|---|---|
| PR-loop caller (or an open PR on the current branch) | Diff against the PR base branch |
| Standalone run with no PR | Uncommitted work (staged and unstaged), falling back to the working tree state the wrapper accepts |

Do not invent a synthetic commit range when a base branch is available. Loop-caller wiring for base-branch resolution lives in [reference/loop-integration.md](reference/loop-integration.md).

### Step 3: Invoke wrapper

Run the Codex review wrapper against the chosen target.

- **CLI surface:** [reference/cli-contract.md](reference/cli-contract.md) — raw command forms (`codex review`, `codex exec … review`), option ordering, success JSONL stream, finding-bullet text shape, and `codex_down` failure classes.
- **This skill's job:** pass the Step 2 target and collect a structured outcome for classification. Do not parse raw Codex stdout inline in these steps; the wrapper owns that boundary.

### Step 4: Classify outcome

Map the wrapper result to exactly one skill-level class:

| Class | Meaning | Next action |
|---|---|---|
| `down` | Codex did not produce a usable review (tool failure, auth, crash) | Refuse with the down line; stop |
| `clean` | Review completed with no findings against the target | Report one-line clean summary; stop |
| `findings` | Review completed with one or more addressable findings | Continue to Step 5 |

#### Skill class ↔ CLI observation map

| Skill class | Maps from (cli-contract) | Signal |
|---|---|---|
| `down` | `codex_down` rows; unrecognized probe shape | Non-usable review (exit 1/2 failures, config/auth/model errors, probe miss) |
| `clean` | Success stream (exit 0 JSONL) with no finding bullets in the `agent_message` body | Usable review, zero addressable findings |
| `findings` | Success stream (exit 0 JSONL) whose `agent_message` carries one or more `- [P#] …` bullets | Usable review with addressable findings |

Raw CLI failure vocabulary is `codex_down` only ([reference/cli-contract.md](reference/cli-contract.md)). Skill steps and loop re-entry use `down` / `clean` / `findings`.

### Step 5: Route findings into the shared fix protocol

When the class is `findings`:

1. Read `$HOME/.claude/skills/pr-fix-protocol/SKILL.md` (or invoke `pr-fix-protocol` by name when the `Skill` tool is available).
2. Pass the findings payload, PR scope when present, and worktree path.
3. Apply the protocol end to end — failing test first when behavior is at stake, one fix commit, push when the caller requires it, reply and resolve per thread when the review is on a PR.

This skill does not restate the fix sequence. Orchestrator callers that re-enter after a push follow [reference/loop-integration.md](reference/loop-integration.md).

## Ground rules

- **One capability:** run Codex review and classify; fixes go through `pr-fix-protocol`.
- **Compose, do not rebuild:** opt-out via `reviews_disabled.py`; fixes via `pr-fix-protocol`.
- **Fail closed** on opt-out, gate parse failure, probe failure, and `down`.
- **Preserve draft state** of any open PR; this skill does not flip ready.
- **Honor hooks** on any commit the fix protocol creates.

## Examples

<example>
User: `/codex-review`
Claude: [runs opt-out gate; on exit 1 probes Codex shape, picks base-branch or uncommitted target, invokes wrapper, reports clean or routes findings; on non-0/1 gate exit stops as a blocker]
</example>

<example>
User: "babysit codex review on this PR"
Claude: [same flow; after findings, applies pr-fix-protocol, then re-invokes wrapper once for confirmation when the caller stays on this skill]
</example>

## Gotchas

- **`--reviewer codex` is the token this skill passes.** The shared gate's known tokens are `bugbot`, `bugteam`, and `copilot`. Step 0 therefore exits with a parse failure (not 0 or 1). Treat that as a blocker and stop rather than skipping the gate. Opt-out exit 0 and the opt-out refusal line apply only when the gate accepts the token and the env list disables it.
- **Raw Codex CLI output is not the findings format.** Only a wrapper-classified `findings` payload enters Step 5.
- **Uncommitted targets have no review threads.** Fix protocol reply-and-resolve applies only when a PR carries threads; local-only runs stop after the fix commit path the protocol allows without a PR.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Hub: opt-out, probe, target, wrapper, classify, fix handoff |
| `CLAUDE.md` | Package map for agents opening this skill |
| `reference/cli-contract.md` | Observed CLI surface, `codex_down`, skill-class map |
| `reference/loop-integration.md` | PR-loop target pick and re-entry after fixes |
| `scripts/codex_review_scripts_constants/` | Named constants for skill scripts |

## Folder map

- `SKILL.md` — orchestration steps and refusals.
- `CLAUDE.md` — purpose, trigger, key files.
- `reference/` — cli-contract and loop-integration detail.
- `scripts/codex_review_scripts_constants/` — importable constants package.
