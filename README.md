# claude-code-config

Consistent development standards for Claude Code across every repo. Install once, get TDD enforcement, code quality hooks, specialized agents, and battle-tested rules everywhere.

## Quick Start

### Prerequisites

- **Node.js 18+** (includes `npx`)
- **Python 3.8+** (for hook scripts)
- **Claude Code CLI** installed and working

### Install

```bash
npx claude-dev-env
```

That's it. The installer will:

1. Detect your Python 3 command (`python3`, `python`, or `py -3`)
2. Copy 14 rules, 5 docs, 35 agents, 11 commands, and 19 skills to `~/.claude/`
3. Copy hook scripts to `~/.claude/hooks/`
4. Merge hook groups into `~/.claude/settings.json` (preserves your existing hooks)
5. Write a manifest to `~/.claude/.claude-dev-env-manifest.json` for clean uninstall

### Selective Install

Only want specific tools? Use the `--only` flag with one or more groups:

```bash
npx claude-dev-env --only prompts           # prompt-generator, agent-prompt + workflow hooks
npx claude-dev-env --only journal           # dream, session-log, session-tidy
npx claude-dev-env --only research          # deep-research, research-mode
npx claude-dev-env --only core             # dev standards, hooks, agents, commands
npx claude-dev-env --only prompts,research  # combine groups
```

| Group | What's included |
|-------|----------------|
| `core` | Rules, docs, commands, agents, all hooks |
| `prompts` | prompt-generator, agent-prompt, prompt-workflow hooks and rules |
| `journal` | dream, session-log, session-tidy |
| `research` | deep-research, research-mode |

### Verify

Start a new Claude Code session. You should see hook activity on your first prompt (code-rules-reminder, hook-structure-context). Run any slash command like `/commit` or `/readability-review` to confirm commands loaded.

### Update

Run the same command again. It overwrites existing files and updates hook entries in place:

```bash
npx claude-dev-env
```

### Uninstall

Removes only the files this package installed (tracked via manifest) and cleans hook entries from `settings.json`:

```bash
npx claude-dev-env --uninstall
```

## What This Solves

Without shared config, every repo needs its own `.claude/rules/`, `.claude/hooks/`, `.claude/agents/`, etc. That means:

- Duplicated config across 5+ repos
- Drift when you update standards in one place but forget others
- New repos start with zero guardrails

This package centralizes all general-purpose Claude Code config. Project-specific rules still live in each repo's `.claude/` directory and merge with these.

## What's Included

### Rules (14)

Behavioral rules loaded into every session. These shape how Claude approaches work before any code is written.

| Rule | What it does |
|------|-------------|
| `tdd` | Red-green-refactor is non-negotiable |
| `code-standards` | References CODE_RULES.md for all code generation |
| `conservative-action` | Research first, act only when explicitly asked |
| `right-sized-engineering` | Simple > clever, functions > classes, concrete > abstract |
| `explore-thoroughly` | Read before proposing, map patterns before committing |
| `research-mode` | Anti-hallucination: cite sources, say "I don't know", use direct quotes |
| `parallel-tools` | Independent tool calls run simultaneously |
| `agent-spawn-protocol` | Context sufficiency check before delegating to agents |
| `git-workflow` | Draft PRs, one commit per review stage, stacked PR patterns |
| `code-reviews` | Systematic PR review response protocol |
| `testing` | Complete mocks, reference TEST_QUALITY.md |
| `context7` | Fetch current docs via Context7 MCP instead of relying on training data |
| `cleanup-temp-files` | Remove scratch files after tasks complete |
| `prompt-workflow-context-controls` | Context footprint controls for prompt refinement workflows |

### Docs (5)

Reference documents that rules and agents point to for detailed standards.

| Document | Coverage |
|----------|----------|
| `CODE_RULES.md` | Hook-enforced rules, naming conventions, config patterns, type hints, readability rubric |
| `TEST_QUALITY.md` | Test writing standards, mock completeness, assertion patterns |
| `REACT_PATTERNS.md` | Component architecture, hooks, state management conventions |
| `DJANGO_PATTERNS.md` | Model patterns, view architecture, ORM best practices |
| `PR_DESCRIPTION_GUIDE.md` | PR description structure and file-grouped format |

### Agents (35)

Specialized agent prompts for common development tasks. Claude Code automatically discovers these and makes them available for delegation.

**Code Quality:** clean-coder, code-quality-agent, code-standards-agent, readability-review-agent, refactoring-specialist, right-sized-engineer

**Testing:** tdd-test-writer, test-data-builder, validation-expert

**Planning:** plan-executor, parallel-workflow-coordinator, mandatory-agent-workflow-agent, stub-detector-agent

**Documentation:** docs-agent, doc-orchestrator, user-docs-writer, project-docs-analyzer

**Configuration:** config-extraction-agent, config-centralizer, magic-value-eliminator-agent, project-structure-organizer-agent

**Tooling:** agent-writer, skill-writer-agent, skill-to-agent-converter, tooling-builder

**Git:** git-commit-crafter, pr-description-writer, session-continuity-manager

**File Formats:** docx-agent, pdf-agent, xlsx-agent

**Research:** deep-research

**Other:** clasp-deployment-orchestrator, workflow-visual-documenter, project-context-loader

### Commands (11)

Slash commands for common workflows.

| Command | Purpose |
|---------|---------|
| `/commit` | Structured git commit with conventional format |
| `/plan` | Create implementation plans with config search |
| `/implement` | Execute plans with TDD workflow |
| `/review-plan` | Review and critique implementation plans |
| `/readability-review` | 8-dimension readability scoring |
| `/right-size` | Check for over/under-engineering |
| `/stubcheck` | Find stubs, TODOs, and NotImplementedError |
| `/pr-comments` | Process PR review comments systematically |
| `/docupdate` | Update documentation after changes |
| `/initialize` | Session initialization with protocol review |
| `/sum` | Summarize current work context |

### Skills (19)

**Prompt Engineering (`--only prompts`):**

| Skill | Purpose |
|-------|---------|
| `prompt-generator` | Write, refine, and structure prompts for Claude with emotion-informed framing |
| `agent-prompt` | Craft structured agent prompts and spawn background agents after approval |

**Session & Memory (`--only journal`):**

| Skill | Purpose |
|-------|---------|
| `dream` | Guided reflection and brainstorming sessions |
| `session-log` | Log session reports to Obsidian vault with decisions and outcomes |
| `session-tidy` | Clean up and organize session folder structure |

**Research (`--only research`):**

| Skill | Purpose |
|-------|---------|
| `deep-research` | Iterative multi-source research with citations and Obsidian reports |
| `research-mode` | Anti-hallucination constraints with citation requirements |

**Core (`--only core`):**

| Skill | Purpose |
|-------|---------|
| `tdd-team` | Orchestrate a 4-agent TDD team (planner, tester, implementer, validator) |
| `pr-review-responder` | Systematic PR review response: fetch comments, checklist, fix, reply, commit |
| `anthropic-plan` | Readonly codebase exploration before code changes, produces a plan file |
| `readability-review` | 8-dimension readability scoring (160 pts) with automatic fixes |
| `ingest` | Digest codebase into LLM-friendly text files via gitingest |
| `npm-creator` | Scaffold npm installer packages for Claude Code plugin repos |
| `rule-audit` | Full enforcement audit of rules, hooks, and docs across user and project layers |
| `rule-creator` | Create and harden Claude Code rules with positive framing and rationale |
| `skill-writer` | Write Claude Code skills with prompt-engineering principles and progressive disclosure |
| `everything-search` | Fast Windows file search via Everything (voidtools) es.exe |
| `recall` | Retrieve prior session context and decisions from Obsidian vault |
| `remember` | Save decisions, gotchas, and architectural choices to Obsidian vault |

### Hooks

Automated enforcement that runs on Claude Code events. The installer detects your Python 3 command and rewrites hook paths to absolute `~/.claude/hooks/` paths in `settings.json`.

#### PreToolUse (before tool execution)

| Matcher | Hook | What it does |
|---------|------|-------------|
| Write\|Edit | `write-existing-file-blocker` | Warns before overwriting files that should be edited |
| Write\|Edit | `sensitive-file-protector` | Blocks writes to .env, credentials, and sensitive files |
| Write\|Edit | `hook-format-validator` | Validates hook file format on write |
| Write\|Edit | `run_all_validators` | Runs the full validation suite (30+ checks) |
| Write\|Edit | `code-rules-enforcer` | Blocks CODE_RULES.md violations (comments, magic values, imports) |
| Write\|Edit | `tdd-enforcer` | Prompts TDD confirmation when writing production code |
| Edit | `refactor-guard` | Ensures refactoring happens only after green tests |
| Edit | `migration-safety-advisor` | Warns about risky database migration patterns |
| Bash | `destructive-command-blocker` | Blocks rm -rf, git reset --hard, and other destructive commands |
| Bash | `block-main-commit` | Blocks direct commits to main/master branch |
| Bash | `pr-description-enforcer` | Enforces PR description structure and style |
| Bash | `test-preflight-check` | Validates server health and database before test runs |
| Task\|Agent | `parallel-task-blocker` | Limits concurrent Task/Agent delegations |
| AskUserQuestion | `attention-needed-notify` | Desktop notification when Claude needs your input |

#### Other Events

| Event | Hook | What it does |
|-------|------|-------------|
| SessionStart | `plugin-data-dir-cleanup` | Cleans stale plugin data on session start |
| CLI | `prompt_workflow_validate.py` | File-based validation loop for prompt-workflow draft artifacts (replaces former Stop hook) |
| Stop | `attention-needed-notify` | Desktop notification when Claude stops |
| Stop | `hedging-language-blocker` | Blocks responses with hedging language (anti-hallucination) |
| SessionEnd | `session-end-cleanup` | Cleans temporary state on session end |
| ConfigChange | `config-change-guard` | Guards against accidental settings changes |
| PostToolUse (Write\|Edit) | `mypy_validator` | Runs mypy type checking after file writes |
| PostToolUse (Write\|Edit) | `auto-formatter` | Auto-formats Python (ruff/black) and JS (prettier) on write |
| PostToolUse (Agent\|Task) | `investigation-tracker-reset` | Resets investigation tracker after delegation |
| Notification | `claude-notification-handler` | Routes Claude Code notifications to desktop |

#### Validators Module

The `hooks/validators/` directory contains 30+ individual check modules with a full test suite:

Abbreviations, code quality, comments, file structure, git conventions, magic values, mypy integration, PR references, Python antipatterns, Python style, React patterns, ruff integration, security, TODO tracking, type safety, useless test detection, and more.

## Also Available as a Plugin

If you prefer the Claude Code plugin system over npm:

```bash
claude plugin install jl-cmd/claude-code-config
```

## Recommended Companion Plugins

These plugins provide additional skills and capabilities that complement this config:

```bash
claude plugin install anthropics/claude-code-plugins        # Official: frontend-design, code-review, playwright, hookify, skill-creator, claude-md-management, serena, pyright-lsp, typescript-lsp, claude-code-setup
claude plugin install anthropics/claude-code-workflows      # Official: python-dev, ui-design, unit-testing, context-management, agent-teams, and more
claude plugin install jl-cmd/claude-workflow                # Workflow definitions with YAML schemas
```

Note: prompt-generator, journal, and deep-research skills are all included in claude-dev-env. Use `--only prompts`, `--only journal`, or `--only research` if you only want a subset.

GSD (project management) is available as an npm package:
```bash
npx get-shit-done-cc
```

## Customization

Installed rules merge with your project's `.claude/` config. To override a rule for a specific project, create a rule with the same filename in your project's `.claude/rules/` directory.

Installed hooks run alongside any hooks already in your `settings.json` or `settings.local.json`. The installer preserves existing hook entries.

## Requirements

- Node.js 18+ (for the installer)
- Python 3.8+ (for hooks)
- Claude Code CLI

## License

MIT
