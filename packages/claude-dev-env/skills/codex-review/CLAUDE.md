# codex-review

Runs OpenAI Codex as a local PR or uncommitted-diff reviewer: opt-out gate, version/shape probe, target pick, wrapper invoke, outcome classification, and handoff of findings into `pr-fix-protocol`. Triggered by `/codex-review`, `codex review`, `run codex review`, `babysit codex review`, or `codex as a PR reviewer`.

## Purpose

One Codex review pass per invocation. The skill owns sequence and classification. Shared peers own opt-out parsing (`reviews_disabled.py` / `reviewer-gates`) and the fix sequence (`pr-fix-protocol`). Wrapper and parser internals sit under `reference/cli-contract.md`; PR-loop wiring sits under `reference/loop-integration.md`.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Flow skeleton: opt-out → probe → target → wrapper → classify → fix handoff; refusals; sub-skills table; ground rules. |
| `reference/cli-contract.md` | Codex CLI surface, wrapper entrypoint I/O (`completed` / `codex_down`), and skill class mapping (`down` / `clean` / `findings`). |
| `reference/loop-integration.md` | Base-branch vs uncommitted target pick; how PR-loop orchestrators re-enter after a fix push. |
| `scripts/run_codex_review.py` | Wrapper entrypoint that invokes Codex and returns completed or codex_down plus agent_message. |
| `scripts/parse_codex_findings.py` | Parses reviewer text into structured or freeform finding records. |
| `scripts/codex_down_classifier.py` | Maps wrapper failures to the `down` class. |
| `scripts/codex_usage_probe.py` | Weekly usage probe used by the conditional Codex convergence gate. |
| `scripts/codex_review_scripts_constants/` | Named constants package for the scripts above. |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Progressive-disclosure pages for cli-contract and loop-integration. |
| `scripts/` | Wrapper, parser, classifier, usage probe, tests, fixtures, and constants package. |

## Environment opt-out

Set `CLAUDE_REVIEWS_DISABLED=codex` to disable. Step 0 runs `reviews_disabled.py --reviewer codex` before any probe or wrapper call.
