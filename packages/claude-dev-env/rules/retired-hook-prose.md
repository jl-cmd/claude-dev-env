---
paths:
  - "**/rules/*.md"
---

# Rules Prose Names Only Hooks That Run

A hook module runs when `hooks/hooks.json` registers it or a dispatcher roster hosts it. A module can survive on disk while appearing in neither place, and it then reaches no tool call. Presence on disk settles nothing in either direction. The installer writes an inert stand-in at a retired hook path when a host's stale `settings.json` still names it, because a registered path that resolves to nothing makes the interpreter exit 2 and the harness reads a PreToolUse exit 2 as a block. A retired hook can also keep working through a different door: its logic moves into a `*_parts/` package that a live module imports, so the hook name is dead while the check it carried still fires. Prose that gives such a module a present-tense action describes a gate the reader never faces, and a reader who trusts it skips the check they were meant to run by hand.

The staged policy lint carries this check as its `retired-hook-prose` rule. It reads each Markdown file under a `rules/` directory, takes every backticked hook module name, and reports the ones that are registered nowhere and that carry a present-tense action verb in the rest of the sentence. CI runs that lint against the merge base. Its reach stops at that directory. Skill manifests, agent definitions, commands, `docs/` and `_shared/` all carry prose about hooks and none of it is read, so a stale claim there passes CI and reaches every reader. Sweep those trees by hand against the retired roster whenever you retire a hook.

A module name counts as a hook when it ends in one of the hook families, such as `_blocker`, `_enforcer`, `_gate`, `_tracker`, or `_dispatcher`, and when it either sits under `hooks/` or appears in `RETIRED_HOOK_REGISTRATION_RELATIVE_PATHS` in `bin/install.mjs`. A support module inside the hooks tree carries no such family suffix, so it stays out of the check. A hook deleted from disk without an entry in that roster resolves nowhere, so add the roster entry when you retire a hook.

Two shapes pass. A past-tense sentence that records what a hook once did makes no live claim. A sentence that names the staged policy lint, `cde_lint`, or a repository check tells the reader where the work runs now, so the module name reads as a pointer to code.

## Retiring a gate drops the detours it required

A gate and the standing orders written to satisfy it are one unit. An order that says to spawn a named agent first, to carry a magic token into a spawn, or to route through an extra step exists because some check demanded it. When the check goes, that order is a toll every later session pays for nothing, and it costs more than a stale sentence does, because a reader obeys it.

So retiring a hook is finished only when the detours it required are gone in the same change. Search for the order, not for the module: the module name is what the lint looks for, and a detour usually names the agent, the step, or the token instead, which is how these survive a lint that reads the same file. Drop the requirement and keep the agent, the skill, or the command itself; a capability nobody is forced to call costs nothing, while a forced call costs every run.

The same duty covers every lane a withdrawn standard rode on. A threshold enforced by a hook is often also stated in an audit rubric, an agent's instruction table, or a review prompt. Withdraw all of them together, and name the lanes in the archive entry. Removing the fast mechanical lane and leaving the slow judgment lane keeps the standard in force while deleting the text that a reader could argue with.

When the rule reports a line, say what the reader faces now. Name the harness permission prompt, the staged policy lint, or the repository check that carries the work, or drop the claim.
