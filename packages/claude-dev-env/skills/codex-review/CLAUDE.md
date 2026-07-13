# codex-review

Runs OpenAI Codex as a local PR or uncommitted-diff reviewer: opt-out gate, version/shape probe, target pick, wrapper invoke, outcome classification, and handoff of findings into `pr-fix-protocol`. Triggered by `/codex-review`, `codex review`, `run codex review`, `babysit codex review`, or `codex as a PR reviewer`.

## Purpose

One Codex review pass per invocation. The skill owns sequence and skill-level classification (`down` / `clean` / `findings`). Shared peers own opt-out parsing (`reviews_disabled.py` / `reviewer-gates`) and the fix sequence (`pr-fix-protocol`). Observed raw CLI surface and `codex_down` failure classes live under `reference/cli-contract.md`; PR-loop wiring lives under `reference/loop-integration.md`.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Flow: opt-out → probe → target → wrapper → classify → fix handoff; refusals; sub-skills table; ground rules. |
| `reference/cli-contract.md` | Observed Codex CLI review surface: command shape, success JSONL stream, finding-bullet format, `codex_down` failure classes, auth, shape probe, and the skill-class map. |
| `reference/loop-integration.md` | Base-branch vs uncommitted target pick; re-entry after a fix push; skill-class vocabulary for orchestrators. |
| `scripts/codex_review_scripts_constants/` | Named constants package for skill scripts. |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Progressive-disclosure pages for cli-contract and loop-integration. |
| `scripts/` | Constants package for skill scripts. |

## Environment opt-out

Step 0 runs `reviews_disabled.py --reviewer codex` before any probe or wrapper call.

| Gate exit | Meaning for this skill |
|---|---|
| 0 | Opt-out active — refuse with the opt-out line in `SKILL.md` and stop |
| 1 | Continue the flow |
| Any other | Shared gate rejects the `--reviewer` argument (known tokens are `bugbot`, `bugteam`, `copilot`) — treat as a blocker and stop |

The shared gate does not accept `codex` as a `--reviewer` value, so Step 0 exits with a parse failure rather than the opt-out or continue path. Sister work owns token registration; this package does not re-parse `CLAUDE_REVIEWS_DISABLED`.
