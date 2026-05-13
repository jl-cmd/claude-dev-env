# Design rationale

## Core principle (expanded)

One audit agent (`code-quality-agent`, opus) walks all A–K categories per loop. One fix agent (`clean-coder`, opus) addresses the audit's findings.

Fresh-spawn clean-room isolation: each `Agent` call creates a new subagent with its own context window and no access to prior conversation. After the subagent writes its outcome XML and self-terminates, the lead reads the file. Results never accumulate in the lead’s context beyond the XML artifact. Verbatim Anthropic quotes and URLs: [`../sources.md`](../sources.md).

## Table of contents in `SKILL.md`

The top-of-file list exists so partial reads (for example `head -100`) still show scope. Anthropic guidance: [Structure longer reference files with table of contents](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#structure-longer-reference-files-with-table-of-contents).

## When `/bugteam` applies (narrative)

The user wants automated convergence on a clean PR without babysitting each step. Typed `/bugteam` once means full authorization for up to twenty audit cycles and the corresponding fix commits.

### Refusal reasons (detail)

- **No PR / diff:** There is nothing scoped to audit.
- **Dirty tree:** The fix subagent will commit; uncommitted local work would be mixed into automated commits.
- **Missing subagents:** Both `code-quality-agent` and `clean-coder` must exist in the environment before Step 0.

Exact refusal strings remain in `SKILL.md`.
