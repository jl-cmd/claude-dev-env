---
name: "source-command-sum"
description: "Generate a formatted session summary for quick pickup in new sessions"
---

# source-command-sum

Use this skill when the user asks to run the migrated source command `sum`.

## Command Template

Provide a nicely formatted summary of where we are leaving off in this session.

Use this format with proper line breaks:

```
---

**Session Summary: [Project/Task Name]**

**Status:** [Current state - e.g., Complete, In Progress, Blocked]

**Commits:** (if any)
- `hash` - Description

**What's Done:**
- Item 1
- Item 2

**Next Step:**
[Single clear next action]

---
```

Keep it concise but readable. Focus on actionable context, not history.
