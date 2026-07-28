---
paths:
  - "**/rules/**"
---

# rules

Rule files installed into `~/.claude/rules/` by `bin/install.mjs`. A rule without `paths:` frontmatter loads at the start of every session; a rule with `paths:` frontmatter loads only when the session works with a file its globs match. The `InstructionsLoaded` log records that match as a `path_glob_match` event. Each `.md` file covers one named rule; hook-enforced rules are also backed by a Python hook in `hooks/`.

## Files

| File | Rule |
|---|---|
| `agent-spawn-protocol.md` | Check context sufficiency before a spawn and ask subagents for file-and-line answers; `/prompt-generator` is recommended for a complex or user-facing spawn |
| `anti-corollary-tests.md` | Tests must carry information: no corollary matrices over canonical reductions, no suite that only matches a dead-implementation default, stated mutation in the audit lane |
| `ask-user-question-required.md` | Every user-directed question goes through the `AskUserQuestion` tool — no plain-text questions |
| `bdd.md` | BDD discovery-driven development workflow and Example Mapping reference |
| `cleanup-temp-files.md` | Remove temporary files created during a task when the task is complete |
| `code-standards.md` | Pointer to `CODE_RULES.md` as the single source of truth, including §8 (TDD) and §7 (right-sizing); BDD is the outer process and TDD the inner loop |
| `confirm-implementation-forks.md` | Stop and ask when two or more workable implementation paths change the deliverable |
| `conservative-action.md` | Research and recommend when intent is ambiguous; act only on explicit request |
| `context7.md` | Use Context7 MCP to fetch current library docs; always prefer live docs over built-in knowledge |
| `destructive-commands.md` | Allowed removal forms and the ephemeral namespace the `destructive_command_blocker` auto-allows; keep destructive literals out of a Bash command string even as data |
| `doc-inventory-integrity.md` | Three inventory shapes stay in step with the code: a per-directory `CLAUDE.md` file list, a package `README`/`SKILL.md` inventory, and an env-var summary table |
| `doc-prose-cuts.md` | Four sentence shapes to cut from prose: exclusion claims, justification sentences, conversation references, and time references |
| `docstring-prose-matches-implementation.md` | Prose enumerations in docstrings cover every behavior the body applies |
| `durable-post-artifacts.md` | GitHub post bodies never reference volatile scratch paths; text embeds inline and binary artifacts upload to the `artifacts` release with the permanent URL linked |
| `eli11-replies.md` | Every chat reply the user reads follows one shape: action first, detail last, few words; `plain-language.md` governs word choice, this rule governs reply length and shape |
| `explore-thoroughly.md` | Read relevant files and map existing patterns before proposing a change |
| `file-global-constants.md` | File-global constants need at least two same-file references; otherwise move value to `config/` |
| `filesystem-search.md` | Every filesystem search names a scope; `es.exe`, `Glob`, `Grep`, and `Read` are equally sanctioned, and the `unscoped_search_blocker` denies a walk from a root |
| `gh-cli-conventions.md` | `--body-file` for every `gh` body; `--paginate --slurp` piped to external `jq` for every paginated list read |
| `git-workflow.md` | PR workflow: always create as draft, one commit per review stage, never commit working docs or images; carries the review-response protocol and a See-also block for its seven siblings |
| `hedging-claims.md` | State the evidence or name the claim unverified; the `hedging_language_blocker` Stop hook sends a hedged response back for a re-check |
| `long-horizon-autonomy.md` | Autonomous-run behaviors: act on what you have, do not end on a promise, delegate and keep working |
| `measurement-denominators.md` | Every reported count names what it scanned and carries its denominator; a rate needs two runs; the consumer cross-checks the count against the scope its denominator names |
| `nas-ssh-invocation.md` | Reach the NAS through the paramiko-backed `nas_ssh_key.py` runner, which signs in-process; every ssh-family client reads the key through file permissions, refuses it, and stalls an unattended run on a password prompt |
| `no-cross-skill-duplicate-helpers.md` | Within one skill a duplicated helper is blocked; across two skill folders a small self-contained copy is a sanctioned isolation tradeoff that draws a non-blocking advisory naming the source skill |
| `orphan-css-class.md` | Every `class="..."` attribute in Python-generated markup has a matching selector in the `<style>` block |
| `paired-test-coverage.md` | A public function omitted by a module's established paired test suite must get a behavioral test |
| `parallel-tools.md` | Make all independent tool calls in a single response |
| `plain-illustrative-docstrings.md` | Public docstring narrative reads plainly and shows behavior with a diagram block (a `::` example or a doctest), painting a concrete scene a general developer follows on first read; a run-on backstop hook, a prose-wall backstop hook, and Category O9 audit enforce it |
| `plain-language.md` | Everyday words, short active sentences, lead with the answer |
| `prompt-workflow-context-controls.md` | Keep prompt-workflow instruction layers small and stable; load heavy skills on demand |
| `proof-of-work-pr-comments.md` | Every PR carries one five-part proof-of-work comment before it leaves draft; the `pr_description_enforcer` hook audits proof-shaped comments and gates `gh pr ready` |
| `re-stage-before-commit.md` | Stage the files edited this session before `git commit`; the session edit stage gate denies a commit that leaves a tracked session edit unstaged, with `-a`, a pathspec, a preceding `git add`, and `# partial-commit` as escapes |
| `research-mode.md` | Three anti-hallucination constraints: say "I don't know", verify with citations, quote for factual grounding |
| `shell-invocation.md` | Windows shell commands run through `pwsh`; no `$(...)`, backtick, or process substitution in a Bash tool command |
| `testing.md` | Test quality and infrastructure standards |
| `vault-context.md` | Search Obsidian vault for prior sessions and decisions before substantive project work |
| `verified-commit-gate-skip.md` | The `# verify-skip` marker on a blocked commit/push is allowed only when the branch surface is the same code a code-verifier already passed clean; any real change since that verdict runs a fresh verification |
| `verify-before-asking.md` | Answer questions by inspecting files or running tools before asking; recalled facts expire until re-checked this session |
| `verify-runtime-state.md` | A "component is fine / not at fault" verdict rests on a live probe this session, never code reading or prior-session memory |
| `windows-filesystem-safe.md` | Use safe `rmtree` patterns on Windows; `mkdirSync` with `recursive: true` on possibly-existing paths |
| `workers-done-before-complete.md` | A task reaches `completed` only when every spawned worker has finished and its results are merged into run state |
| `workflow-substitution-slots.md` | Per-iteration values in `.workflow.js` templates use angle-bracket slots |

## Hook enforcement

Rules marked with ⚡ in `~/.claude/docs/CODE_RULES.md` are backed by a blocking hook in `hooks/blocking/`. Rules without a hook are judgment-based and enforced via audit rubrics (`audit-rubrics/`).
