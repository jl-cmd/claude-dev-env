# Tool profiles

Set `tool_profile` per worker on the batch spec. The launcher builds the argv
from it; the exact flag tokens live in
`scripts/dev_env_scripts_constants/grok_worker_constants.py`.

## Profiles

- `readonly` — the launcher passes `--disallowed-tools Write,Edit,Bash`, so the
  worker reads only. Set `is_repo_only: true` to also pass `--disable-web-search`
  for a repo-only scan. Use for investigation, file:line mapping, and plan input.
- `build` — full tool surface. Use for edits and tests inside a closed file
  allow list. This session owns git and `gh`.

## Named agent charters

When a worker's `agent_name` names a charter, the runner passes `--agent <name>`
and grok loads that charter from the user-level Claude config home
(`~/.claude/agents/`, plus the installed `skills/`, `rules/`, `hooks/`). Name a
charter to bind that agent; leave `agent_name` as `null` (or omit it) to run the
worker on the base installed config.

## Profile cheat sheet

| Work | `tool_profile` | `is_repo_only` | `agent_name` |
|---|---|---|---|
| Map call sites in-repo only | `readonly` | `true` | `null` or an audit agent |
| Research that may need the web | `readonly` | `false` | `null` |
| Closed edit + tests | `build` | ignored | often `clean-coder` |
| Audit-style read under a charter | `readonly` | as needed | `code-quality-agent` |
