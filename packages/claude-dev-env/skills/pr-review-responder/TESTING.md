# Testing the PR Review Responder Skill

This document provides testing instructions and expected behavior.

## Skill Activation Tests

### Should Activate (Expected Triggers)

Test these queries - skill SHOULD activate:

1. **Direct requests**:
   - "Respond to PR review comments"
   - "Reply to code review feedback"
   - "Post responses to reviewer comments"
   - "Answer PR review comments before pushing"

2. **Workflow mentions**:
   - "Before I push, respond to PR comments"
   - "I need to respond to review feedback"
   - "Help me reply to the PR reviewer"

3. **Context mentions**:
   - "Address PR feedback and respond to comments"
   - "Notify reviewers what I fixed"
   - "Post review responses before pushing"

### Should NOT Activate (False Positives to Avoid)

These queries should NOT activate the skill:

1. **Different operations**:
   - "Create a new PR" → different skill
   - "Review this code" → code review skill
   - "What do the PR comments say?" → just viewing
   - "How do I respond to reviews?" → asking how, not doing

2. **Reading/viewing**:
   - "Show me PR comments"
   - "What feedback did I get?"
   - "Read the review comments"

3. **Other PR operations**:
   - "Merge the PR"
   - "Update PR description"
   - "Add reviewer to PR"

## Functional Tests

### Test 1: Happy Path (with PR and comments)

**Setup**:
```bash
# Create test PR with review comments
gh pr create --title "Test PR" --body "Testing"
# Have someone leave review comments
# Make changes addressing comments
git add .
git commit -m "fix: address feedback"
```

**Test**:
```
"Respond to PR review comments"
```

**Expected behavior**:
1. Detects PR #N
2. Finds review comments
3. Matches comments to changes
4. Drafts responses
5. Shows responses for approval
6. Posts to GitHub after confirmation

**Validation**:
- Check GitHub PR for posted responses
- Verify response format: `✅ **Fixed**: [description]`
- Confirm responses are on correct comment threads

### Test 2: No PR for Branch

**Setup**:
```bash
git checkout -b new-feature
# Don't create PR
git commit -m "add feature"
```

**Test**:
```
"Respond to PR review comments"
```

**Expected behavior**:
1. Checks for PR
2. Finds no PR
3. Informs user: "No PR found for this branch"
4. Suggests creating PR first
5. Exits gracefully

**Validation**:
- No errors thrown
- Clear message to user
- Suggestion to create PR

### Test 3: PR with No Review Comments

**Setup**:
```bash
gh pr create --title "Test PR" --body "Testing"
# No one has reviewed yet
git commit -m "update"
```

**Test**:
```
"Respond to PR review comments"
```

**Expected behavior**:
1. Detects PR
2. Fetches comments
3. Finds no comments
4. Informs user: "No review comments found"
5. Exits gracefully

**Validation**:
- No errors
- Clear message
- No unnecessary API calls

### Test 4: Comments Don't Match Changes

**Setup**:
```bash
gh pr create --title "Test PR" --body "Testing"
# Reviewer comments on src/views.py
# You modify src/models.py instead
git add src/models.py
git commit -m "update models"
```

**Test**:
```
"Respond to PR review comments"
```

**Expected behavior**:
1. Detects PR
2. Finds review comments
3. Gets changed files
4. Finds no matches
5. Shows what comments exist vs what you changed
6. Exits with explanation

**Validation**:
- Lists comment locations
- Lists changed files
- Clear mismatch explanation

### Test 5: Multiple Comments Addressed

**Setup**:
```bash
# PR with 5 review comments across 3 files
# Make changes addressing all 5
git add .
git commit -m "fix: address all feedback"
```

**Test**:
```
"Respond to PR review comments"
```

**Expected behavior**:
1. Detects PR
2. Finds 5 comments
3. Matches all 5 to changes
4. Drafts 5 responses
5. Shows all for approval
6. Posts all 5 after confirmation

**Validation**:
- All 5 responses posted
- Each on correct comment thread
- Consistent format

### Test 6: Already Responded Comments Filtered

**Setup**:
```bash
# PR with 3 comments
# You already responded to 2 yesterday
# Only 1 new comment unresponded
git commit -m "fix: latest feedback"
```

**Test**:
```
"Respond to PR review comments"
```

**Expected behavior**:
1. Detects PR
2. Finds 3 comments total
3. Filters out 2 already-replied
4. Shows only 1 new comment
5. Drafts 1 response
6. Posts 1 response

**Validation**:
- Only 1 new response posted
- Doesn't duplicate on already-replied comments
- Tracks which were skipped

## Standalone Script Tests

### Test 7: Script with Auto-Approve

**Setup**:
```bash
# PR with review comments
# Changes committed
```

**Test**:
```bash
python scripts/respond_to_reviews.py --auto-approve
```

**Expected behavior**:
- Finds comments
- Drafts responses
- Posts WITHOUT asking for confirmation
- Shows success report

**Validation**:
- No interactive prompts
- Responses posted automatically
- Exit code 0

### Test 8: Script with Specific PR Number

**Setup**:
```bash
# Multiple PRs open
# Specify which one
```

**Test**:
```bash
python scripts/respond_to_reviews.py --pr 123
```

**Expected behavior**:
- Uses PR #123 (not auto-detect)
- Processes that PR's comments
- Posts responses

**Validation**:
- Correct PR processed
- Doesn't use current branch's PR

## Edge Cases

### Test 9: Authentication Failure

**Setup**:
```bash
gh auth logout
```

**Test**:
```
"Respond to PR review comments"
```

**Expected behavior**:
- Attempts to fetch PR
- Gets auth error
- Shows clear error message
- Suggests: `gh auth login`

### Test 10: Merged PR

**Setup**:
```bash
# PR is already merged
# Try to respond to old comments
```

**Test**:
```
"Respond to PR review comments"
```

**Expected behavior**:
- Detects PR is merged
- Informs user
- Explains can't add comments to merged PR

### Test 11: Permission Denied

**Setup**:
```bash
# Readonly access to repo
```

**Test**:
```
"Respond to PR review comments"
```

**Expected behavior**:
- Finds comments
- Drafts responses
- Fails to post (permission denied)
- Shows error with suggestion to request access

## Performance Tests

### Test 12: Large PR with Many Comments

**Setup**:
- PR with 50+ review comments
- Changes addressing 20+ comments

**Expected behavior**:
- Handles large number of comments
- Doesn't timeout
- Efficiently matches comments to changes
- Shows progress during processing

**Validation**:
- Completes in reasonable time (< 30 seconds)
- Correct matches found
- All responses posted

## Validation Checklist

Before considering skill production-ready:

- [ ] Frontmatter validated (name lowercase, description < 1024 chars)
- [ ] Directory name matches frontmatter name
- [ ] All activation triggers work
- [ ] False positive triggers correctly avoided
- [ ] Happy path works end-to-end
- [ ] Edge cases handled gracefully
- [ ] Error messages are clear and actionable
- [ ] Standalone script works independently
- [ ] Documentation is comprehensive
- [ ] Examples cover common scenarios

## Debugging

If skill doesn't activate:

1. **Check skill loading**:
   ```bash
   ls ~/.claude/skills/pr-review-responder/SKILL.md
   ```

2. **Restart Claude Code**:
   ```
   Exit and restart to reload skills
   ```

3. **Test with explicit trigger**:
   ```
   "Use the pr-review-responder skill to respond to PR comments"
   ```

4. **Check description specificity**:
   - Does description mention "PR review", "code review", "feedback"?
   - Does it include "respond", "reply", "post"?
   - Are trigger words present?

If script fails:

1. **Check gh CLI**:
   ```bash
   gh --version
   gh auth status
   ```

2. **Check git repository**:
   ```bash
   git remote -v
   ```

3. **Run with error output**:
   ```bash
   python scripts/respond_to_reviews.py 2>&1 | tee debug.log
   ```

## Success Metrics

Skill is working correctly if:

1. **Activation rate**: Activates on relevant queries (>90%)
2. **False positive rate**: Doesn't activate on unrelated queries (<5%)
3. **Matching accuracy**: Correctly matches comments to changes (>85%)
4. **Response quality**: Drafted responses are specific and concise
5. **Posting success**: API calls succeed (>95%)
6. **User satisfaction**: Saves time vs manual responses

Track these over time to validate skill effectiveness.
