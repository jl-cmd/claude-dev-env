---
name: pr-consistency-audit
description: >-
  Audits a PR for cross-file inconsistencies. Finds wrong argument names, missing required args, references to files or scripts that do not exist, stale feature remnants, docstring-vs-implementation mismatches, placeholder text, cross-file contradictions, parameter naming convention violations, and cross-platform bugs. Use when the user says "audit this PR", "find inconsistencies", "cross-reference docs against scripts", "check for stale references", "PR consistency audit".
---

# PR Consistency Audit

Read every changed file in a pull request. Find every inconsistency across files. Leave nothing unchecked. Leave nothing assumed. Zero context needed beyond the diff.

## Gotchas

- The highest-signal rule is canonical-source cross-reference. Do it first. Do it slowly. Copilot found 20 of its 43 findings with this rule alone. Missing it means missing half the bugs.
- Parameter naming conventions are per-tool, not per-project. `issue_read` uses `issue_number` (snake_case). `add_issue_comment` uses `issueNumber` (camelCase). A doc that mixes them is wrong even if snake_case works for `issue_read`.
- When a finding appears in many files with the same wrong pattern, flag every instance individually. Do not say "this is wrong in 20 files" and move on. List every file with its line.
- Template files and obstacle files are often skipped because they feel "generated" or "low priority." They are not. Copilot found 6 issues in template files that human auditors never opened.
- A manifest written to a temp file is not optional. Hold all script signatures, all MCP tool names, all constants, and all concept names in a JSON file. Read from it during detection. Memory fails. Files do not.

## When this skill applies

Trigger when the user provides a PR diff, a list of changed files, or asks to audit cross-file consistency. The agent needs no prior knowledge of the repo, the scripts, or the project conventions.

## Process

### Step 1: Build the manifest

Read every file in the diff. Top to bottom. Build `<tmp>/audit-manifest-<timestamp>.json`. Track:

- Python scripts → argparse arguments (`add_argument("--name", ...)`), which are `required=True`
- MCP tool call patterns in docs → tool name, every parameter used, file and line
- Shell commands (`gh`, `git`, `python`, `bash`) → full command, file, line
- File paths referenced in docs → whether they resolve to real files
- Named concepts in prose → "inline_lag", "COPILOT_WAIT", "bugfind", phase names, state values. File and line each.
- Constants, thresholds, timeouts → value, concept it measures, file, line
- Functions with docstring claims → function name, claim made, file, line

### Step 2: Find canonical sources

Identify the files that define the authoritative form of each concept. Signs a file is canonical:

- Has structured schemas, payload definitions, API contracts (files like `gh-payloads.md`, `mcp_tool_signatures.json`, `constants.py`)
- Name includes "reference", "spec", "schema", "payload", "contract", "canonical"
- Other files cite it as the source of truth
- It defines the implementation that docstrings describe (the `.py` file, not the `.md` that talks about it)

For each canonical source, note what concept it is canonical for. When a rule needs to decide what is "correct," the canonical source wins.

### Step 3: Run detection rules

Read [`reference/detection-rules.md`](reference/detection-rules.md). Run all ten rules against every file. Write findings immediately to `<tmp>/inconsistency-audit-<timestamp>.csv`:

```
file_path | line_number | rule_id | severity | what_is_wrong | what_it_should_be | evidence_path | evidence_detail
```

### Step 4: Produce summary

Print to stdout:

```
====== DIFF INCONSISTENCY AUDIT ======
Files audited: <N>
Canonical sources: <list>
Total findings: <N>

By rule:
Rule 1 — canonical_source_cross_reference: X (P0: A, P1: B, P2: C)
...

By severity:
P0 (runtime failure): X
P1 (confusing or wrong): Y
P2 (cleanup): Z

Top findings:
1. file:line — [P0] — what is wrong — what it should be
2. ...

Full report: <tmp>/inconsistency-audit-<timestamp>.csv
Manifest: <tmp>/audit-manifest-<timestamp>.json
====== END AUDIT ======
```

## Constraints

- Read every file completely. No skimming.
- Write findings immediately. Do not batch in memory.
- Every finding cites file:line of problem AND file:line of evidence.
- When two files contradict, flag both. Do not guess which is correct.
- If unresolvable, mark "unresolvable — no canonical source found."
- Run every rule. The highest-signal findings come from rules you think will be empty.

## Severity

| Severity | Meaning |
|----------|---------|
| P0 | Runtime failure — the command or tool call will error |
| P1 | Confusing or wrong — will mislead but not crash |
| P2 | Cleanup — stale references, docs out of sync |

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | Hub — process, constraints, gotchas |
| `reference/detection-rules.md` | All 10 detection rules with how-to instructions |
| `reference/illustrations.md` | Concrete findings with why-they-matter explanations |
| `scripts/config/constants.py` | Severity labels, output templates, rule IDs |

## Folder map

- `SKILL.md` — hub.
- `reference/` — detection rules and illustrations.
- `scripts/` — helpers and config.
