Plan a feature through the workflow-backed `anthropic-plan` skill.

Invoke `anthropic-plan` with the user request. The skill launches the Claude Code Workflow at:

`$HOME/.claude/skills/anthropic-plan/workflow/plan-packet.mjs`

The workflow creates a validated `docs/plans/<slug>/` packet, spawns the fresh `plan-packet-validator` agent, repairs packet findings, and stops before implementation.

Usage:

```text
/plan add user authentication
/plan refactor the payment system
```
