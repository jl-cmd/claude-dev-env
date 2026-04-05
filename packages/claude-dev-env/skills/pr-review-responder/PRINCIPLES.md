# PR Review Response Principles

Theory and best practices for responding to code review comments.

## Why Respond to Review Comments?

### Problem: Silent Fixes

Common anti-pattern:
1. Reviewer leaves comments
2. Developer fixes issues
3. Developer pushes changes
4. Reviewer has to re-review entire PR to find what changed
5. Reviewer doesn't know if comments were addressed

Result: **Wasted time, frustrated reviewers, slower feedback loops**

### Solution: Explicit Responses

Better workflow:
1. Reviewer leaves comments
2. Developer fixes issues
3. Developer responds to each comment: "Fixed: [what changed]"
4. Developer pushes changes
5. Reviewer sees responses, knows what to re-check
6. Faster approval

Result: **Clear communication, faster reviews, happy team**

## Principles of Good Review Responses

### Principle 1: Specificity Over Brevity

**Bad**: "Fixed"
**Good**: "Fixed: Renamed user_name to display_name"

**Why**: Reviewer needs to know WHAT changed, not just that something changed.

**Rule**: One sentence explaining the specific change made.

### Principle 2: Acknowledge, Don't Argue

**Bad**: "The wrapper class provides better encapsulation though"
**Good**: "Fixed: Removed wrapper, using Path().read_bytes()"

**Why**: Code review is not a debate. If reviewer requested change, make it or discuss synchronously.

**Rule**: Responses are for confirmation, not debate. Save discussions for meetings.

### Principle 3: Reviewer Can Verify

**Bad**: "Updated the code"
**Good**: "Fixed: Using select_related('profile') to eliminate N+1 query"

**Why**: Reviewer needs to verify the fix. Specific details make this easy.

**Rule**: Include enough detail for reviewer to quickly verify without deep code inspection.

### Principle 4: One Response Per Comment

**Bad**: (One response for 3 different comments)
**Good**: Individual response on each comment thread

**Why**: GitHub organizes by comment threads. Keeps conversation context clear.

**Rule**: Never combine responses to multiple comments.

### Principle 5: Respond Only to What You Changed

**Bad**: Responding "Fixed" to every comment, even ones you didn't address
**Good**: Only respond to comments where you made changes

**Why**: False positives waste reviewer time. They check, find nothing changed, lose trust.

**Rule**: Only post response if you actually modified the relevant code.

### Principle 6: Acknowledge Good Catches

**Bad**: "Fixed: Using shared function"
**Good**: "Fixed: Good catch! Using shared upload function now"

**Why**: Positive reinforcement encourages thorough reviews. Shows gratitude.

**Rule**: When reviewer finds a real issue, acknowledge it in your response.

### Principle 7: Keep It Short

**Bad**: Multi-paragraph explanation of the architectural decision
**Good**: One sentence stating what changed

**Why**: Review responses are for confirmation, not documentation. Save details for code comments.

**Rule**: Maximum one sentence. If you need more, the change needs discussion.

## Response Format Guide

### Standard Format

```
✅ **Fixed**: [concise description of change]
```

**Components**:
- ✅ checkmark: Visual confirmation, shows positive acknowledgment
- **Fixed**: Bold keyword, makes it scannable in long threads
- Concise description: What changed, not why (code/comments explain why)

### Variations

**Cannot fix now** (rare):
```
📝 **Noted**: Will address in separate PR to avoid scope creep
```

**Needs discussion** (use sparingly):
```
❓ **Question**: Should this be async or sync? Happy to discuss synchronously
```

**Good catch acknowledgment**:
```
✅ **Fixed**: Good catch! [what changed]
```

**Clarification needed** (ask, don't respond):
```
❓ Which shared function should I use here?
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Defending Your Original Code

**Example**:
```
Reviewer: "This wrapper class is unnecessary"
You: "Actually, it provides better separation of concerns and follows
     the Single Responsibility Principle from SOLID..."
```

**Why it's bad**:
- Code review is not the place for architectural debates
- Reviewer already reviewed and decided it's unnecessary
- If you disagree, discuss synchronously (call/meeting)
- Long async debates waste everyone's time

**Better approach**:
```
✅ **Fixed**: Removed wrapper, using Path().read_bytes()
```

If you STRONGLY disagree, discuss in person, then respond with outcome.

### Anti-Pattern 2: Vague Acknowledgments

**Example**:
```
Reviewer: "This causes N+1 queries"
You: "Fixed"
```

**Why it's bad**:
- Reviewer doesn't know HOW you fixed it
- Might have used wrong solution (prefetch vs select_related)
- Requires re-review to verify

**Better approach**:
```
✅ **Fixed**: Added select_related('profile') to eliminate N+1 query
```

Now reviewer knows exactly what to check.

### Anti-Pattern 3: Over-Explaining in Responses

**Example**:
```
Reviewer: "Use the shared upload function"
You: "I've refactored this to use the storage.upload_file()
     function which provides versioned filenames, calculates hashes from
     file contents, updates the filename map in storage, and is shared with
     the web upload interface following the DRY principle..."
```

**Why it's bad**:
- Too verbose for a review response
- Details belong in code comments or commit messages
- Wastes reviewer's time reading

**Better approach**:
```
✅ **Fixed**: Using storage.upload_file()
```

The code and commit message explain the rest.

### Anti-Pattern 4: Responding Before Fixing

**Example**:
```
Reviewer leaves comment → You respond "Will fix" → Days pass → Reviewer asks "Did you fix it?"
```

**Why it's bad**:
- "Will fix" is noise, not signal
- Reviewer can't verify anything
- Creates extra back-and-forth

**Better approach**:
```
Fix the code → Respond with "Fixed: [what changed]" → Push
```

Only respond when done, not when planning.

### Anti-Pattern 5: Batch Responses on Unrelated Comments

**Example**:
```
Reviewer comments on 5 different issues
You post one response: "Fixed all the issues you mentioned"
```

**Why it's bad**:
- Reviewer doesn't know which issues are fixed
- No connection between comment and fix
- Makes re-review difficult

**Better approach**:
```
Individual response on each of the 5 comment threads
```

One-to-one mapping, clear context.

## GitHub Review Comment Types

### Type 1: Inline Code Comments

**What**: Comments on specific lines of code

**GitHub location**: File diffs, attached to specific line numbers

**How to respond**:
```bash
gh api repos/{owner}/{repo}/pulls/comments/{comment_id}/replies \
  -X POST \
  -f body="✅ **Fixed**: [description]"
```

**Skill behavior**: Automatically detects and responds to these

### Type 2: General PR Comments

**What**: Comments on the PR overall, not tied to code

**GitHub location**: PR conversation tab

**How to respond**:
```bash
gh pr comment {pr_number} -b "✅ **Fixed**: [description]"
```

**Skill behavior**: Detects but cannot auto-respond (lacks line context)

### Type 3: Review Summary Comments

**What**: Comments submitted as part of "Review changes" flow

**GitHub location**: Part of a review submission

**How to respond**: Reply to individual comments in the review

**Skill behavior**: Treats these as inline comments

### Type 4: Threaded Conversations

**What**: Back-and-forth discussion on a comment

**GitHub location**: Nested under original comment

**How to respond**: Add to the thread (same as inline comments)

**Skill behavior**: Adds response at end of thread

## Timing and Workflow

### When to Respond

**Best practice**: After fixing, before pushing

**Workflow**:
```
1. Receive review feedback
2. Make code changes addressing feedback
3. Commit changes
4. Respond to review comments (this skill)
5. Push changes
```

**Why**: Reviewer sees responses immediately when they get push notification.

### When NOT to Respond

**Don't respond if**:
- You haven't fixed the issue yet
- Comment is a question (answer instead)
- Comment needs discussion (discuss synchronously)
- You disagree with the feedback (discuss first)

### Multiple Commits

**Scenario**: Several commits addressing different comments

**Approach**: Respond once after all commits

**Workflow**:
```
commit 1: Fix field names
commit 2: Extract validation
commit 3: Add docstrings

Then: Respond to all comments at once
Then: Push all commits
```

**Why**: One batch of responses, one push notification, cleaner.

## Psychology of Review Responses

### Reviewer Perspective

**What reviewers want**:
- Clear confirmation of what changed
- Easy verification (specific details)
- Acknowledgment of their time investment
- Fast feedback loop

**What reviewers hate**:
- Guessing if comments were addressed
- Re-reviewing entire PR to find changes
- Vague responses requiring follow-up
- Defensive arguments

### Developer Perspective

**Benefits of good responses**:
- Faster PR approvals
- Less back-and-forth
- Better reviewer relationships
- Clearer feedback loops

**Costs of poor responses**:
- Slower reviews
- Frustrated reviewers
- Longer PR lifetimes
- Less thorough future reviews

## Cultural Context

### High-Trust Teams

**Characteristic**: Reviewers trust developers to fix issues

**Response style**: Brief confirmations
```
✅ **Fixed**: Using shared function
```

### Low-Trust or New Teams

**Characteristic**: Need more detail to build confidence

**Response style**: Slightly more detail
```
✅ **Fixed**: Using storage.upload_file() instead of boto3 directly
```

### Open Source

**Characteristic**: Reviewers don't know you, need proof

**Response style**: More context
```
✅ **Fixed**: Replaced custom uploader with storage.upload_file() (DRY)
```

Adjust your response detail to your team's culture.

## Automation Benefits

### Manual Response Problems

- Forget to respond to some comments
- Inconsistent response format
- Time-consuming to match comments to changes
- Easy to miss comments in large PRs

### Automated Response Benefits

- **Consistency**: Same format every time
- **Completeness**: Never miss a comment
- **Speed**: Seconds instead of minutes
- **Accuracy**: Automatic matching of changes to comments

### When to Override Automation

**Override if**:
- Need to add context (unusual fix)
- Want to acknowledge particularly good feedback
- Change was complex, needs brief explanation
- Disagreeing with reviewer (then discuss)

## Integration with Development Workflow

### TDD + Review Responses

**Workflow**:
```
1. Write failing test (TDD)
2. Write minimal code to pass (TDD)
3. Commit
4. Create PR
5. Receive review feedback
6. Fix issues (maintaining TDD)
7. Respond to reviews (this skill)
8. Push
```

### CI/CD Integration

**Opportunity**: Hook into CI/CD pipeline

**Example**:
```yaml
# .github/workflows/pr.yml
on: pull_request_review_comment

jobs:
  track-responses:
    runs-on: ubuntu-latest
    steps:
      - name: Check if all comments responded
        run: ./scripts/check_review_responses.sh
```

### Metrics

**Track**:
- Time from review to response
- Percentage of comments with responses
- Time from response to re-review
- PR approval time

**Goal**: Faster feedback loops, higher quality communication

## Advanced: Handling Difficult Situations

### Situation 1: Disagree with Reviewer

**Wrong**:
```
❌ "I disagree, the wrapper provides better encapsulation"
```

**Right**:
```
1. Discuss synchronously (call/Slack)
2. Agree on approach
3. Respond with: "Discussed offline, using [agreed approach]"
```

### Situation 2: Can't Fix in This PR

**Wrong**:
```
❌ "Can't fix this now"
```

**Right**:
```
📝 **Noted**: Will address in separate PR #124 (created) to avoid scope creep
```

### Situation 3: Comment is Actually Wrong

**Wrong**:
```
❌ "Actually this doesn't cause N+1 queries because..."
```

**Right**:
```
1. Politely explain in response
2. If reviewer still wants change, discuss synchronously
3. Either make the change or reach consensus
```

### Situation 4: Massive Refactor Requested

**Wrong**:
```
❌ "That's a huge change, can't do it now"
```

**Right**:
```
📝 **Noted**: Significant refactor, proposing we:
1. Merge this PR as-is (provides value)
2. Create issue #125 for refactor
3. Tackle in dedicated PR next sprint

Thoughts?
```

## Summary

**Core principles**:
1. Be specific (what changed)
2. Be concise (one sentence)
3. Acknowledge good feedback
4. Respond only to what you fixed
5. Make reviewer's job easy

**Format**:
```
✅ **Fixed**: [specific change made]
```

**Timing**:
- After fixing, before pushing

**Automation value**:
- Consistency, completeness, speed

**Result**:
- Faster reviews, happier teams, better code

Use the pr-review-responder skill to make this effortless.
