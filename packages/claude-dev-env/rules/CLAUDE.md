# rules

Rule files installed into `~/.claude/rules/` by `bin/install.mjs`. Claude Code loads these as always-on behavioral constraints for every session. Each `.md` file covers one named rule; hook-enforced rules are also backed by a Python hook in `hooks/`.

## Files

| File | Rule |
|---|---|
| `agent-spawn-protocol.md` | Protocol for spawning subagents: context sufficiency check, prompt generation via `/prompt-generator`, then spawn |
| `ask-user-question-required.md` | Every user-directed question goes through the `AskUserQuestion` tool — no plain-text questions |
| `bdd.md` | BDD discovery-driven development workflow and Example Mapping reference |
| `claude-md-orphan-file.md` | Every backticked bare filename in a per-directory `CLAUDE.md` table's first column names a file in that directory's subtree |
| `cleanup-temp-files.md` | Remove temporary files created during a task when the task is complete |
| `code-reviews.md` | Mandatory protocol for responding to GitHub PR review feedback |
| `code-standards.md` | Pointer to `CODE_RULES.md` as the single source of truth |
| `confirm-implementation-forks.md` | Stop and ask when two or more workable implementation paths change the deliverable |
| `conservative-action.md` | Research and recommend when intent is ambiguous; act only on explicit request |
| `context7.md` | Use Context7 MCP to fetch current library docs; always prefer live docs over built-in knowledge |
| `docstring-prose-matches-implementation.md` | Prose enumerations in docstrings cover every behavior the body applies |
| `explore-thoroughly.md` | Read relevant files and map existing patterns before proposing a change |
| `file-global-constants.md` | File-global constants need at least two same-file references; otherwise move value to `config/` |
| `gh-body-file.md` | Use `--body-file` with a temp file for all `gh` commands carrying markdown body content |
| `gh-paginate.md` | Use `--paginate --slurp` piped to external `jq` for paginated GitHub API list endpoints |
| `git-workflow.md` | PR workflow: always create as draft, one commit per review stage, never commit working docs or images |
| `hook-prose-matches-detector.md` | Hook prose descriptions match what the hook actually detects |
| `long-horizon-autonomy.md` | Autonomous-run behaviors: act on what you have, do not end on a promise, delegate and keep working |
| `no-cross-skill-duplicate-helpers.md` | No duplicating shared helpers across skills; use `_shared/` |
| `no-historical-clutter.md` | Documentation describes current state only; no historical or transitional language |
| `no-inline-destructive-literals.md` | No destructive-command literals in Bash tool command strings, even as data |
| `orphan-css-class.md` | Every `class="..."` attribute in Python-generated markup has a matching selector in the `<style>` block |
| `package-inventory-stale-entry.md` | A new production code file added to a directory carries an entry in that directory's `README.md`/`CLAUDE.md` file inventory |
| `parallel-tools.md` | Make all independent tool calls in a single response |
| `plain-language.md` | Everyday words, short active sentences, lead with the answer |
| `prompt-workflow-context-controls.md` | Keep prompt-workflow instruction layers small and stable; load heavy skills on demand |
| `research-mode.md` | Three anti-hallucination constraints: say "I don't know", verify with citations, quote for factual grounding |
| `right-sized-engineering.md` | Simple over clever; functions over classes; concrete over abstract |
| `self-contained-docs.md` | Every document is fully self-contained; no references to the conversation that produced it |
| `shell-invocation-policy.md` | All Windows shell commands use `pwsh`; `powershell.exe`, `cmd /c`, and `bash -c` are blocked |
| `tdd.md` | Test-driven development: red → green → refactor, no production code before a failing test |
| `testing.md` | Test quality and infrastructure standards |
| `vault-context.md` | Search Obsidian vault for prior sessions and decisions before substantive project work |
| `verify-before-asking.md` | Answer questions by inspecting files or running tools before asking the user |
| `windows-filesystem-safe.md` | Use safe `rmtree` patterns on Windows; `mkdirSync` with `recursive: true` on possibly-existing paths |
| `workflow-substitution-slots.md` | Per-iteration values in `.workflow.js` templates use angle-bracket slots |

## Hook enforcement

Rules marked with ⚡ in `packages/claude-dev-env/docs/CODE_RULES.md` are backed by a blocking hook in `hooks/blocking/`. Rules without a hook are judgment-based and enforced via audit rubrics (`audit-rubrics/`).
