# skills-archived

Versioned archive of retired Claude Code skills. These trees stay in the repository for reference and history but are not shipped to users.

## Layout

Each subdirectory is one retired skill with its historical `SKILL.md`, reference docs, scripts, and tests. Live runtime helpers for convergence and Codex review live under `packages/claude-dev-env/_shared/pr-loop/scripts/` — not in these trees.

## Installer behavior

`bin/install.mjs` copies skills only from `.agents/skills/`. This directory is outside that path and outside the `.claude/skills` lookup pointer, so archived skills never install to `~/.agents/skills/`.

`bin/ever-shipped-skills.mjs` still lists retired skill names so a full install prunes stale copies from prior releases.

## Archived skills

| Skill | Role |
|---|---|
| `anthropic-plan` | Source-grounded plan packet workflow |
| `auditing-claude-config` | Claude Code startup instruction audit |
| `beat-sheet` | Single-line beat formatting |
| `bugteam` | Open PR audit-fix loop |
| `closeout` | Session obstacle harvest to GitHub issues |
| `codex-review` | Local Codex PR reviewer (runtime scripts in `_shared`) |
| `comments` | PR review comment guide |
| `condensing-instructions` | Instruction slimming for Claude 5 |
| `copilot-finding-triage` | Copilot gate finding tiering |
| `copilot-review` | Copilot reviewer babysitter |
| `descriptions` | PR description guide |
| `emergencies` | Emergency change guide |
| `grokify` | Grok Build handoff prompt |
| `plan-to-pr` | Plan packet to PR workflow |
| `pr-converge` | Paced PR convergence loop (runtime scripts in `_shared`) |
| `pr-fix-protocol` | Reviewer finding fix protocol |
| `pr-loop-cloud-transport` | Cloud session gh-to-MCP transport |
| `pr-loop-lifecycle` | PR-loop open and close |
| `recall` | Obsidian vault recall |
| `release-notes-html` | Session release-notes HTML page |
| `remember` | Obsidian vault remember |
| `reviewer-gates` | External reviewer availability gates |
| `reviews` | Code review guide |
| `show` | Inline visual explanations |
| `split-pr` | PR split analyzer |

Prompt-generator dependency skills (`agent-prompt`, `pmin`, `pmax`, `pmid`, `prompt-generator`) shipped via the `@jl-cmd/prompt-generator` npm package and never had source trees in this repository.
