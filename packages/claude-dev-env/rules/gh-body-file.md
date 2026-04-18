# gh --body-file Rule

**Root cause:** In shell-invoked `gh` command contexts used in this repo, passing markdown body text via `--body "..."` can cause backticks to be stored as `\`` literals on GitHub instead of rendering as markdown code formatting. Quoting and escaping rules vary by execution environment (Bash, PowerShell, CMD), but the failure mode is the same: inline code and code fences can be broken in issues, PR descriptions, comments, and reviews written this way.

**Rule:** All `gh` commands that include markdown body content **must** use `--body-file <path>` with a temp file. Never pass body text as a string argument to `--body` or its shorthand `-b`.

## Affected subcommands

- `gh issue create`
- `gh issue edit`
- `gh issue comment`
- `gh pr create`
- `gh pr edit`
- `gh pr comment`
- `gh pr review`

## Safe patterns

### Python (preferred)

```python
import subprocess
import tempfile

body = "## Summary\n\nFixes `foo` by updating `bar`.\n"

with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
    f.write(body)
    body_path = f.name

subprocess.run(["gh", "pr", "create", "--title", "My PR", "--body-file", body_path], check=True)
```

### PowerShell (Windows — preferred for this repo)

`Set-Content -Encoding utf8` writes UTF-8-**with-BOM** on Windows PowerShell 5.1,
which causes `gh` to treat the leading BOM as part of the first heading character
and can corrupt rendering. Use the BOM-free pattern below — it works on both
Windows PowerShell 5.1 and PowerShell 7+.

```powershell
$bodyPath = [System.IO.Path]::ChangeExtension((New-TemporaryFile).FullName, '.md')
$body = @'
## Summary

Fixes `foo` by updating `bar`.
'@
[IO.File]::WriteAllText($bodyPath, $body, [Text.UTF8Encoding]::new($false))

gh pr create --title "My PR" --body-file $bodyPath
```

On PowerShell 7+ you can alternatively use `Set-Content -Encoding utf8NoBOM`,
but the `[IO.File]::WriteAllText` pattern above is version-agnostic.

### Bash

Safe Bash patterns are intentionally omitted from this rule file. This repo
is Windows/PowerShell-first, and Bash-only safe patterns such as `mktemp` and
heredocs are not applicable here. Use the PowerShell example above in shell
contexts in this repo, or the Python example when invoking `gh` from Python.
The "What NOT to do" examples below use Bash syntax for illustration only and
do not imply Bash is a supported safe-pattern environment.

## What NOT to do

```bash
# BAD — backticks become \` on GitHub
gh pr create --title "My PR" --body "Fixes \`foo\` by updating \`bar\`."

# BAD — disallowed by repo policy; markdown body content must use --body-file
gh issue create --title "T" --body 'Use `x` to do `y`'
```

## Enforcement

A PreToolUse hook (`gh-body-arg-blocker.py`) blocks any Bash call that uses
`gh <subcommand> ... --body <arg>` (without `-file`) and returns a corrective
message directing you to use `--body-file` instead.
