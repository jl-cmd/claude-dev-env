---
name: pr-refinement
description: Coordinate shared-extraction and capability-naming audits, then update an existing pull request or publish a required focused GitHub pull-request stack. Use when a user asks to turn a PR architecture audit into extracted shared code and small pull requests.
---

# PR Refinement

Turn audit findings into a focused existing pull-request update or a required dependency-ordered GitHub pull-request stack.

## Peer skills

1. Run `pr-shared-extraction-audit` for reusable-code placement, canonical shared homes, and extraction findings.
2. Run `pr-name-by-capability-audit` for module, symbol, path, branch, and pull-request naming findings.
3. Use `pr-small-cl` to divide approved fixes into coherent, independently reviewable pull requests.

The peer skills own their audit rules and finding priorities.

## Workflow

1. Run both audits in parallel against the same pull request. Keep their findings, locations, priorities, destinations, API directions, and naming directions.
2. Build one change map. Group findings by shared capability and dependency.
3. Use `pr-small-cl` to choose the delivery shape. Update the existing pull request when it remains one coherent, reviewable outcome.
4. Create a replacement pull-request stack when the focused-change review identifies independent increments. Give each pull request one coherent outcome, related tests, a clear verification boundary, and a capability-oriented branch and title. Close the original pull request as superseded and link the replacement stack.
5. Implement the existing pull request or the replacement stack in dependency order. Earlier pull requests create stable shared foundations. Later pull requests migrate consumers and remove replaced code.
6. Run scoped production-path tests for each pull request. Record commands and results.
7. Commit and push each branch. Update the existing pull request, or open draft replacement pull requests in stack order and set every child pull request base to its parent.
8. Include scope, verification, risks, and stack dependencies in every pull-request body.

## Completion

Deliver a focused, tested, pushed existing pull request, or a replacement stack with explicit parent-child links. Keep merge authority with the user.
