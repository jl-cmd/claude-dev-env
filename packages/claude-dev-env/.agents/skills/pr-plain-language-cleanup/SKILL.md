---
name: pr-plain-language-cleanup
disable-model-invocation: true
description: Review every line of every changed PR file and trim words, names, docs, comments, and code while keeping real behavior.
---

# PR plain-language cleanup

Review and trim this pull request:

<PR LINK>

If no link is given, find the clear PR in the current context. If none is clear, ask for one.

Read the full PR, full diff, every changed file, changed tests and docs, and all repo rules that apply.

Find the changed files. Send one capable agent to each file. If there are more files than agents, use small batches.

Each agent owns one file. Read every line. Review code, tests, names, comments, docstrings, strings, notes, Markdown, and examples.

Trim filler, repeats, vague words, needless code, needless names, dead notes, jargon, and steps that add no value. Use few words and small words.

Keep real behavior, checks, data, error detail, context, tests, and public names unless a safe full rename is clear. Do not change behavior for style. Do not shorten a name when it loses meaning.

Follow the repo rules:

- Name modules for their capability.
- Name functions for their action.
- Name variables for the value they hold.
- Name classes for what they are.
- Use capability names for shared code.
- Keep workflow words on workflow code.
- Keep comments and docs true to the code.
- Use real data and real behavior in tests.

If a change needs another file, report it to the main agent. The main agent owns cross-file changes.

After the file agents finish, apply safe edits, fix cross-file names and links, search for old names and wording, and read every changed file and the full diff again.

Run the repo's format, lint, type, and test checks. Fix failures. Check the final diff against the repo rules.

Do not invent behavior, tests, or benefits. Stop and ask only when a change could alter behavior, break a public API, or exceed the PR scope.

Commit and push the changes to the PR branch.

Return:

## What changed

Short list of the main trims.

## Files checked

Every file reviewed.

## Verification

Checks run and results.

## Remaining items

Only items that need a user choice.
