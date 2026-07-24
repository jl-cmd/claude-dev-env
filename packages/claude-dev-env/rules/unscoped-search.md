# Unscoped Filesystem Search

**When this applies:** Any Bash or PowerShell command that walks the filesystem with `find`, recursive `Get-ChildItem` / `gci` / `dir` / `ls -R`, or an equivalent whole-tree search.

## Rule

Every filesystem search names a **scoped** start path — a project, worktree, package, or other directory under the work in progress. A search that starts at the filesystem root, a drive root, or bare home is out of bounds.

The `unscoped_search_blocker` PreToolUse hook (Bash/PowerShell, hosted by `bash_pre_tool_use_dispatcher`) denies those shapes and returns the scoped alternative.

## Allowed shapes

| Shape | Example |
|---|---|
| Cwd-relative | `find . -iname '*.py'` |
| Project path | `find packages/claude-dev-env -name code_rules_gate.py` |
| Git Bash scoped path | `find /c/Users/<you>/repo -iname SKILL.md` |
| Recursive listing under a project | `Get-ChildItem -Path .\src -Recurse` |
| Windows file search with scope | `es.exe path:C:\dev\repo ext:py gate` |

## Denied shapes

| Shape | Example |
|---|---|
| Filesystem root | `find / -iname code_rules_gate.py` |
| Git Bash drive root | `find /c -name '*.py'` |
| Windows drive root | `find C:\ -name foo` / `Get-ChildItem C:\ -Recurse` |
| Bare home | `find ~ -name README.md` / `find $HOME -type f` |

## Preferred tools

On Windows, prefer `es.exe` with a path scope (see `es-exe-file-search.md`), or the harness Grep/Glob tools. Prefer Read over shell when the path is already known.

## Shell batching

Issue one shell search at a time when the walk is large. Parallel full-tree searches contend for the shell and can lock the host; the unscoped-root gate blocks the worst roots, and agents still batch remaining shell work.
