# No Inline Destructive-Command Literals in Bash

The `destructive_command_blocker` PreToolUse hook matches destructive patterns (`rm -rf`, `git reset --hard`, `dd`, `mkfs`, `chmod -R`, fork bombs) as raw text anywhere in a Bash-tool command, with no quote-awareness — so a destructive literal carried only as data (a commit message, a PR/issue body, an echoed string, a `python -c` / `node -e` / `awk` argument, a heredoc) trips the confirmation prompt even though the shell never executes it. In a background or auto-mode run no human can answer that prompt, so the call stalls.

Keep destructive literals out of the Bash command string:

- Bodies that describe destructive-command behavior go in a file passed by path — `git commit -F <file>`, `gh ... --body-file <file>` (see [`gh-body-file`](gh-body-file.md)) — never `git commit -m` / `gh ... -b`.
- To exercise or verify the blocker (or any hook), run the committed test suite (`python -m pytest <test_file>`), which passes the command strings as in-language data — never an inline `python -c` harness.
- Genuine cleanup targets the OS temp dir or `$CLAUDE_JOB_DIR/tmp` (auto-allowed as ephemeral), never a repository or worktree path.
