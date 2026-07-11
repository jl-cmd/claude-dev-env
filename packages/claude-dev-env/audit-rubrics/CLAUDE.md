# audit-rubrics

Audit rubrics for the PR-loop code-review suite. The rubrics define the 17 bug categories (A–Q), their sub-bucket decompositions, and the prompt templates agents use during an audit pass. Installed into `~/.claude/audit-rubrics/` by `bin/install.mjs`.

## Key file

| File | Purpose |
|---|---|
| `source-material-section-types.md` | Lookup table for how to chunk an artifact into sections for an audit prompt; covers code PRs, docs, SQL schemas, config files, and more |

## Subdirectories

| Entry | Description |
|---|---|
| `category_rubrics/` | One `.md` per category (A–Q): defines what the category audits, example findings, and a sub-bucket decomposition table |
| `prompts/` | One `.md` per category: the ready-to-use audit prompt template an agent inlines the artifact into |

## Categories

| ID | Name |
|---|---|
| A | API contract verification |
| B | Selector engine compatibility |
| C | Resource cleanup |
| D | Scoping and ordering |
| E | Dead code |
| F | Silent failures |
| G | Bounds and overflow |
| H | Security boundaries |
| I | Concurrency |
| J | Code-rules compliance |
| K | Codebase conflicts |
| L | Behavior equivalence |
| M | Producer-consumer cardinality |
| N | Test name / scenario verifier |
| O | Docstring vs implementation drift |
| P | Name vs behavior contract |
| Q | Cross-surface claim consistency |

## Breaking-change rule

Adding a sub-bucket to a category rubric requires updating the matching prompt template in `prompts/` in the same commit. Skills that reference category IDs (`bugteam`, `findbugs`) rely on stable sub-bucket IDs (A1, A2, … P-n).
