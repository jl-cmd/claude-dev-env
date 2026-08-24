---
name: emergencies
description: >-
  Classify an urgent production change and guide its focused emergency review.
  Use when a user asks about an "emergency hotfix", "production incident", or "urgent security fix".
---

# Emergency Review Guide

## Emergency Classification

Use emergency handling for a narrow change that mitigates an active, severe
consequence:

- A production failure materially affecting users or a critical service.
- An active security or legal exposure requiring prompt mitigation.
- A contractual, hardware, or market deadline where a missed delivery causes a
  severe external consequence.

Record the incident, affected system, immediate consequence, and the proposed
mitigation before assessing the change.

## Standard Priority

Use the [review guide](../reviews/SKILL.md#review-workflow) for feature
schedules, end-of-day timing, ordinary delivery targets, and build remediation.
Use a focused rollback or remediation change when it restores service safely.

## While the Incident Is Active

Keep the change as small as the mitigation permits. Evaluate whether it resolves
the incident, introduces a new immediate risk, and has sufficient validation for
the affected path.

State the incident context, verification performed, observed result, and any
remaining recovery work in the pull request. Use the [comment guide](../comments/SKILL.md#writing-useful-review-comments)
to communicate required mitigation work clearly.

## Follow-up Assessment

After service is stable, use the [review guide](../reviews/SKILL.md#evaluation-criteria)
for the broader maintainability, testing, documentation, and prevention work.
