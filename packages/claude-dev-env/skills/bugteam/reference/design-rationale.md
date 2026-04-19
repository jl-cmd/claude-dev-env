# Design rationale

## Core principle (expanded)

A Claude Code **agent team** runs the audit-and-fix loop until convergence. The bugfind teammate audits clean-room (own context window, no chat history); the bugfix teammate addresses each audit's findings; both spawn fresh per loop. A 10-loop hard cap prevents runaway cost. Project permissions are granted at session start and revoked at session end.

Teammate isolation versus subagents returning into the lead’s context is the clean-room property. Verbatim Anthropic quotes and URLs: [`../sources.md`](../sources.md).

## Why not parallel subagents here

Subagents return their results into the lead’s context, which accumulates across loops. Agent-team teammates are independent sessions with their own context windows and do not pollute the lead. The lead can shut down and respawn each loop so every audit starts fresh. For `/bugteam`, the independent-context property is required; parallel subagents fail the clean-room requirement. Supporting quotes: [`../sources.md`](../sources.md) (subagents vs agent teams).

## Table of contents in `SKILL.md`

The top-of-file list exists so partial reads (for example `head -100`) still show scope. Anthropic guidance: [Structure longer reference files with table of contents](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#structure-longer-reference-files-with-table-of-contents).

## When `/bugteam` applies (narrative)

The user wants automated convergence on a clean PR without babysitting each step. Typed `/bugteam` once means full authorization for up to ten audit cycles and the corresponding fix commits.

### Refusal reasons (detail)

- **Agent teams off:** Without the feature flag, the workflow cannot run.
- **No PR / diff:** There is nothing scoped to audit.
- **Dirty tree:** The fix teammate will commit; uncommitted local work would be mixed into automated commits.
- **Missing subagents:** Both `code-quality-agent` and `clean-coder` must exist in the environment before Step 0.

Exact refusal strings remain in `SKILL.md`.
