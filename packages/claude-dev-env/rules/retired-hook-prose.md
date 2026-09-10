---
paths:
  - "**/rules/*.md"
---

# Rules Prose Names Only Hooks That Run

A hook module runs when `hooks/hooks.json` registers it or a dispatcher roster hosts it. A module can survive on disk while appearing in neither place, and it then reaches no tool call. Prose that gives such a module a present-tense action describes a gate the reader never faces, and a reader who trusts it skips the check they were meant to run by hand.

The staged policy lint carries this check as its `retired-hook-prose` rule. It reads each Markdown file under a `rules/` directory, takes every backticked hook module name, and reports the ones that are registered nowhere and that carry a present-tense action verb in the rest of the sentence. Run `python packages/claude-dev-env/scripts/cde_lint.py --staged` before you commit. CI runs the same lint against the merge base.

A module name counts as a hook when it ends in one of the hook families, such as `_blocker`, `_enforcer`, `_gate`, `_tracker`, or `_dispatcher`, and when it either sits under `hooks/` or appears in `RETIRED_HOOK_REGISTRATION_RELATIVE_PATHS` in `bin/install.mjs`. A support module inside the hooks tree carries no such family suffix, so it stays out of the check. A hook deleted from disk without an entry in that roster resolves nowhere, so add the roster entry when you retire a hook.

Two shapes pass. A past-tense sentence that records what a hook once did makes no live claim. A sentence that names the staged policy lint, `cde_lint`, or a repository check tells the reader where the work runs now, so the module name reads as a pointer to code.

When the rule reports a line, say what the reader faces now. Name the harness permission prompt, the staged policy lint, or the repository check that carries the work, or drop the claim.
