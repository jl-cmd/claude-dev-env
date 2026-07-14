# codex-review/reference

Reference pages for the `codex-review` skill. `SKILL.md` cites these files for CLI contract and PR-loop integration detail.

## Key files

| File | Purpose |
|---|---|
| `cli-contract.md` | Codex CLI surface, wrapper I/O (`completed` / `codex_down`), skill class mapping (`down` / `clean` / `findings`), failure classes, auth, and shape probe. |
| `loop-integration.md` | Target selection, findings handoff, re-entry after fix, and orchestrator state fields (`codex_clean_at`, `codex_down`). |

## Conventions

- Each page is the stable home for one child workstream. Cross-references from `SKILL.md` use these paths.
- Keep one level deep: `SKILL.md` links here; these pages do not nest further references.
