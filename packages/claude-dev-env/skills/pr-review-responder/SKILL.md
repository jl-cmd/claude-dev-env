---
name: pr-review-responder
description: MANDATORY systematic protocol for responding to GitHub PR review comments. Use when addressing PR feedback, code review comments, or before pushing PR fixes. Triggers on "address feedback", "fix review comments", "respond to code review", "handle PR feedback", "reply to reviewer".
---
@~/.claude/skills/pr-review-responder/EXAMPLES.md
@~/.claude/skills/pr-review-responder/PRINCIPLES.md

<EXTREMELY_IMPORTANT>
# PR Review Responder

**This skill is MANDATORY when responding to PR review comments.**

IF you are addressing PR review feedback, YOU DO NOT HAVE A CHOICE. YOU MUST FOLLOW THIS PROTOCOL.

**Why this matters:** A typical multi-commit PR with many review comments is easy to fumble. Missing even one comment forces another review round.

## MANDATORY FIRST RESPONSE PROTOCOL

Before doing ANYTHING:

1. [ ] Fetch ALL review comments with `per_page=100` pagination
2. [ ] Create TodoWrite checklist with ONE item per comment
3. [ ] Fix comments ONE AT A TIME, marking complete as you go
4. [ ] Draft reply for EVERY comment (DO NOT post directly)
5. [ ] Create ONE review fix commit (DO NOT squash with original)
6. [ ] Push — the git pre-push hook (installed via `npx claude-dev-env`) runs automatically
7. [ ] Verify ALL draft replies are prepared

**Responding WITHOUT completing this checklist = automatic failure.**

## Critical Rules - NO EXCEPTIONS

### Rule 1: Fetch ALL Comments First

**NEVER start fixing without fetching every comment.**

- [ ] FORBIDDEN: Assuming you know what the comments say
- [ ] FORBIDDEN: Using default pagination (30 results, causes missed comments)
- [x] REQUIRED: `gh api repos/{owner}/{repo}/pulls/{pr_number}/comments?per_page=100`
- [x] REQUIRED: Check for additional pages if 100+ comments

**WHY:** Missing comments forces extra review rounds. Default pagination (30) silently drops comments.

### Rule 2: TodoWrite Checklist Before Any Fixes

**NEVER make fixes without a checklist.**

- [ ] FORBIDDEN: Fixing comments as you read them
- [ ] FORBIDDEN: Bulk-updating todos after fixing multiple items
- [x] REQUIRED: Create TodoWrite with one item per comment BEFORE any fix
- [x] REQUIRED: Include BOTH fix items AND reply items

**WHY:** Without a checklist, you WILL miss comments.

Example checklist:
```
- [ ] Fix: src/views.py:45 - Use shared upload function
- [ ] Fix: src/models.py:23 - Rename user_name to display_name
- [ ] Reply: src/views.py:45 - Post inline response
- [ ] Reply: src/models.py:23 - Post inline response
```

### Rule 3: Fix Systematically

**NEVER skip ahead or bulk-update.**

For each comment in TodoWrite:
1. Read the comment
2. Make the fix
3. Mark todo item complete: `[x]`
4. Verify fix addresses comment
5. Move to next comment

### Rule 4: Draft Replies for User Review

**NEVER post comments directly. Draft them for user to review and post.**

Format each draft reply:
```
DRAFT REPLIES (for user to post):
================================

Comment #1 (file.py:45 - "description"):
Reply: Fixed: [specific description of what was changed]

Comment #2 (file.py:67 - "description"):
Reply: Fixed: [specific description of what was changed]
```

**Reply quality rules:**
- Concise: One sentence maximum
- Specific: Say WHAT changed, not just "fixed"
- Actionable: Reviewer can verify the fix

### Rule 5: Separate Review Fix Commit

**NEVER squash review fixes into the original commit.**

- [ ] FORBIDDEN: Amending the original commit with review fixes
- [ ] FORBIDDEN: Multiple fix commits for the same review round
- [x] REQUIRED: ONE new commit for all review fixes from this round

**WHY:** Squashing shows the ENTIRE feature as new on GitHub instead of just the delta. Keeping commits separate lets the reviewer click the second commit to see exactly what changed.

```bash
git add [files]
git commit -m "fix: address code review feedback

- Fixed: [specific change 1]
- Fixed: [specific change 2]

Addresses review comments from PR #{number}"
```

### Rule 6: Pre-Push Gate Fires Automatically

**The git pre-push hook (installed via `npx claude-dev-env`) runs automatically on every `git push`.** It covers lint, magic values, boolean naming, imports, and all code-rules enforcer checks — no manual invocation needed.

- [ ] FORBIDDEN: Pushing without gate passing
- [ ] FORBIDDEN: Manually handling draft conversion
- [x] REQUIRED: Run `git push`; the pre-push hook fires and blocks if any check fails

Use `/qbug` only when you want a full multi-loop PR audit with subagents after the PR is open — it is NOT a substitute for the pre-push gate and refuses when no PR exists yet.

**WHY:** The pre-push hook catches ALL patterns reviewers flag: code style, draft status, commit structure. It fires automatically so nothing is missed.

### Rule 7: Verify All Drafts Complete

**NEVER declare success without matching draft count to comment count.**

- Count of drafts must match count of comments
- Each draft must reference a specific fix
- Present drafts in clear format for user to copy

## Common Rationalizations That Mean You're About To Fail

- **"I know what the comments say, no need to fetch"** -> WRONG. Missing comments forces extra review rounds.
- **"Let me fix this one quickly before making the checklist"** -> WRONG. Without checklist you will miss others.
- **"I'll post the replies myself to save time"** -> WRONG. User controls what gets posted.
- **"This is a small fix, I can squash it"** -> WRONG. Squashing hides the delta from reviewers.
- **"Pre-push review is overkill for review fixes"** -> WRONG. The git pre-push hook catches style issues you introduced while fixing; it fires automatically on every push.

</EXTREMELY_IMPORTANT>

---

## Final Report Format

Only after ALL validations pass:

```
PR Review Response Complete

Fetched: {X} comments (with per_page=100)
Fixed: {X} issues
Pre-push hook: PASSED (fired automatically on git push)
Draft replies: {X} prepared for user
Commits: 2 (original + review fix, NOT squashed)

TodoWrite checklist: 100% complete

DRAFT REPLIES FOR USER TO POST:
================================
[List all draft replies here]

PR #{number}: {url}

Ready to push!
```

## Edge Cases

**No review comments found:**
Report with verification that per_page=100 was used.

**Comments but no matching changes:**
List the comments and their file locations, ask if fixes were forgotten.

**PR already merged:**
Cannot add review responses to merged PRs. Report error.

## Response Format Rules

**Good replies:**
- Fixed: Removed wrapper function, using direct storage.upload_file()
- Fixed: Extracted shared logic to utils/view_helpers.py
- Fixed: Renamed user_name to display_name to avoid User.username conflict
- Noted: Will handle in separate PR to avoid scope creep

**Bad replies:**
- "Fixed" (not specific)
- "Done" (lazy)
- "Addressed your comment" (tells reviewer nothing)

## Requirements

- `gh` CLI installed and authenticated
- Current branch must have an open PR
- Git repository with remote on GitHub
- Write access to repository

## Remember

This protocol prevents repeated review failures. Being systematic is NOT optional. Missing even ONE comment wastes everyone's time.
