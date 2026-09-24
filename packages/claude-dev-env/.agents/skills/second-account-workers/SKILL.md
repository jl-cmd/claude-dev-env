---
name: second-account-workers
description: >-
  Run local headless Claude workers through the second-account picker.
  Triggers: spawn a worker on the second account, offload a worker,
  claude-ev worker, save main account usage.
---

# Second Account Workers

Use this skill when a task needs a local Claude worker and the session should
save main account usage.

## Choose a worker

Keep the Agent tool for small, fast lookups. For any worker that edits code,
researches at length, or runs long, give it its own Git worktree, write a
standalone brief to a file, and launch the account worker in the background.

```bash
python "$HOME/.claude/scripts/claude_account_worker.py" \
  --prompt-file "<brief>" \
  --cwd "<worktree>" \
  --report-file "<report>" \
  >"<worker-log>" 2>&1 &
worker_pid=$!
wait "$worker_pid"
worker_exit=$?
cat "<report>"
```

Read the JSON report and worker log after the process ends. The JSON fields are
`account`, `reason`, `exit_code`, `duration_seconds`, `result`, and `is_error`.
The runner writes one summary line with the selected account, exit code, and
report path.

When the command exits 3 and the report has `"account": "wait"`, both accounts
are out of room. Report the picker's reason and reset time. Do not fall back to
the Agent tool. Claude can also return exit 3 after a worker starts. When the
report account is `main` or `second`, report the child's exit code and result.

Workers never commit, push, or call `gh`. The calling session reviews each
worktree diff and owns every Git step.

## Write a standalone brief

When pstack is installed, the first brief line is `/pstack:poteto-mode`.
Otherwise, begin with the worker role. Include every detail needed to finish
without the calling session's conversation.

```text
/pstack:poteto-mode
Role: <one worker duty>
Owned files: <exact paths this worker may edit>
Acceptance checks:
- <observable behavior>
- <commands to run and expected result>
Report:
Changed: <files and reason>
Proof: <checks run and last result lines>
Blocked: <open issue, or none>
```

Keep the owned file list closed. Name the worktree path with `--cwd` and use a
separate brief and report path for each worker.
