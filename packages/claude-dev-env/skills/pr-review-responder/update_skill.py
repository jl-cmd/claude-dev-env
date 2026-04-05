#!/usr/bin/env python3
"""Update pr-review-responder skill with all changes at once."""

import re
from pathlib import Path

SKILL_PATH = Path(__file__).parent / "SKILL.md"

def main() -> None:
    content = SKILL_PATH.read_text(encoding="utf-8")

    # 1. Change 7-step to 8-step
    content = content.replace("strict 7-step protocol", "strict 8-step protocol")

    # 2. Update Step 4: Change from posting to drafting
    old_step4 = '''## STEP 4: REPLY TO EACH COMMENT INLINE (MANDATORY)

**For EACH comment, you MUST post an inline reply.**

**NOT a summary comment. NOT a general "fixed everything" comment. EACH comment gets INDIVIDUAL reply.**

1. **Response format**:
   ```
   ✅ **Fixed**: [brief description of what was changed]
   ```

2. **Post inline reply**:
   ```bash
   gh api repos/{owner}/{repo}/pulls/comments/{comment_id}/replies \\
     -X POST \\
     -f body="✅ **Fixed**: [description]"
   ```

3. **Examples**:
   - `✅ **Fixed**: Removed wrapper function, using direct storage.upload_file() calls`
   - `✅ **Fixed**: Extracted shared logic to utils/view_helpers.py`
   - `✅ **Fixed**: Moved CSS values from Python to stylesheet`
   - `✅ **Fixed**: Added type hints to all function parameters`

**CRITICAL VALIDATION:**
- ☐ Did you reply to EVERY comment? (not just some)
- ☐ Are replies inline? (not summary comment)
- ☐ Did you mark reply todos complete?

**If validation fails:**
```
ERROR: Missing inline replies.
Found {X} comments but only {Y} replies.
STOPPING execution.
```

**Why this matters:** Reviewers need to know WHICH comments were addressed. Summary comments don't cut it.'''

    new_step4 = '''## STEP 4: DRAFT REPLIES FOR EACH COMMENT (MANDATORY)

**For EACH comment, you MUST draft an inline reply for the user to post.**

**DO NOT POST COMMENTS DIRECTLY. Draft them and present to user for review.**

1. **Response format**:
   ```
   ✅ **Fixed**: [brief description of what was changed]
   ```

2. **Draft replies in a clear format for user to copy**:
   ```
   DRAFT REPLIES (for user to post):
   ================================

   Comment #1 (file.py:45 - "description of comment"):
   Reply: ✅ **Fixed**: [description of fix]

   Comment #2 (file.py:67 - "description of comment"):
   Reply: ✅ **Fixed**: [description of fix]
   ```

3. **Examples**:
   - `✅ **Fixed**: Removed wrapper function, using direct storage.upload_file() calls`
   - `✅ **Fixed**: Extracted shared logic to utils/view_helpers.py`
   - `✅ **Fixed**: Moved CSS values from Python to stylesheet`
   - `✅ **Fixed**: Added type hints to all function parameters`

**CRITICAL VALIDATION:**
- ☐ Did you draft a reply for EVERY comment? (not just some)
- ☐ Are drafts specific and actionable?
- ☐ Did you present drafts clearly for user review?

**Why this matters:** User controls what gets posted. Drafts ensure nothing is missed while giving user final say.'''

    content = content.replace(old_step4, new_step4)

    # 3. Add new Step 5 (pre-push-review) before Step 5 (commits)
    old_step5_header = '''---

## STEP 5: KEEP COMMITS SEPARATE (MANDATORY)'''

    new_step5_and_6 = '''---

## STEP 5: RUN PRE-PUSH REVIEW (MANDATORY)

**BEFORE committing, you MUST run the pre-push-review skill.**

**This catches style violations, anti-patterns, and repeat mistakes BEFORE they get committed.**

1. **Invoke the pre-push-review skill**:
   ```
   Skill(pre-push-review)
   ```

2. **CRITICAL VALIDATION**:
   - ☐ Did you run pre-push-review on all changed files?
   - ☐ Did all 22 checks pass?
   - ☐ Did you fix any violations found?

3. **If violations found**:
   - Fix the violations FIRST
   - Re-run pre-push-review
   - Only proceed when all checks pass

**Why this matters:** Pre-push-review catches the EXACT patterns reviewers flag in code reviews. Running it prevents repeat mistakes.

---

## STEP 6: KEEP COMMITS SEPARATE (MANDATORY)'''

    content = content.replace(old_step5_header, new_step5_and_6)

    # 4. Renumber Step 6 -> Step 7
    content = content.replace("## STEP 6: VERIFY ALL REPLIES POSTED", "## STEP 7: VERIFY ALL DRAFTS COMPLETE")

    # 5. Update Step 7 (was 6) content
    old_step6_content = '''**Before declaring success, you MUST verify ALL replies are visible on GitHub.**

1. **Check PR comments page**:
   ```bash
   gh pr view {pr_number} --comments
   ```

2. **CRITICAL VALIDATION**:
   - ☐ Are all replies visible?
   - ☐ Do reply counts match comment counts?
   - ☐ No failed posts?

3. **If validation fails**:
   ```
   ERROR: Reply verification failed.
   Expected {X} replies, found {Y}.
   Check GitHub PR page manually.
   ```'''

    new_step7_content = '''**Before declaring success, you MUST verify ALL reply drafts are prepared.**

1. **Review draft replies**:
   - Count of drafts matches count of comments
   - Each draft is specific and actionable
   - Drafts are formatted clearly for user to copy

2. **CRITICAL VALIDATION**:
   - ☐ Draft count matches comment count?
   - ☐ Each draft references specific fix?
   - ☐ Drafts presented in clear format?

3. **If validation fails**:
   ```
   ERROR: Missing draft replies.
   Expected {X} drafts, found {Y}.
   Complete all drafts before proceeding.
   ```'''

    content = content.replace(old_step6_content, new_step7_content)

    # 6. Renumber Step 7 -> Step 8
    content = content.replace("## STEP 7: FINAL REPORT", "## STEP 8: FINAL REPORT")

    # 7. Update final report
    old_report = '''```
✅ PR Review Response Complete

Fetched: {X} comments (with per_page=100)
Fixed: {X} issues
Replied: {X} inline comments (100% coverage)
Commits: 2 (original + review fix, NOT squashed)

TodoWrite checklist: 100% complete
All inline replies verified on GitHub

PR #{number}: {url}

Ready to push!
```'''

    new_report = '''```
✅ PR Review Response Complete

Fetched: {X} comments (with per_page=100)
Fixed: {X} issues
Pre-push review: PASSED (all 22 checks)
Draft replies: {X} prepared for user
Commits: 2 (original + review fix, NOT squashed)

TodoWrite checklist: 100% complete

DRAFT REPLIES FOR USER TO POST:
================================
[List all draft replies here]

PR #{number}: {url}

Ready to push!
```'''

    content = content.replace(old_report, new_report)

    # 8. Update enforcement mechanisms
    old_enforcement4 = '''4. **Step 4 violation**: Missing inline replies
   ```
   ERROR: Missing inline replies to comments.
   Found {X} comments, only {Y} replies posted.
   Every comment requires individual inline reply.
   STOPPING execution.
   ```

5. **Step 5 violation (ERROR)**: Commits were squashed'''

    new_enforcement4_5_6 = '''4. **Step 4 violation**: Missing draft replies
   ```
   ERROR: Missing draft replies to comments.
   Found {X} comments, only {Y} drafts prepared.
   Every comment requires individual draft reply.
   STOPPING execution.
   ```

5. **Step 5 violation**: Pre-push review not run or failed
   ```
   ERROR: Must run pre-push-review skill before committing.
   This catches style violations and anti-patterns.
   STOPPING execution.
   ```

6. **Step 6 violation (ERROR)**: Commits were squashed'''

    content = content.replace(old_enforcement4, new_enforcement4_5_6)

    # 9. Update Step 6 violation -> Step 7
    content = content.replace(
        '6. **Step 6 violation**: Reply verification failed',
        '7. **Step 7 violation**: Draft verification failed'
    )
    content = content.replace(
        'ERROR: Cannot verify all replies posted to GitHub.\n   Check PR page manually: {url}',
        'ERROR: Cannot verify all draft replies prepared.\n   Expected {X} drafts, found {Y}.\n   Complete all drafts before proceeding.'
    )

    # 10. Update quick reference
    old_quick_ref = '''# 4. Reply inline to EACH comment
gh api repos/{owner}/{repo}/pulls/comments/{comment_id}/replies -X POST -f body="✅ Fixed: ..."

# 5. Create ONE review fix commit (DON'T squash with original)'''

    new_quick_ref = '''# 4. Draft replies for user (DO NOT POST)
# Present drafts in clear format for user to copy and post

# 5. Run pre-push-review skill
Skill(pre-push-review)

# 6. Create ONE review fix commit (DON'T squash with original)'''

    content = content.replace(old_quick_ref, new_quick_ref)

    # 11. Update remaining quick reference steps
    content = content.replace(
        "# 6. Verify ALL replies posted\ngh pr view {pr_number} --comments",
        "# 7. Verify ALL draft replies complete\n# Count drafts matches count of comments"
    )
    content = content.replace(
        "# 7. Push (keeps commits separate for GitHub visibility)\ngit push",
        "# 8. Push (keeps commits separate for GitHub visibility)\ngit push"
    )

    # 12. Update root cause section
    content = content.replace(
        "- Did NOT reply inline to each comment\n- Did NOT verify all replies posted",
        "- Did NOT draft replies for each comment\n- Did NOT run pre-push-review"
    )

    # 13. Update "why protocol is mandatory" section
    content = content.replace(
        "- ✅ Clear communication (inline reply to each)",
        "- ✅ Clear communication (draft reply for each)"
    )

    SKILL_PATH.write_text(content, encoding="utf-8")
    print("Skill updated successfully!")


if __name__ == "__main__":
    main()
