---
name: descriptions
description: >-
  Draft or revise a pull-request description. Use when a user asks for a "PR
  description", "pull request summary", or "change description".
---

# Pull Request Description Guide

## When to Use This Guide

Use this guide to prepare or revise the written context for a pull request. A
description explains the change to reviewers and future readers; it records the
intent and evidence that source code alone cannot express.

## Required Content

Start with a short, specific summary line. Follow it with the information needed
to understand the change:

- The problem, motivation, and affected users or systems.
- The implemented approach and meaningful design decisions.
- Verification performed, including test commands and observed results.
- Risks, migrations, compatibility effects, and rollback or recovery context.
- Related issues, design records, and scoped follow-up work.

Use durable prose for every essential fact when linked material has restricted
access or a limited retention period.

## Description Shape

```text
Summarize the delivered change.

Explain the problem and the approach.

Verification: <commands and results>
Risk: <migration, compatibility, or recovery context>
```

Keep tags short and use them according to the repository's established format.

## Reviewing a Description

Compare the description with the changed files and the review findings. Keep the
summary, scope, verification, and risk information aligned with the pull
request's current contents.

Use [reviews](../reviews/SKILL.md#review-workflow) for substantive code
assessment and [small-cl](../small-cl/SKILL.md#what-a-focused-pull-request-contains)
to establish a focused scope.
