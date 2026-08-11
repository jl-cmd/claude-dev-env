# codex-review/reference

Reference pages for the `codex-review` skill. `SKILL.md` cites these files for CLI contract and PR-loop integration detail.

## Key files

| File | Purpose |
|---|---|
| `cli-contract.md` | Observed Codex CLI review surface: classifying `codex exec … review --json` path, wrapper capture (`completed` / `codex_down`), probe signals, success JSONL and findings parse, fixture-backed failure classes, skill-class map (`down` / `clean` / `findings`), auth modes, and cloud runbook. |
| `loop-integration.md` | Gate placement in pr-converge and autoconverge; threshold rule; opt-out token; state fields; target selection; skill-class vocabulary; findings handoff; re-entry after a fix push. |

## Conventions

- Each page is the stable home for one child workstream. Cross-references from `SKILL.md` use these paths.
- Keep one level deep: `SKILL.md` links here; orchestrator-owned detail links out to pr-converge / autoconverge pages rather than restating them.
