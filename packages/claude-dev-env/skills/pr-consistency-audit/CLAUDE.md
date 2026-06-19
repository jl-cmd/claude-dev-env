# pr-consistency-audit skill

Audits a PR for cross-file inconsistencies: wrong argument names, missing required args, references to files or scripts that do not exist, stale feature remnants, docstring-vs-code mismatches, placeholder text, cross-file contradictions, parameter naming convention violations, and cross-platform bugs.

**Trigger:** "audit this PR", "find inconsistencies", "cross-reference docs against scripts", "check for stale references", "PR consistency audit".

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Full process: build manifest, find canonical sources, run 10 detection rules, produce summary |
| `reference/detection-rules.md` | All 10 detection rules with procedures |
| `reference/illustrations.md` | Concrete examples of findings with why-they-matter explanations |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Detection rules and worked illustrations |

## Process overview

1. **Build manifest** — read every changed file; track argparse args, MCP tool calls, shell commands, file path references, named constants, and docstring claims. Write to a temp JSON file.
2. **Find canonical sources** — note which files define the ground truth for each concept (schemas, payloads, config files, `.py` sources).
3. **Run all 10 detection rules** — write each finding at once to a temp CSV with `file_path | line_number | rule_id | severity | what_is_wrong | what_it_should_be | evidence_path | evidence_detail`.
4. **Produce summary** — print totals by rule and severity; list top findings; cite the CSV and manifest paths.

## Severity

| Severity | Meaning |
|---|---|
| P0 | Runtime failure — the command or tool call will error |
| P1 | Confusing or wrong — will mislead but not crash |
| P2 | Cleanup — stale references, docs out of sync |
