# codex-review/reference

Reference pages for the `codex-review` skill. `SKILL.md` cites these files for CLI contract and PR-loop integration detail.

## Key files

| File | Purpose |
|---|---|
| `cli-contract.md` | Observed Codex CLI review surface: classifying `codex exec … review --json` path, non-classifying plain `codex review`, option ordering, success JSONL stream and finding-bullet format, `codex_down` failure classes, skill-class map (`down` / `clean` / `findings`), auth surface, and the `codex exec review --help` probe with minimum shape signals. |
| `loop-integration.md` | Target selection for PR loops vs standalone `--uncommitted` (staged + unstaged + untracked), skill-class vocabulary for re-entry, and findings handoff into `pr-fix-protocol`. |

## Conventions

- Each page is the stable home for one child workstream. Cross-references from `SKILL.md` use these paths.
- Keep one level deep: `SKILL.md` links here; these pages do not nest further references.
