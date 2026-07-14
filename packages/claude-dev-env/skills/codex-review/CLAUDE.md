# codex-review

Runs OpenAI Codex as a local PR or uncommitted-diff reviewer: opt-out gate, version/shape probe, target pick, wrapper invoke, outcome classification, and handoff of findings into `pr-fix-protocol`. Triggered by `/codex-review`, `codex review`, `run codex review`, `babysit codex review`, or `codex as a PR reviewer`.

## Purpose

One Codex review pass per invocation. The skill owns sequence and skill-level classification (`down` / `clean` / `findings`). The headless wrapper is capture-only (`completed` / `codex_down` plus raw fields). Shared peers own opt-out parsing (`reviews_disabled.py` / `reviewer-gates`) and the fix sequence (`pr-fix-protocol`). Wrapper and classification contracts sit under `reference/cli-contract.md`; PR-loop wiring sits under `reference/loop-integration.md`.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Flow skeleton: opt-out → probe → target → wrapper → classify → fix handoff; refusals; sub-skills table; ground rules. |
| `reference/cli-contract.md` | CLI version/shape probe, wrapper capture contract (`completed` / `codex_down`), skill classes (`down` / `clean` / `findings`). |
| `reference/loop-integration.md` | Base-branch vs uncommitted target pick; how PR-loop orchestrators re-enter after a fix push. |
| `scripts/run_codex_review.py` | Headless capture wrapper: probes, single-target argv, JSONL capture, `completed` / `codex_down`. |
| `scripts/test_run_codex_review.py` | Behavioral tests for `run_codex_review`. |
| `scripts/codex_review_scripts_constants/run_constants.py` | Named constants for the capture wrapper. |
| `scripts/codex_review_scripts_constants/` | Named constants package for skill scripts. |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Progressive-disclosure pages for cli-contract and loop-integration. |
| `scripts/` | Capture wrapper, tests, and constants package. |

## Environment opt-out

Set `CLAUDE_REVIEWS_DISABLED=codex` to disable. Step 0 runs `reviews_disabled.py --reviewer codex` before any probe or wrapper call.
