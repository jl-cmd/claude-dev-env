# gotcha skill

Captures an obstacle encountered during a skill run and records it as a gotcha entry in the relevant skill file, then opens a draft PR via the `fresh-branch` skill.

**Trigger:** `/gotcha`, "add a gotcha", "document this gotcha", "record this obstacle".

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Full workflow: collect obstacle details, delegate to `bg-agent`, confirm to user |

## Workflow

1. Distill the obstacle into: which skill file was affected, what happened, what the user did to resolve it, and what to do differently next time.
2. Invoke `/bg-agent` with a self-contained prompt that instructs the agent to use `/fresh-branch` (branch name `gotcha/<short-slug>`), append to or create a `## Gotchas` section at the bottom of the skill file, commit, push, and open a draft PR.
3. Confirm to the user that the recording is running in the background.

## Gotcha entry format

Each entry is a bullet under `## Gotchas`:

```markdown
- **<title>:** <what happens>. <what to do instead>.
```

## Repo routing

| Skill location | Target repo |
|---|---|
| `packages/claude-dev-env/skills/<name>/` | `jl-cmd/claude-code-config` |
| `~/.claude/skills/<name>/` | `jl-cmd/claude-code-config` |
| Project `.claude/skills/<name>/` | That project's repo |
