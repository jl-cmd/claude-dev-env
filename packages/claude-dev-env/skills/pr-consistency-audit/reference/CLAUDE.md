# pr-consistency-audit/reference

Reference material for the `pr-consistency-audit` skill. These files define the detection rules the skill runs and show worked examples of findings.

## Key files

| File | Purpose |
|---|---|
| `detection-rules.md` | All 10 detection rules, each with a procedure for how to run it |
| `illustrations.md` | Concrete examples of findings with explanations of why each matters |

## Conventions

- The skill reads `detection-rules.md` during Step 3 (run detection rules). Every rule must run against every file; none are skippable.
- Rule 1 (canonical-source cross-reference) is the highest-signal rule. The skill runs it first.
- `illustrations.md` is for reviewers and skill authors, not for the skill's runtime process.
