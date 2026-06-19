# .github/ISSUE_TEMPLATE

GitHub issue form templates. GitHub renders these as structured forms when a user clicks "New Issue."

## Files

| File | Template name | Purpose |
|------|--------------|---------|
| `config.yml` | — | Disables blank issues; redirects prompt-generator bugs to `jl-cmd/prompt-generator` via a contact link |
| `bug-report.yml` | Bug Report | Structured form for bugs in `claude-dev-env` or `claude-code-config` — collects description, reproduction steps, expected behavior, and environment |
| `feature-request.yml` | Feature Request | Form for new rules, agents, skills, or other improvements — collects summary, motivation, and alternatives |
| `prompt-generator-redirect.yml` | Report a prompt-generator bug (redirect) | Redirects issues about the prompt-generator skill, agent-prompt skill, or prompt-workflow hooks to `jl-cmd/prompt-generator`; requires the reporter to acknowledge the redirect before submitting |

## Conventions

- `config.yml` sets `blank_issues_enabled: false`, so GitHub shows only these templates.
- When adding a template, use the YAML form format (`body:` with `type: textarea` / `type: checkboxes`), not the older Markdown template format.
- Labels set in a template (`labels:`) are applied automatically on submission; keep them in sync with the repo's label set.
