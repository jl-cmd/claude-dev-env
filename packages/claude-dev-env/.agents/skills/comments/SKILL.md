---
name: comments
description: >-
  Draft, refine, or respond to pull-request review comments. Use when a user
  asks to "write a review comment", "address review feedback", or "reply to a reviewer".
---

# Review Comment Guide

## When to Use This Guide

Use this guide to draft a finding, refine its tone, reply to reviewer feedback,
or resolve a comment thread. Use the [review guide](../reviews/SKILL.md#review-judgment)
to decide whether a concern merits a finding.

## Writing Useful Review Comments

Each comment names the affected behavior, the observed concern, the relevant
evidence, and the expected outcome. Give the author enough context to choose an
effective fix.

- Use `Required` for a change that materially affects the review judgment.
- Use `Consider`, `Nit`, or `FYI` for improvement, polish, and context.
- Explain the technical rationale when the connection from evidence to outcome
  needs context.
- Recognize strong decisions and completed fixes with the same specificity.

## Respectful and Actionable Feedback

Treat every contributor as capable and acting in good faith. Keep feedback
about the code, its behavior, and its effect on users or maintainers.

- Consolidate a disagreement into one focused exchange with the relevant
  context and reasoning.
- Use proportionate language that directs attention to the required change.
- Respect repository tooling and established formatting conventions.
- Close a thread when its outcome satisfies the applicable review judgment.

## Responding to Feedback

Start with the substance of the feedback. Clarify the code, its tests, or its
documentation when that gives future readers the needed context.

Ask for clarification when the requested outcome remains unclear. Reply with
the trade-off, evidence, and proposed resolution when an alternative approach
better serves the stated goal.

## Resolving Pushback

Reassess a disputed finding against the repository rubric and the change's
evidence. Keep advocating for a material improvement when the rationale remains
sound, and accept an evidence-backed alternative that meets the same quality
goal.

Escalate to a maintainer or lead when product direction or code ownership is
needed. Record the resulting decision in the pull request thread.

## Related Guides

- Use [reviews](../reviews/SKILL.md#review-workflow) for substantive code
  assessment.
- Use [small-cl](../small-cl/SKILL.md#responding-to-review) for author-side
  review responses and focused follow-up work.
- Use [emergencies](../emergencies/SKILL.md#while-the-incident-is-active) for
  urgent production-change communication.
