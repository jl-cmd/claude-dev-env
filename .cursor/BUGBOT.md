# Code rules for Claude, Cursor BugBot, Copilot, and other agents

The canonical review-criteria instruction set for every AI agent that audits pull requests in this repository lives in [`packages/claude-dev-env/docs/CODE_RULES.md`](../packages/claude-dev-env/docs/CODE_RULES.md):

- **Claude** (PR review)
- **Cursor BugBot** (PR review)
- **GitHub Copilot** (PR review)
- Any other agent that reviews pull requests in this repository

Load `CODE_RULES.md` for the full rule set: comments, naming, magic values and configuration, types, structure, design, tests, platform and tooling, repo hygiene, scope of review, and hook enforcement. Agents apply those rules to the **lines a PR adds or modifies**, surface deviations as findings, and recommend corrections.

`packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py` is the hand-maintained production enforcement for the mechanical rules. Session policies (question routing, task tracking) live under `packages/claude-dev-env/rules/` — see `rules/code-standards.md`. Apply [`packages/claude-dev-env/rules/asd-ste100-language.md`](../packages/claude-dev-env/rules/asd-ste100-language.md) for user-facing wording.

This file stays at this path because Cursor BugBot reads it from here.
