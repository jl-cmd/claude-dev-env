---
name: reviews
description: >-
  Review a pull request or code change for code health. Use when a user asks to
  "code review", "review this PR", or "review this change".
---

# Code Review Guide

Use this guide to evaluate a pull request or code change. Apply the repository's
`AGENTS.md` and `CODE_RULES.md` as its project-specific quality rubric.

## Review Judgment

Review work supports code health. Frame each conclusion around observable
behavior, maintainability, risk, and the change's intended outcome.

- Use technical evidence and repository conventions to resolve trade-offs.
- Mark a required change when it materially affects correctness, security,
  reliability, data integrity, maintainability, or the stated behavior.
- Mark optional improvement as `Consider` or `Nit` so the author can prioritize
  the work accurately.
- Accept an evidence-backed explanation when it satisfies the applicable
  quality rubric.

## Evaluation Criteria

Evaluate the changed code and the surrounding context for:

- Design fit, interfaces, complexity, and future maintenance cost.
- Functional behavior, user impact, edge cases, concurrency, privacy,
  security, and accessibility where applicable.
- Tests that exercise the changed behavior and distinguish regressions.
- Names, comments, documentation, and style against the repository rubric and
  the applicable language guide.
- Migration, configuration, compatibility, and operational effects.

## Review Workflow

1. Read the pull request description and identify the intended outcome.
2. Inspect the changed code, relevant callers, and the surrounding design.
3. Run or assess relevant verification and identify its coverage boundaries.
4. Write each finding with the affected location, observed effect, expected
   outcome, and supporting evidence.
5. State the reviewed scope, verification performed, and any remaining
   uncertainty in the review output.

Use the [comment guide](../comments/SKILL.md#writing-useful-review-comments)
for finding wording and the [description guide](../descriptions/SKILL.md#reviewing-a-description)
for description content.

## Execution Support

Use available runners for inspection, verification, and repository navigation.
This guide supplies the judgment criteria and the corresponding guide anchors.

## Review Responsiveness

Begin a requested review at the next clean work boundary. Provide a useful
response promptly, including the completed scope and the remaining work when
context gathering continues.

Review the highest-impact design questions early. A focused response gives the
author a clear next action while the full assessment continues.

## Resolving Disagreements

Consolidate a disagreement into one thread that records the relevant context,
technical rationale, and desired decision. Reassess the finding against the
repository rubric and accept a sound alternative that meets the same outcome.

Seek a maintainer or lead decision when the discussion requires ownership or
product direction beyond the available evidence. Keep the resulting decision in
the pull request record.

## Related Guides

- Use [comments](../comments/SKILL.md#when-to-use-this-guide) to draft or answer
  review feedback.
- Use [descriptions](../descriptions/SKILL.md#when-to-use-this-guide) to prepare
  or assess pull request context.
- Use [emergencies](../emergencies/SKILL.md#emergency-classification) to classify
  an urgent production change.
- Use [small-cl](../small-cl/SKILL.md#when-to-use-this-guide) to focus or split
  a change that exceeds a clear review boundary.
