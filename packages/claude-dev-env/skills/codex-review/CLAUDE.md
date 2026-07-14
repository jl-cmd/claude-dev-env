# codex-review

Runs OpenAI Codex as a local PR or uncommitted-diff reviewer: opt-out gate, version/shape probe, target pick, classifying review (`codex exec … review --json`), outcome classification, and handoff of findings into `pr-fix-protocol`. Triggered by `/codex-review`, `codex review`, `run codex review`, `babysit codex review`, or `codex as a PR reviewer`.

## Purpose

One Codex review pass per invocation. The skill owns sequence and skill-level classification (`down` / `clean` / `findings`) from the exec+JSONL stream. Shared peers own opt-out parsing (`reviews_disabled.py` / `reviewer-gates`) and the fix sequence (`pr-fix-protocol`). Observed raw CLI surface, probe signals, and `codex_down` failure classes live under `reference/cli-contract.md`; PR-loop wiring lives under `reference/loop-integration.md`.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Flow: opt-out → probe → target → classifying review → classify → fix handoff; refusals; sub-skills table; ground rules. |
| `reference/cli-contract.md` | Observed Codex CLI review surface: classifying `codex exec … review --json` path, non-classifying plain `codex review`, success JSONL stream, finding-bullet format, `codex_down` failure classes, auth, minimum probe signals, and the skill-class map. |
| `reference/loop-integration.md` | Base-branch vs `--uncommitted` (staged + unstaged + untracked) target pick; re-entry after a fix push; skill-class vocabulary for orchestrators. |
| `scripts/codex_review_scripts_constants/` | Named constants only. The headless wrapper entrypoint is sister work. |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Progressive-disclosure pages for cli-contract and loop-integration. |
| `scripts/` | Constants package only; no wrapper entrypoint in this package. |

## Environment opt-out

Step 0 runs `reviews_disabled.py --reviewer codex` before any probe or review invoke.

| Gate exit | Meaning for this skill |
|---|---|
| 0 | Opt-out active — refuse with the opt-out line in `SKILL.md` and stop |
| 1 | Continue the flow |
| Any other | Blocker — stop; do not invent an opt-out refusal |

Set `CLAUDE_REVIEWS_DISABLED=codex` to disable. This package does not re-parse `CLAUDE_REVIEWS_DISABLED`; the shared gate owns the token parse.

## Scripts surface

`scripts/` holds named constants only. The headless wrapper entrypoint is sister work. Agents classify only from a `codex exec … review --json` JSONL stream via the skill-class map; do not invent a non-JSONL parse.
