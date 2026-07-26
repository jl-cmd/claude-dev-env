# Loop integration

How `codex-review` plugs into PR-loop orchestrators and standalone runs. Orchestrator-owned detail lives in the linked pages; this page states each rule once and points outward.

## Target selection

| Caller context | Target |
|---|---|
| PR loop (`pr-converge`, `autoconverge`, `bugteam`, or an open PR on the branch) | Diff against the PR base branch (`base_branch=<pr.base.ref>` / `--base`) |
| Standalone (no PR) | Uncommitted work (`is_uncommitted=True` / `--uncommitted`: staged + unstaged + untracked) |

Do not invent a synthetic commit range when a base branch is available. Wrapper argv and probe rules live in [cli-contract.md](cli-contract.md).

## Classification vocabulary

Orchestrators re-enter on the skill-level classes from `SKILL.md` Step 4. CLI failures map through `codex_down` in [cli-contract.md](cli-contract.md).

| Skill class | CLI observation | Orchestrator next step |
|---|---|---|
| `down` | `codex_down` / probe miss | Mark the Codex gate skipped or stop per the caller's policy |
| `clean` | Success stream, no finding bullets | End the Codex gate |
| `findings` | Success stream with finding bullets | Shared fix path or `pr-fix-protocol` (see Findings handoff) |

## Where the gate sits

### `pr-converge` (tick-driven)

After the terminal Bugbot gate confirms HEAD (or sets `bugbot_down`) and **before** the machine convergence checklist:

1. Opt-out probe (`reviews_disabled.py --reviewer codex`)
2. Usage probe (`codex_usage_probe.py` → `is_codex_review_required`)
3. Skill / wrapper against the PR base branch
4. Classify → stamp, fix, or bypass
5. Convergence checklist (`check_convergence.py`)

Owner docs: [pr-converge per-tick Codex step](../../pr-converge/reference/per-tick.md#codex-review-step-conditional) and [convergence gate (g)](../../pr-converge/reference/convergence-gates.md#g-codex-review-gate-conditional-required).

### `autoconverge` (single autonomous run)

Phase order ends with terminal confirmation gates: Bugbot → Copilot → **CODEX** → FINALIZE (`check_convergence.py`).

The CODEX phase calls `runCodexGate(head)`, classifies via `classifyCodexGateOutcome`, then:

| Outcome kind | Loop action |
|---|---|
| `skip-token` | Set `codexDown`, clear stamp, advance to FINALIZE |
| `skip-usage` | Clear stamp (no down flag), advance to FINALIZE |
| `down` | Set `codexDown`, clear stamp, advance to FINALIZE |
| `fix` (non–code-standard) | Apply fixes via the shared fix path; re-enter CONVERGE |
| `fix` (standards-only) | Defer via `openStandardsFollowUpOnce`; stamp `codexCleanAt = head`; advance to FINALIZE |
| `clean` | Stamp `codexCleanAt = head`; advance to FINALIZE |
| `retry` | Re-run the gate on the same HEAD |

Owner doc: [autoconverge convergence CODEX phase](../../autoconverge/reference/convergence.md).

## Threshold rule

Shared helper only — never restate the numeric percent in callers.

- Probe: `python "$HOME/.claude/skills/codex-review/scripts/codex_usage_probe.py"` → JSON `{percent_left, window_reset, source}`.
- Decision: `is_codex_review_required(percent_left)` from the same module.
- **Required** only when `percent_left` is known and strictly greater than `WEEKLY_USAGE_GATE_THRESHOLD_PERCENT` (constant in `codex_review_scripts_constants/codex_usage_probe_constants.py`).
- **Skipped** when `percent_left` is null or at/below the threshold. Skip never blocks ready; do not stamp a clean SHA.

`check_convergence.py` applies the same helper on the machine checklist so agent path and checklist stay aligned.

## Opt-out token

```bash
python "$HOME/.claude/skills/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer codex
```

| Exit | Meaning |
|---|---|
| 0 | `CLAUDE_REVIEWS_DISABLED` lists `codex` — treat as bypass (`codex_down` / `codexDown`); do not probe usage or run the wrapper |
| 1 | Continue |

Gate semantics for the token live in `reviewer-gates`. This skill does not re-parse the env var.

`check_convergence.py` also honors an exported `codex` token (and `--codex-down`) so a re-check without flags still bypasses.

## State fields

| Field | pr-converge (job state / checklist) | autoconverge (run locals → checklist flags) |
|---|---|---|
| Clean stamp | `codex_clean_at` — HEAD SHA of last clean skill run, or `null` | `codexCleanAt` → `--codex-clean-at <SHA>` |
| Down / bypass | `codex_down` — `true` on wrapper `codex_down`, opt-out token, or explicit `--codex-down` | `codexDown` → `--codex-down` |

Rules (stated once):

- Stamp equals `current_head` only when the threshold rule requires a review.
- Push invalidates both fields (reset stamp to `null`, down to `false`); the next Codex entry re-probes opt-out and usage.
- While down/bypass is true, the machine gate never blocks ready.

Schema detail: [pr-converge state schema](../../pr-converge/reference/state-schema.md). Checklist labels and detail strings: [convergence gate (g)](../../pr-converge/reference/convergence-gates.md#g-codex-review-gate-conditional-required).

## Findings handoff

Split by caller — do not mix orchestrator vocabularies.

| Caller | On `findings` |
|---|---|
| Standalone `/codex-review` | Invoke `pr-fix-protocol` by name with the findings payload, PR scope, and worktree path. That protocol owns test-first fixes, commit, push, and reply-and-resolve when threads exist. |
| `pr-converge` terminal Codex step | Apply the **shared fix protocol** (same family as other pr-converge findings). Reset push-invalidated markers (all `*_clean_at`, `merge_state_status`, `bugbot_down`, `bugbot_acknowledged_at`, `codex_down`); set `phase = CODE_REVIEW`; schedule the next wakeup. Owner: [pr-converge per-tick Codex step](../../pr-converge/reference/per-tick.md#codex-review-step-conditional). |
| `autoconverge` CODEX phase | Do **not** call `pr-fix-protocol` by name. Route from the CODEX outcome table above — non-code-standard findings use the orchestrator shared fix path (`applyFixes`) and re-enter CONVERGE; standards-only findings defer a follow-up, stamp `codexCleanAt`, and advance to FINALIZE with no fix push. Owner: [autoconverge convergence CODEX phase](../../autoconverge/reference/convergence.md). |

Codex gate findings are local (no GitHub review thread). Reply-and-resolve applies only when a PR already carries threads from another reviewer.

## Re-entry after a fix

Orchestrators that keep looping after a push:

1. Re-resolve current HEAD (push cleared clean stamps and down flags).
2. Re-run internal converge / code-review phases as the orchestrator requires (`pr-converge` re-enters at `CODE_REVIEW` after a findings fix; `autoconverge` re-enters CONVERGE after non-standard fixes).
3. Re-enter the Codex gate against the same target class (PR base branch).
4. Re-classify: `clean` stamps and ends the Codex gate; `findings` follows the caller-specific handoff table above; `down` / opt-out / usage-skip advances without blocking.

Standalone skill re-entry (babysit mode): re-resolve HEAD, re-run the classifying path (`codex exec … review --json`) on the same target class, re-classify.
