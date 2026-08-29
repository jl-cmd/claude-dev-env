---
name: pr-plain-language-cleanup
disable-model-invocation: true
description: >-
  Trim unnecessary words and improve readability in changed PR text while
  preserving meaning and behavior. Triggers: /pr-plain-language-cleanup,
  plain-language cleanup, PR prose cleanup, trim words in a PR, reduce wordiness,
  remove filler, readability cleanup, avoid reflow churn, text-only cleanup.
---

# PR plain-language cleanup

## Principle

Make changed PR text shorter and easier to scan. Keep meaning, behavior, checks,
data, error detail, context, and public names. This is a text-only cleanup.

## Gotchas

- Compression is required. Reflow alone is not cleanup.
- Reflow is allowed only after a real trim and only when it materially improves
  scanability.
- Keep terms that carry meaning. Do not shorten a name when it loses meaning.
- Do not invent behavior, benefits, tests, or findings.
- If a material issue appears, report it and stop.

## When this applies

Use for a requested plain-language or word-count cleanup of a pull request,
branch, or stated changed-file set. If no clear target exists, ask for a PR,
branch, or file path.

Review only changed files and applicable repo rules. Refuse or redirect requests
for correctness, bug, security, performance, architecture, feature, API, data,
or test-logic work. Do not broaden the file set, commit, push, merge, or change
GitHub state.

## Process

At the start, register four session tasks through the host task tool:
before/after word count, readability/scanability, changed-line/diff-churn, and
meaning/behavior. Complete each with evidence.

1. Read the full target PR and diff, every changed file, changed tests and docs,
   and all applicable repo rules. For several files, keep review ownership
   separate when workers are available.
2. **Word count:** record the edited text's before and after word counts and the
   delta. Remove filler, repeats, and needless words. If no words can be cut,
   report clean; do not add reflow churn.
3. **Readability/scanability:** check sentence length, order, headings, jargon,
   repeated terms, and dense blocks. Edit only where the result is easier to
   read or scan.
4. **Changed lines/diff churn:** inspect the final diff and changed-line count.
   Remove whitespace-only movement and reflow-only churn. Allow reflow only
   when it materially improves scanability and follows compression.
5. **Meaning:** compare before and after. Confirm no change to behavior, APIs,
   data, test intent, conditions, warnings, error detail, context, or public
   names. Keep code logic and data out of scope.
6. Re-read every changed file and the full diff. Run only the smallest relevant
   check, such as `git diff --check`. Stop and report any material issue.

## Return

Report:

- What changed
- Files checked
- Before and after word counts, readability result, diff-churn result, and
  meaning result as separate checks
- Remaining items that need a user choice

## File index

| Path | Purpose |
|---|---|
| `SKILL.md` | Text-only PR cleanup rules, process, limits, and report shape |

## Folder map

```text
pr-plain-language-cleanup/
└── SKILL.md
```
