# Promotion task seeds (clean-room protocol)

Register every numbered item below as a session task (`TaskCreate`, or `TodoWrite` if that is the host tool) at the start of the promotion phase. Work only from the task list. Mark each complete only with evidence — a command result, a path, a verdict, or a skill's return. This is not a checkbox board; it is a seed catalog for the task tool.

Promotion runs in the **normal, fully-hooked session** — never inside the `--bare` sandbox. Nothing from the sandbox history is carried; only its file content is re-applied and re-verified.

1. **Confirm the prototype is worth promoting.** The sandbox build works and the user (or the standing goal) wants it shipped. Evidence: the working behavior observed, one sentence on what the POC proves.

2. **Fresh branch off live upstream.** Re-fetch `origin/main` and branch from it via the `fresh-branch` skill. Evidence: the returned `base_commit` matches current `origin/main`. This starts clean history and keeps the work based on live upstream.

3. **Bring prototype content as an uncommitted working-tree diff, by allowlist.** Take the sandbox diff against its `base_commit` and copy only the product files you intend to ship into the fresh branch's working tree. Do NOT cherry-pick or merge the sandbox commits, and do NOT bulk-copy the worktree. Exclude the sandbox settings file (`.prototype-sandbox-settings.json`) and every scratch, debug, or artifact file the POC produced — name the files you are bringing, not the ones you are dropping. Evidence: the allowlist of copied paths; `git status` shows only those unstaged; `git log` shows no sandbox commits.

4. **Cleanup pass.** Remove every scratch file, debug dump, and temp helper the prototype created (see the `cleanup-temp-files` rule). Evidence: the removed paths, or a stated "none created".

5. **Privacy sweep.** Run the `privacy-hygiene` skill over the full applied working tree, not only the diff — a POC that pulled live data can leave a secret in a file the diff view hides. Evidence: its clean report, or the leak it found and how it was removed. If the skill is missing, do a manual PII and secret review and say so.

6. **Verify in a fresh context.** Spawn the `code-verifier` agent against the real diff. Expect findings and a repair loop — the code was un-TDD'd. Evidence: the verifier's clean verdict, and a note of what it made you fix. Do not skip this on the belief that the sandbox agent already tested it.

7. **Commit and open a draft PR.** Only on a clean verdict, run `/commit` (which mints the commit-gate verdict and pushes), then open a draft PR per the `git-workflow` rule. Evidence: the commit hash and the PR URL.

8. **State the honest limitations.** Post the two statements from `reference/honest-limitations.md` — write-time rules never ran; TDD ordering waived — in the PR body or to the user. Evidence: the text was included.

9. **Hand to a PR-loop skill.** Hand the PR to `autoconverge` by default — one autonomous run to ready. Reach for `pr-converge` when paced ticks fit better, or `bugteam` for an open-loop audit-fix. Evidence: the skill was invoked, or the user chose to converge manually.
