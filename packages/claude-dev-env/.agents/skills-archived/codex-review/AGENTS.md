# codex-review

Runs OpenAI Codex as a local PR or uncommitted-diff reviewer: opt-out gate, version/shape probe, target pick, classifying review (`codex exec … review --json`), outcome classification, and handoff of findings into `pr-fix-protocol`. Triggered by `/codex-review`, `codex review`, `run codex review`, `babysit codex review`, or `codex as a PR reviewer`.

## Purpose

One Codex review pass per invocation. The skill owns sequence and skill-level classification (`down` / `clean` / `findings`). The headless wrapper is capture-only (`completed` / `codex_down` plus raw fields). Shared peers own opt-out parsing (`reviews_disabled.py` / `reviewer-gates`) and the fix sequence (`pr-fix-protocol`). Observed raw CLI surface, wrapper capture contract, probe signals, failure fixtures, auth modes, cloud runbook, and classification map live under `reference/cli-contract.md`; PR-loop wiring lives under `reference/loop-integration.md`.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Flow skeleton: opt-out → probe → target → wrapper → classify → fix handoff; refusals; sub-skills table; ground rules. |
| `reference/cli-contract.md` | Wrapper entrypoint and argv; version/shape probe; success JSONL and findings parse; failure classes tied to fixtures; auth modes; cloud runbook. |
| `reference/loop-integration.md` | Gate placement in pr-converge and autoconverge; threshold rule; opt-out token; state fields; re-entry after fixes. |
| `scripts/run_codex_review.py` | Headless capture wrapper: probes, single-target argv, JSONL capture, `completed` / `codex_down`. |
| `scripts/test_run_codex_review.py` | Behavioral tests for `run_codex_review`. |
| `scripts/codex_down_classifier.py` | Maps a Codex run's exit code and stream text to a failure detail class and the gate outcome class (`completed` / `codex_down`). |
| `scripts/parse_codex_findings.py` | Parses reviewer text into findings: fenced JSON first, then the freeform bullet shape, then a single floor finding. |
| `scripts/codex_usage_probe.py` | Weekly usage probe CLI: app-server rate-limits read, null-on-unknown JSON report. |
| `scripts/test_codex_usage_probe.py` | Unit tests for the weekly usage probe and gate helper. |
| `scripts/codex_review_scripts_constants/run_constants.py` | Named constants package for skill scripts: binary name, flags, prompt, probe pattern, timeout, exit sentinels, JSONL keys, capture outcome labels. |
| `scripts/codex_review_scripts_constants/codex_usage_probe_constants.py` | Named constants for the weekly usage probe. |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Progressive-disclosure pages for cli-contract and loop-integration. |
| `scripts/` | Capture wrapper, classifier, findings parser, weekly usage probe, tests, fixtures, and constants package. |

## Environment opt-out

Step 0 runs `reviews_disabled.py --reviewer codex` before any probe or review invoke.

| Gate exit | Meaning for this skill |
|---|---|
| 0 | Opt-out active — refuse with the opt-out line in `SKILL.md` and stop |
| 1 | Continue the flow |
| Any other | Blocker — stop; do not invent an opt-out refusal |

Set `CLAUDE_REVIEWS_DISABLED=codex` to disable. This package does not re-parse `CLAUDE_REVIEWS_DISABLED`; the shared gate owns the token parse.

## Scripts surface

`scripts/` holds the capture wrapper (`run_codex_review.py`), the down classifier (`codex_down_classifier.py`), the findings parser (`parse_codex_findings.py`), the weekly usage probe (`codex_usage_probe.py`), their tests, fixtures, and named constants. The wrapper returns capture fields only (`completed` / `codex_down`); agents map those fields to skill classes via the skill-class map and parse findings through `parse_codex_findings`. Classify only from a `codex exec … review --json` JSONL stream; do not invent a non-JSONL parse.
