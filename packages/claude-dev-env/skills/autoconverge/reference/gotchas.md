# Gotchas

Hard-won lessons for the autoconverge workflow. Append a bullet each time a run
fails in a new way.

- **The workflow script cannot sleep.** `Date.now`, `Math.random`, and timers
  are unavailable in the script body, and a foreground sleep is blocked. Every
  reviewer wait lives inside an `agent`'s own poll loop — a shell-agnostic `sleep`
  loop (PowerShell `Start-Sleep` is an allowed alternative), or `gh` check
  polling. Never try to wait in the script itself.

- **Workflow agents start blank.** Spawned agents do not inherit CLAUDE.md,
  rules, or this skill's context. Each agent prompt is self-contained: it names
  the exact scripts and flags, the full `origin/main...HEAD` diff scope, and the
  return contract.

- **Only the fix lens writes.** The three converge lenses read and report; they
  never edit, commit, or push. Because only the serial fix step pushes, the
  parallel sweep needs no worktree isolation.

- **Fetch origin/main once before the parallel lenses.** The code-review and
  bug-audit lenses both diff against `origin/main`. Concurrent `git fetch` calls
  contend on the worktree `.git` lock and fail intermittently, so the workflow
  runs a single serial `git fetch origin main` (the `prefetch-main` step) at the
  start of each round and the parallel lenses run no git fetch of their own —
  they diff against the already-current ref.

- **The CLEAN bugteam artifact is HEAD-specific.** `check_convergence.py` reads
  the bugteam review on the current HEAD. Any push moves HEAD and invalidates a
  prior artifact, so post it only when a round is fully clean, and post a fresh
  one after any later fix round.

- **Bot login fields differ by endpoint.** `get_reviews` returns `.user.login`
  (an object), while `get_review_comments` returns `.author` (a string). Match
  bot logins with case-insensitive substring tests, not strict equality.

- **`scriptPath` takes a real path, not a shell variable.** `$HOME` expands in a
  Bash command but not in the `Workflow` tool's `scriptPath` argument. Pass the
  expanded absolute path to `workflow/converge.mjs`.

- **Tilde paths fail on Windows Git Bash.** Inside shell calls, use `$HOME/.claude/...`,
  not `~/.claude/...`; a tilde resolves to the wrong home and gives a
  file-not-found error that looks like a script failure.

- **`gh` token drift across accounts.** When a run touches more than one GitHub
  account, pin the token with `--user <login>`; `gh auth token` alone can return
  another account's token after a switch.
