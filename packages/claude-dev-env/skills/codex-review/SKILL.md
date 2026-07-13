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
- Classification is `down`: `/codex-review cannot complete: Codex reviewer is down.`

Gate exits other than 0 or 1 are blockers: stop without a probe or review invoke. Do not invent an opt-out refusal for a non-opt-out failure.

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
- [ ] Step 3 — Run classifying review
- [ ] Step 4 — Classify outcome
- [ ] Step 5 — Route findings (or stop on clean / down)
```

### Step 0: Opt-out gate

Before any other work, run:

```bash
python "$HOME/.claude/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer codex
```

- **Exit 0** — Codex reviews are disabled: refuse with the opt-out line above. Do not probe, review, or fix.
- **Exit 1** — continue.
- **Any other exit** — treat as a blocker and stop; do not skip the gate or continue as if it exited 1. Do not report the opt-out refusal line for a non-opt-out failure.

Gate semantics live in `reviewer-gates` ([../reviewer-gates/SKILL.md](../reviewer-gates/SKILL.md)). The shared script owns the token parse; this skill does not re-parse `CLAUDE_REVIEWS_DISABLED`.

### Step 1: Version and shape probe

Probe the local Codex CLI so the run fails closed when the binary is missing or the installed shape does not match the contract.

- **Contract owner:** [reference/cli-contract.md](reference/cli-contract.md) — probe command (`codex exec review --help`), minimum shape signals, and fail-as-`codex_down` rule.
- **Probe outcome:** continue only when the probe reports a supported shape. On failure, refuse with the probe refusal line above (skill class `down`).

### Step 2: Target pick

Choose what Codex reviews:

| Context | Target |
|---|---|
| PR-loop caller (or an open PR on the current branch) | Diff against the PR base branch (`--base`) |
| Standalone run with no PR | Uncommitted work via `--uncommitted` (staged + unstaged + untracked) |

Do not invent a synthetic commit range when a base branch is available. Loop-caller wiring for base-branch resolution lives in [reference/loop-integration.md](reference/loop-integration.md).

### Step 3: Run classifying review

Run Codex against the chosen target on the classifying path only.

- **Classifying command:** `codex exec [options] review --json …` — this is the only path that emits the success JSONL stream Step 4 reads. Full surface: [reference/cli-contract.md](reference/cli-contract.md).
- **Non-classifying form:** plain `codex review` (no `exec`, no `--json`) is not a classification input on the observed CLI; do not feed its stdout into Step 4.
- **`scripts/` surface:** this package's `scripts/` directory holds named constants only. The headless wrapper entrypoint is sister work and is not present here.
- **Interim classify path:** agents classify only from the `codex exec … review --json` JSONL stream via the skill-class map in Step 4. Do not invent a non-JSONL parse. Fail closed on probe miss, non-usable stream, or `codex_down`.

### Step 4: Classify outcome

Map the JSONL observation to exactly one skill-level class:

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
- **Fail closed** on opt-out, non-0/1 gate exit, probe failure, and `down`.
- **Preserve draft state** of any open PR; this skill does not flip ready.
- **Honor hooks** on any commit the fix protocol creates.

## Examples

<example>
User: `/codex-review`
Claude: [runs opt-out gate; on exit 1 probes Codex shape, picks base-branch or `--uncommitted` target, runs `codex exec … review --json`, classifies from JSONL, reports clean or routes findings; on non-0/1 gate exit stops as a blocker]
</example>

<example>
`CLAUDE_REVIEWS_DISABLED=codex`
Claude: `/codex-review is disabled via CLAUDE_REVIEWS_DISABLED.`
</example>

<example>
User: "babysit codex review on this PR"
Claude: [same flow; after findings, applies pr-fix-protocol, then re-runs the classifying review once for confirmation when the caller stays on this skill]
</example>

## Gotchas

- **Opt-out uses `CLAUDE_REVIEWS_DISABLED=codex`.** Step 0 exit 0 means refuse with the opt-out line; exit 1 means continue; any other exit is a blocker.
- **Only `codex exec … review --json` JSONL is classifiable.** Plain `codex review` stdout is non-classifying. Only a Step 4 `findings` class enters Step 5.
- **`scripts/` holds constants only.** The headless wrapper entrypoint is sister work; agents do not invent a non-JSONL parse in this package.
- **Uncommitted targets have no review threads.** Fix protocol reply-and-resolve applies only when a PR carries threads; local-only runs stop after the fix commit path the protocol allows without a PR.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Hub: opt-out, probe, target, classifying review, classify, fix handoff |
| `CLAUDE.md` | Package map for agents opening this skill |
| `reference/cli-contract.md` | Observed CLI surface, probe signals, `codex_down`, skill-class map |
| `reference/loop-integration.md` | PR-loop target pick and re-entry after fixes |
| `scripts/codex_review_scripts_constants/` | Named constants only (wrapper entrypoint is sister work) |

## Folder map

- `SKILL.md` — orchestration steps and refusals.
- `CLAUDE.md` — purpose, trigger, key files.
- `reference/` — cli-contract and loop-integration detail.
- `scripts/codex_review_scripts_constants/` — importable constants package (no wrapper entrypoint here).
