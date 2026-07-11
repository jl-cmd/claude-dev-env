# pr-review-responder

Mandatory systematic protocol for responding to GitHub PR review comments.

**Trigger:** "address feedback", "fix review comments", "respond to code review", "handle PR feedback", "reply to reviewer".

## Purpose

Prevents missed review comments by enforcing a strict fetch-then-checklist-then-fix order. The skill is declared `MANDATORY` — any PR review response that skips it is an automatic failure per the skill body.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Hub — the seven mandatory rules and the final report format |
| `EXAMPLES.md` | Concrete good and bad reply examples |
| `PRINCIPLES.md` | Design rationale behind the protocol |
| `README.md` | Overview for readers new to the skill |
| `TESTING.md` | Testing guidance for the skill |

## Seven mandatory rules

1. Fetch ALL review comments with `per_page=100` before touching any file.
2. Create a `TodoWrite` checklist — one item per comment — before any fix.
3. Fix one comment at a time, marking each todo complete before moving on.
4. Write reply text for every comment; never post directly.
5. Create ONE new commit for all fixes from this review round; never squash with the original.
6. Push — the git pre-push hook fires automatically.
7. Verify the draft count matches the comment count before reporting done.

## Conventions

- GitHub MCP (`pull_request_read`) with `per_page=100` is the required fetch path.
- Draft replies are presented for the user to post; Claude never posts them directly.
- The pre-push hook (`npx claude-dev-env`) runs on `git push` with no manual invocation.
