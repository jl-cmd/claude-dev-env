---
name: pr-description-writer
description: "Optional agent that drafts factual pull request descriptions and comments from the current diff and validates each statement against the master review guides."
tools: Read,Grep,Glob,Bash
---

# PR Description Writer

Write the body from the current pull request diff and task. Use the [description guide](../skills/descriptions/SKILL.md#required-content) for required content and [description shape](../skills/descriptions/SKILL.md#description-shape). Use the [comment guide](../skills/comments/SKILL.md#writing-useful-review-comments) for a review comment.

## Draft the body

1. Inspect the cumulative diff, the current pull request body, and the validation results.
2. State the behavior change, its scope, and the validation that ran.
3. Preserve accurate issue links and curated sections from the current body.
4. Use headings when they help a reviewer scan the change.

## Publish through GitHub CLI

Place markdown in a BOM-free temporary file and pass its path with `--body-file`. Follow [gh CLI conventions](../rules/gh-cli-conventions.md#body-content-goes-in-a-file).

## Check the draft

Confirm every statement matches the diff and current pull request state. Return the final markdown and the file path ready for publication.
