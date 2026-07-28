# Filesystem Search

**When this applies:** Any search for files by name, path, extension, size, or date — through `es.exe`, a shell `find`, a recursive `Get-ChildItem` / `gci` / `dir` / `ls -R`, or the harness Grep and Glob tools.

## The scope invariant

Every filesystem search names a scope. A scope is a project, worktree, or package directory under the work in progress, or a filter that narrows the walk: an `ext:` filter, a `dm:` date filter, a `size:` filter, or a name pattern.

A search that starts at the filesystem root, a drive root, bare home, or a network share is out of bounds. Narrow it to what you need.

## Choosing a tool

Three tools are equally sanctioned; pick by what you know:

| You know | Use |
|---|---|
| The exact path | `Read` — no search at all |
| A name, extension, or date, on Windows | `es.exe` with a path scope |
| A name or path pattern | The harness `Glob` tool |
| Text inside files | The harness `Grep` tool |

When `es.exe` fails or returns nothing, fall back to `Glob` or `Grep` without pausing, and report the outage so the reader knows the index was unavailable. Ask the user only after all three tools fail.

`skills/everything-search/SKILL.md` holds the full `es.exe` operator reference: `ext:`, `dm:`, `size:`, wildcards, OR/AND/NOT, output flags, and the junction and drive-mapping note.

## Allowed and denied shapes

| Allowed | Example |
|---|---|
| Cwd-relative | `find . -iname '*.py'` |
| Project path | `find packages/claude-dev-env -name code_rules_gate.py` |
| Git Bash scoped path | `find /c/Users/<you>/repo -iname SKILL.md` |
| Recursive listing under a project | `Get-ChildItem -Path .\src -Recurse` |
| Scoped Windows index search | `es.exe path:C:\dev\repo ext:py gate` |

| Denied | Example |
|---|---|
| Filesystem root | `find / -iname code_rules_gate.py` |
| Git Bash drive root | `find /c -name '*.py'` |
| Windows drive root | `find C:\ -name foo` / `Get-ChildItem C:\ -Recurse` |
| Bare home | `find ~ -name README.md` / `find $HOME -type f` |
| Network share root | `find //server/share -name x` — a path under the share (`//server/share/project/src`) is allowed |

## Shell batching

Issue one shell search at a time when the walk is large. Parallel full-tree searches contend for the shell and can lock the host. Harness `Grep` and `Glob` calls carry no such cost and run in parallel freely — see [`parallel-tools.md`](parallel-tools.md).

## Enforcement

- `unscoped_search_blocker` (PreToolUse on Bash and PowerShell, hosted by `bash_pre_tool_use_dispatcher`) denies a walk from an unscoped root and returns the scoped alternative.
- `es_exe_path_rewriter` (PreToolUse on Bash) substitutes `{project-name}` placeholders and bare registry keys in an `es.exe` command with their quoted absolute paths, read from `~/.claude/project-paths.json`. It allows and rewrites; it never blocks, and a machine with no registry file passes the command through unchanged. `scripts/setup_project_paths.py` writes the registry.
