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

Gate semantics live in `reviewer-gates` ([../reviewer-gates/SKILL.md](../reviewer-gates/SKILL.md)). The shared script owns the token parse; this skill does not re-parse `CLAUDE_REVIEWS_DISABLED`.

### Step 1: Version and shape probe

Probe the local Codex CLI so the run fails closed when the binary is missing or the installed shape does not match the wrapper contract.

- **Contract owner:** [reference/cli-contract.md](reference/cli-contract.md) — probe commands, minimum shape, and fail signals.
- **Probe outcome:** continue only when the probe reports a supported shape. On failure, refuse with the probe refusal line above.

Wrapper and parser internals that implement the probe live with the cli-contract child; this step names the gate and its stop behavior.

### Step 2: Target pick

Choose what Codex reviews:

| Context | Target |
|---|---|
| PR-loop caller (or an open PR on the current branch) | Diff against the PR base branch |
| Standalone run with no PR | Uncommitted work (staged and unstaged), falling back to the working tree state the wrapper accepts |

Do not invent a synthetic commit range when a base branch is available. Loop-caller wiring for base-branch resolution lives in [reference/loop-integration.md](reference/loop-integration.md).

### Step 3: Invoke wrapper

Run the Codex review wrapper against the chosen target.

- **Contract owner:** [reference/cli-contract.md](reference/cli-contract.md) — wrapper entrypoint, required arguments (target, repo root, optional PR metadata), stdout/stderr shape, and exit codes.
- **This skill's job:** pass the Step 2 target and collect the wrapper outcome (`outcome_class`, `agent_message`, paths). Do not re-parse raw Codex streams by hand.

### Step 4: Classify outcome

Map the wrapper result plus the findings parser to exactly one class:

| Class | Meaning | Next action |
|---|---|---|
| `down` | Wrapper `outcome_class` is `codex_down` (tool failure, auth, crash) | Refuse with the down line; stop |
| `clean` | Wrapper completed and `parse_codex_findings(agent_message)` is empty | Report one-line clean summary; stop |
| `findings` | Wrapper completed and the parser returns one or more findings | Continue to Step 5 |

`run_codex_review` returns `completed` or `codex_down` plus captured text. `parse_codex_findings` turns `agent_message` into the findings list. Classification rules and payload fields live in [reference/cli-contract.md](reference/cli-contract.md).

### Step 5: Route findings into the shared fix protocol

When the class is `findings`:

1. Read `$HOME/.claude/skills/pr-fix-protocol/SKILL.md` (or invoke `pr-fix-protocol` by name when the `Skill` tool is available).
2. Pass the findings payload, PR scope when present, and worktree path.
3. Apply the protocol end to end — failing test first when behavior is at stake, one fix commit, push when the caller requires it, reply and resolve per thread when the review is on a PR.

This skill does not restate the fix sequence. Orchestrator callers that re-enter after a push follow [reference/loop-integration.md](reference/loop-integration.md).

## Ground rules

- **One capability:** run Codex review and classify; fixes go through `pr-fix-protocol`.
- **Compose, do not rebuild:** opt-out via `reviews_disabled.py`; fixes via `pr-fix-protocol`.
- **Fail closed** on opt-out, probe failure, and `down`.
- **Preserve draft state** of any open PR; this skill does not flip ready.
- **Honor hooks** on any commit the fix protocol creates.

## Examples

<example>
User: `/codex-review`
Claude: [runs opt-out gate, probes Codex shape, picks base-branch or uncommitted target, invokes wrapper, reports clean or routes findings]
</example>

<example>
User: "babysit codex review on this PR"
Claude: [same flow; after findings, applies pr-fix-protocol, then re-invokes wrapper once for confirmation when the caller stays on this skill]
</example>

<example>
`CLAUDE_REVIEWS_DISABLED=codex`
Claude: `/codex-review is disabled via CLAUDE_REVIEWS_DISABLED.`
</example>

## Gotchas

- **`--reviewer codex` is the opt-out token.** `reviews_disabled.py --reviewer codex` accepts the `codex` token. Exit 0 refuses the skill; exit 1 continues.
- **Raw Codex CLI output is not the findings format.** Step 4 maps the wrapper outcome and `parse_codex_findings` output into `down` / `clean` / `findings` before Step 5.
- **Uncommitted targets have no review threads.** Fix protocol reply-and-resolve applies only when a PR carries threads; local-only runs stop after the fix commit path the protocol allows without a PR.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Hub: opt-out, probe, target, wrapper, classify, fix handoff |
| `CLAUDE.md` | Package map for agents opening this skill |
| `reference/cli-contract.md` | CLI probe, wrapper, and classification contracts |
| `reference/loop-integration.md` | PR-loop target pick and re-entry after fixes |
| `scripts/run_codex_review.py` | Wrapper entrypoint: invoke Codex; return completed or codex_down plus agent_message |
| `scripts/parse_codex_findings.py` | Parse reviewer text into structured or freeform findings |
| `scripts/codex_down_classifier.py` | Map wrapper failures to the `down` class |
| `scripts/codex_usage_probe.py` | Weekly usage probe for the conditional Codex gate |
| `scripts/codex_review_scripts_constants/` | Named constants for the scripts above |
| `scripts/fixtures/` | Sample Codex outputs for script tests |

## Folder map

- `SKILL.md` — orchestration steps and refusals.
- `CLAUDE.md` — purpose, trigger, key files.
- `reference/` — cli-contract and loop-integration detail.
- `scripts/` — wrapper, parser, classifier, usage probe, tests, and fixtures.
- `scripts/codex_review_scripts_constants/` — importable constants for the scripts.
