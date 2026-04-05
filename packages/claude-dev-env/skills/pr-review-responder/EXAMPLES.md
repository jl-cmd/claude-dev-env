# PR Review Responder Examples

Real-world examples of responding to PR review comments.

## Example 1: Over-Engineering Feedback

**Scenario**: Reviewer catches unnecessary wrapper class

**PR Context**:
- PR #12: "Add file upload to admin interface"
- Reviewer: Reviewer
- Comment on `src/storage.py:45`

**Review comment**:
```
Why create a wrapper class here? The Path().read_bytes() approach
is more straightforward and avoids unnecessary abstraction.
```

**Your changes** (commit addressing feedback):
```python
# Before (over-engineered)
class FileReader:
    def __init__(self, path):
        self.path = path

    def read(self):
        return Path(self.path).read_bytes()

file_data = FileReader(file_path).read()

# After (simplified)
file_data = Path(file_path).read_bytes()
```

**Skill execution**:
```
$ "Respond to PR review comments"

Found 1 review comment addressed:

1. @reviewer on src/storage.py:45
   Comment: "Why create a wrapper class here? The Path().read_bytes()..."
   Response: ✅ **Fixed**: Removed FileReader wrapper, using Path().read_bytes() directly

Post this response to the PR? (y/n) y

Posted 1 response to PR #12
View PR: https://github.com/yourorg/project/pull/43

Ready to push!
```

**Posted response on GitHub**:
```
✅ **Fixed**: Removed FileReader wrapper, using Path().read_bytes() directly
```

---

## Example 2: Multiple Comments Across Files

**Scenario**: Refactoring PR with feedback on several files

**PR Context**:
- PR #67: "Refactor timing system"
- Reviewer: Reviewer
- 4 inline comments across 3 files

**Review comments**:

1. **src/views.py:23**:
   ```
   This animation logic is duplicated in the schedule view.
   Should extract to shared utility.
   ```

2. **src/views.py:89**:
   ```
   Same timing calculation here. DRY principle.
   ```

3. **templates/base.html:45**:
   ```
   Why pass CSS timing values through Python context?
   Put them directly in CSS.
   ```

4. **src/utils.py:12**:
   ```
   Good extraction! But needs type hints on parameters.
   ```

**Your changes** (commit addressing all feedback):
```python
# src/utils/view_helpers.py (NEW FILE)
from typing import Dict

def calculate_timing(duration: int, delay: int) -> Dict[str, str]:
    """Calculate CSS animation timing values."""
    return {
        'duration': f'{duration}ms',
        'delay': f'{delay}ms'
    }

# src/views.py (MODIFIED - removed duplication)
from utils.view_helpers import calculate_timing

# templates/base.html (MODIFIED - CSS values direct)
<style>
    .fade-in { animation-duration: 300ms; }
</style>
```

**Skill execution**:
```
$ "Respond to PR review comments before I push"

Found 4 review comments addressed:

1. @reviewer on src/views.py:23
   Comment: "This animation logic is duplicated..."
   Response: ✅ **Fixed**: Extracted to utils/view_helpers.py

2. @reviewer on src/views.py:89
   Comment: "Same timing calculation here. DRY principle."
   Response: ✅ **Fixed**: Now using shared calculate_timing()

3. @reviewer on templates/base.html:45
   Comment: "Why pass CSS timing values through Python context?"
   Response: ✅ **Fixed**: Moved animation values directly to CSS

4. @reviewer on src/utils.py:12
   Comment: "Good extraction! But needs type hints..."
   Response: ✅ **Fixed**: Added type hints (int, Dict[str, str])

Post these 4 responses to the PR? (y/n) y

Posted 4 responses to PR #67
View PR: https://github.com/yourorg/project/pull/67

Ready to push!
```

---

## Example 3: Partial Addressing (Some Comments Not Fixed)

**Scenario**: Some feedback addressed, some deferred

**PR Context**:
- PR #89: "Add user profile customization"
- Reviewer: Reviewer
- 3 comments, only 2 addressed in this commit

**Review comments**:

1. **src/models.py:34**:
   ```
   user_name conflicts with User.username. Rename to display_name.
   ```

2. **src/views.py:56**:
   ```
   This profile logic should be in a service layer, not the view.
   ```

3. **src/forms.py:23**:
   ```
   Missing validation on age field (must be positive).
   ```

**Your changes** (commit addressing 2 of 3):
```python
# Fixed: Renamed field
class UserProfile(models.Model):
    display_name = models.CharField(max_length=100)  # was user_name

# Fixed: Added validation
class ProfileForm(forms.ModelForm):
    def clean_age(self):
        age = self.cleaned_data['age']
        if age <= 0:
            raise ValidationError("Age must be positive")
        return age

# NOT FIXED: Service layer refactor (deferred to separate PR)
```

**Skill execution**:
```
$ "Respond to PR review comments"

Found 3 review comments, 2 addressed in this commit:

1. @reviewer on src/models.py:34
   Comment: "user_name conflicts with User.username..."
   Response: ✅ **Fixed**: Renamed to display_name to avoid conflict

2. @reviewer on src/forms.py:23
   Comment: "Missing validation on age field..."
   Response: ✅ **Fixed**: Added positive integer validation in clean_age()

Not addressed (no changes to these files):
3. @reviewer on src/views.py:56
   Comment: "This profile logic should be in a service layer..."
   [File not modified in this commit]

Post 2 responses to addressed comments? (y/n) y
What about the view.py comment? Add a response? (y/n) y

Custom response for src/views.py:56:
> 📝 **Noted**: Will refactor to service layer in separate PR to keep changes focused

Posted 3 responses to PR #89
Ready to push!
```

---

## Example 4: No Matching Changes (Warning)

**Scenario**: Committed changes don't address any review comments

**PR Context**:
- PR #52: "Add notification system"
- Reviewer: Reviewer
- Comment on `src/notifications.py:23`

**Review comment**:
```
The email sending logic should use async/await for better performance.
```

**Your changes** (commit on different topic):
```python
# Modified src/templates/notifications.html
# (Not related to the async/await comment)
```

**Skill execution**:
```
$ "Respond to PR review comments"

Checking PR #52 for review comments...

Found 1 review comment on src/notifications.py:23
But your commit doesn't modify that file.

Review comment:
  @reviewer: "The email sending logic should use async/await..."

Your changes:
  - templates/notifications.html

No matching changes to respond to. Did you mean to address this comment?
```

---

## Example 5: Already Responded Comments (Filtered Out)

**Scenario**: Some comments already have responses

**PR Context**:
- PR #78: "Refactor authentication flow"
- Multiple commits addressing different comments

**Review comments**:

1. **src/auth.py:12** (ALREADY REPLIED):
   ```
   Reviewer: "Use Django's built-in password validation"
   You (yesterday): "✅ Fixed: Using validate_password()"
   ```

2. **src/views.py:45** (NOT REPLIED):
   ```
   Reviewer: "Session timeout should be configurable"
   ```

**Your changes** (new commit):
```python
# src/settings.py (NEW)
SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '3600'))

# src/views.py (MODIFIED)
request.session.set_expiry(settings.SESSION_TIMEOUT)
```

**Skill execution**:
```
$ "Respond to PR review comments"

Checking PR #78 for review comments...

Found 2 review comments total:
- 1 already has replies (skipping)
- 1 needs response

Comments to respond to:

1. @reviewer on src/views.py:45
   Comment: "Session timeout should be configurable"
   Response: ✅ **Fixed**: Added SESSION_TIMEOUT env variable in settings

Post this response? (y/n) y

Posted 1 response to PR #78
(Skipped 1 already-replied comment)

Ready to push!
```

---

## Example 6: General PR Comments (Not Inline)

**Scenario**: PR-level comments, not tied to specific code lines

**PR Context**:
- PR #91: "Add caching layer"
- General comment (not inline code review)

**Review comment** (general PR comment):
```
Reviewer: "Looks good overall! Can you add tests for the cache invalidation logic?"
```

**Your changes**:
```python
# tests/test_cache.py (NEW)
def test_cache_invalidation():
    # Test implementation
    pass
```

**Skill execution**:
```
$ "Respond to PR review comments"

Checking PR #91 for review comments...

Found 1 general PR comment (not inline):
  @reviewer: "Looks good overall! Can you add tests..."

This is a general comment, not tied to specific code lines.
Cannot auto-respond to general comments.

Suggestion: Reply manually on GitHub or use gh CLI:
  gh pr comment 91 -b "✅ **Added**: Cache invalidation tests in tests/test_cache.py"
```

---

## Example 7: Using Custom Responses

**Scenario**: Skill drafts response, but you want to customize

**PR Context**:
- PR #103: "Optimize database queries"
- Comment about N+1 query

**Review comment**:
```
This causes N+1 queries. Use select_related() or prefetch_related().
```

**Your changes**:
```python
# Before
users = User.objects.all()
for user in users:
    print(user.profile.name)  # N+1 query

# After
users = User.objects.select_related('profile').all()
for user in users:
    print(user.profile.name)  # Single query
```

**Skill execution**:
```
$ "Respond to PR review comments"

Found 1 review comment addressed:

1. @reviewer on src/queries.py:23
   Comment: "This causes N+1 queries..."
   Response: ✅ **Fixed**: Added select_related('profile')

Post this response? (y/n/edit) edit

Edit response:
> ✅ **Fixed**: Added select_related('profile') to eliminate N+1 query. Reduced from 100 queries to 1.

Post edited response? (y/n) y

Posted 1 response to PR #103
Ready to push!
```

---

## Example 8: Multiple Commits, One Response Session

**Scenario**: Addressed different comments in multiple commits

**PR Context**:
- PR #115: "Refactor data models"
- Made 3 commits addressing different feedback

**Your commits**:
```
commit abc123: fix: rename conflicting field names
commit def456: refactor: extract validation to forms
commit ghi789: docs: add docstrings to model methods
```

**Skill execution** (run ONCE after all commits):
```
$ "Respond to all PR review comments for my recent commits"

Analyzing commits abc123..ghi789

Found 3 review comments addressed across 3 commits:

1. @reviewer on src/models.py:34 (fixed in abc123)
   Comment: "user_name conflicts with User.username"
   Response: ✅ **Fixed**: Renamed to display_name

2. @reviewer on src/views.py:45 (fixed in def456)
   Comment: "Validation should be in forms, not views"
   Response: ✅ **Fixed**: Moved validation to ProfileForm.clean()

3. @reviewer on src/models.py:12 (fixed in ghi789)
   Comment: "Missing docstring on calculate_score method"
   Response: ✅ **Fixed**: Added docstring explaining score calculation logic

Post all 3 responses? (y/n) y

Posted 3 responses to PR #115
Ready to push!
```

---

## Integration Patterns

### Pattern 1: Pre-Push Workflow

```bash
# Your workflow
git add .
git commit -m "fix: address PR feedback"

# Before pushing, respond to reviews
"Respond to PR review comments"

# Then push
git push
```

### Pattern 2: Slash Command

```bash
# Add to .claude/settings.json
{
  "commands": {
    "/respond": "Use pr-review-responder skill"
  }
}

# Usage
/respond
```

### Pattern 3: Automated Hook

```bash
# .git/hooks/pre-push
#!/bin/bash
echo "Checking for review comments to respond to..."
claude "Use pr-review-responder skill for current changes"
```

### Pattern 4: Batch Review Response

```bash
# After fixing multiple PRs
cd project1 && "Respond to PR reviews" && git push
cd project2 && "Respond to PR reviews" && git push
cd project3 && "Respond to PR reviews" && git push
```

---

## Response Quality Examples

### Good Responses

✅ **Specific and actionable**:
```
✅ **Fixed**: Extracted upload logic to storage.upload_file()
✅ **Fixed**: Renamed user_name to display_name to avoid User.username conflict
✅ **Fixed**: Moved animation timing from Python context to CSS
✅ **Fixed**: Added type hints (int, str, Optional[Dict])
```

✅ **Acknowledges good feedback**:
```
✅ **Fixed**: Good catch! Removed duplicate error handling
✅ **Fixed**: You're right, using select_related() now
```

✅ **Explains non-obvious changes**:
```
✅ **Fixed**: Using Path().read_bytes() instead of wrapper (KISS)
✅ **Fixed**: Extracted to shared function (DRY principle)
```

### Bad Responses

❌ **Too vague**:
```
Fixed
Done
Updated code
Changed it
```

❌ **Too verbose**:
```
✅ **Fixed**: I removed the FileReader wrapper class that was
creating unnecessary abstraction and replaced it with a direct
call to Path().read_bytes() which is more straightforward and
follows the KISS principle as discussed in CLAUDE.md...
```

❌ **Defensive**:
```
Well, I thought the wrapper was cleaner but I changed it
I guess we can do it your way
Not sure why this is a problem but fixed
```

❌ **Argues in response**:
```
The wrapper class provides better encapsulation though
This is actually a valid pattern from Design Patterns book
```

---

## Advanced: Handling Complex Review Threads

**Scenario**: Long conversation thread on one comment

**Review thread**:
```
Reviewer: "This should use the shared upload function"
You: "Which shared function? I don't see one in the codebase"
Reviewer: "Check storage.py, upload_file()"
You: [makes the change]
```

**Skill behavior**:
- Detects existing conversation thread
- Posts reply at END of thread
- Keeps conversation context

**Posted response**:
```
✅ **Fixed**: Using storage.upload_file() as suggested
```

This appears after the conversation, making it clear this is the resolution.

---

## Summary

The pr-review-responder skill:
- Finds unresponded review comments
- Matches them to your code changes
- Drafts concise, specific responses
- Posts them to GitHub
- Makes PR feedback loops faster

Use it before every push to keep reviewers informed!
