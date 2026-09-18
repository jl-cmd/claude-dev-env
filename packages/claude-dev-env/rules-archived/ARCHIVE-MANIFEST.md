# Archived rules

A rule lands here when it states a house preference rather than a practice an
outside authority backs, and nothing in the package points at it. Nothing is
deleted: each file keeps its history, and a restore is one `git mv` back.

| File | Why it moved | Restore |
|---|---|---|
| `claims-as-quotes.md` | Prescribes a three-piece citation shape on top of `research-mode.md`, which already requires a source. No outside authority prescribes the shape. The file declares "No hook backs it." No module, lint rule, skill, or test referenced it. | `git mv packages/claude-dev-env/rules-archived/claims-as-quotes.md packages/claude-dev-env/rules/` |
| `measurement-denominators.md` | One paragraph asking a count to name its denominator, already covered by `research-mode.md` and `hedging-claims.md`. The file declares "No hook." No module, lint rule, skill, or test referenced it. | `git mv packages/claude-dev-env/rules-archived/measurement-denominators.md packages/claude-dev-env/rules/` |
