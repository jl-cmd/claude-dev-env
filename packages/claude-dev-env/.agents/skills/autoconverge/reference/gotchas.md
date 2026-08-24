# Gotchas

Hard-won lessons for the autoconverge workflow. Append a bullet each time a run
fails in a new way.

- **The workflow script cannot sleep, and neither can an agent's foreground shell.** `Date.now`, `Math.random`, and timers
  are unavailable in the script body, and a foreground `sleep` / `Start-Sleep` is blocked in the headless harness. Every
  reviewer wait lives inside an `agent`'s own poll loop, and that loop waits with the Monitor tool inside the same turn —
  never a foreground sleep, and never backgrounding a wait and ending the turn to await it, which
  leaves a schema-bearing agent with no `StructuredOutput` call. Never try to wait in the script itself.

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
  runs a single serial `git fetch origin main` inside the merged `preflight-git`
  step — the one git-utility agent that also resolves the PR HEAD SHA, probes
  mergeability, and checks Copilot and Bugbot availability — and the parallel
  lenses run no git fetch of their own; they
  diff against the already-current ref. The workflow threads the resolved HEAD
  through the rounds and re-runs `preflight-git` only after a push or rebase
  invalidates it, so a round on an unchanged HEAD spawns no git agent at all.

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

- **Commit or push fails after a repair.** Read the hook or command output,
  repair the named issue, and record the rerun. Apply the
  [precatch rubric](../../_shared/pr-loop/precatch-rubric.md) before retrying.

- **A Copilot "down" verdict is valid only after the full poll budget.** A
  successful review request means the review is in flight — Copilot typically
  posts within 10–15 minutes of the request. A gate agent that returns
  `down:true` on a partial poll misreports an in-flight review as reviewer
  unavailability, and the run marks the PR ready moments before the review
  lands. After a successful request the only valid gate outcomes are a
  received review on HEAD, an out-of-usage notice, or the full poll budget
  spent. The teardown re-checks the PR for a late-arriving Copilot review
  whenever the gate was bypassed, and routes its findings through one more
  fix round.
