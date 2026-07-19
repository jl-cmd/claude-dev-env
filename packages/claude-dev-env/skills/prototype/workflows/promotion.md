# Promotion workflow (Phase 2)

Turn a successful proof-of-concept into a real, verified change. Run every step in the normal, fully-hooked session — never inside the `--bare` sandbox. The sandbox produced a reference build; promotion re-verifies it to standard and often rewrites parts of it.

## Seed the task list first

Register every item in `reference/promotion-tasks.md` as a session task (`TaskCreate`, or `TodoWrite` if that is the host tool). Work only from the task list. Mark each complete with evidence — a command result, a path, a verdict, or a skill's return.

## The clean-room protocol

The task seeds carry the full ordered detail. The shape:

1. **Confirm** the POC is worth promoting and the user wants it shipped.
2. **Fresh branch** off freshly-fetched `origin/main` via `fresh-branch` — clean history, based on live upstream.
3. **Bring content as an uncommitted diff.** Copy the POC's file changes into the new branch's working tree. Do not cherry-pick or merge the sandbox commits; the sandbox history stays behind.
4. **Cleanup.** Remove scratch files, debug dumps, and temp helpers the POC created (`cleanup-temp-files` rule).
5. **Privacy sweep** via `privacy-hygiene` over the diff.
6. **Verify** with the `code-verifier` agent — `model: sonnet`, worker-model routing per [`skills/orchestrator/SKILL.md`](../../orchestrator/SKILL.md#workflow-agent-routing); resolver-supplied sonnet-equivalent on third-party hosts — in a fresh context. This is where standards re-engage. Expect findings and a repair loop — the POC was un-TDD'd.
7. **Commit and PR.** Only on a clean verdict, run `/commit`, then open a draft PR per the `git-workflow` rule.
8. **State the honest limitations** from `reference/honest-limitations.md` in the PR body or to the user.
9. **Converge** by handing the PR to `autoconverge` by default; use `pr-converge` for paced ticks or `bugteam` for an open-loop audit.

## Why the clean room, not a push

`code_rules_enforcer` is a write-time Write/Edit gate. Content that lands through `git apply`, `git checkout`, or cherry-pick never passes through it, so pushing the sandbox branch would ship code the rule engine never saw, carrying sandbox scratch along with it. Standards re-engage through the `code-verifier` agent, the `privacy-hygiene` sweep, and the PR review — not through a write-time hook. Steps 4-6 are hard gates: the honest claim on promoted POC code is code-verifier-passed, privacy-swept, review-passed, with TDD ordering waived.

The `verified_commit_gate` hook is the backstop under all of this — it refuses a commit or push with no minted verdict — but the clean-room steps are the mechanism, not the gate firing.
