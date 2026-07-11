# Confirm Implementation Forks

At a material fork — two or more viable paths that change the deliverable's scope, completeness, deferred work, dependencies, or a hard-to-reverse contract — stop and ask which path via `AskUserQuestion` before implementing. A path that defers work or leaves a placeholder is itself a fork to surface, never a silent default.

How to ask: plain language, one option per path with its tradeoff in the description, recommended path listed first and flagged "(Recommended)", hold edits to the forked area until the answer arrives.

Not a fork (just proceed): trivially reversible internal-only choices, anything the codebase / stated goal / an existing rule already determines (see `verify-before-asking`), or a single viable path.
