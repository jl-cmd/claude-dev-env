# codex-review

Runs OpenAI Codex as a local PR or uncommitted-diff reviewer: opt-out gate, version/shape probe, target pick, wrapper invoke, outcome classification, and handoff of findings into `pr-fix-protocol`. Triggered by `/codex-review`, `codex review`, `run codex review`, `babysit codex review`, or `codex as a PR reviewer`.

## Purpose

One Codex review pass per invocation. The skill owns sequence and classification. Shared peers own opt-out parsing (`reviews_disabled.py` / `reviewer-gates`) and the fix sequence (`pr-fix-protocol`). Wrapper and parser internals sit under `reference/cli-contract.md`; PR-loop wiring sits under `reference/loop-integration.md`.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Flow skeleton: opt-out → probe → target → wrapper → classify → fix handoff; refusals; sub-skills table; ground rules. |
| `reference/cli-contract.md` | CLI version/shape probe, wrapper entrypoint and I/O contract, classification classes (`down` / `clean` / `findings`). |
| `reference/loop-integration.md` | Base-branch vs uncommitted target pick; how PR-loop orchestrators re-enter after a fix push. |
| `scripts/codex_usage_probe.py` | Weekly usage probe CLI: app-server rate-limits read, null-on-unknown JSON report. |
| `scripts/test_codex_usage_probe.py` | Unit tests for the weekly usage probe and gate helper. |
| `scripts/codex_review_scripts_constants/codex_usage_probe_constants.py` | Named constants for the weekly usage probe. |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Progressive-disclosure pages for cli-contract and loop-integration. |
| `scripts/` | Skill CLIs (usage probe) and their constants package. |

## Environment opt-out

Set `CLAUDE_REVIEWS_DISABLED=codex` to disable. Step 0 runs `reviews_disabled.py --reviewer codex` before any probe or wrapper call.
