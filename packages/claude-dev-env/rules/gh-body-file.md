# gh --body-file Rule

Every `gh` command carrying markdown body content (`gh pr create/edit/comment/review`, `gh issue create/edit/comment`) uses `--body-file <path>` with a temp file — never a `--body`/`-b` string, where backticks land on GitHub as literal `\``. Write the temp file BOM-free: `[IO.File]::WriteAllText($bodyPath, $body, [Text.UTF8Encoding]::new($false))`. MCP GitHub tools take `body` as a structured parameter and are unaffected.

`gh_body_arg_blocker.py` (PreToolUse on Bash) blocks `--body <arg>` and returns the corrective message.
