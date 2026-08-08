# Promotion workflow (Phase 2)

Turn a successful proof-of-concept into a real, verified change. Run every step in the normal, fully-hooked session — never inside the `--bare` sandbox. The sandbox produced a reference build; promotion re-verifies it to standard and often rewrites parts of it.

## Seed the task list first

Register every item in `reference/promotion-tasks.md` as a session task (`TaskCreate`, or `TodoWrite` if that is the host tool). Work only from the task list. Mark each complete with evidence — a command result, a path, a review record, or a skill's return.

## The clean-room protocol

The task seeds carry the full ordered detail. The shape:

1. **Confirm** the POC is worth promoting and the user wants it shipped.
2. **Fresh branch** off freshly-fetched `origin/main` via `fresh-branch` — clean history, based on live upstream.
3. **Bring content as an uncommitted diff.** Copy the POC's file changes into the new branch's working tree. Do not cherry-pick or merge the sandbox commits; the sandbox history stays behind.
4. **Cleanup.** Remove scratch files, debug dumps, and temp helpers the POC created (`cleanup-temp-files` rule).
5. **Privacy sweep** via `privacy-hygiene` over the diff.
6. **Review and verify** the real diff against the [review guide](../../reviews/SKILL.md#review-workflow). Record the checks run and repair every required finding.
7. **Commit and PR.** After the review and verification record is complete, run `/commit`, then open a draft PR per the `git-workflow` rule.
8. **State the honest limitations** from `reference/honest-limitations.md` in the PR body or to the user.
9. **Converge** by handing the PR to `autoconverge` by default; use `pr-converge` for paced ticks or `bugteam` for an open-loop audit.

## Why the clean room, not a push

`code_rules_enforcer` is a write-time Write/Edit gate. Content that lands through `git apply`, `git checkout`, or cherry-pick receives the clean-room controls in steps 4–6: cleanup, privacy review, and review and verification under the [review guide](../../reviews/SKILL.md#review-workflow). The promotion record states the checks run and the remaining TDD limitation.
