# prompts

XML agent prompt templates for the PR audit-fix loop.

## Key files

| File | Role |
|---|---|
| `pr-consistency-audit.xml` | Structured prompt artifact for the cross-file consistency audit agent. Defines the agent role, scope anchors, a ten-rule detection workflow, and output format. `bugteam` and `pr-converge` both inject this prompt when running the consistency audit step. |
