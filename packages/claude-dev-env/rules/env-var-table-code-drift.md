---
paths:
  - "**/*.md"
---

# Env-Var Summary Table Names a Code File That Reads the Variable

Every row in an env-var summary table pairs an UPPER_SNAKE variable with a code-file path that reads it — written as `` | `GOOGLE_APPLICATION_CREDENTIALS` | `auth/google_auth.py` | ... | ``. When a code change removes the last read of a variable from a file, the same change drops or corrects the table row that names that file.

`env_var_table_code_drift_blocker.py` (PreToolUse on Write|Edit|MultiEdit of `.md`) blocks a row whose named code file exists yet never references the variable, and names the fix. For an Edit, drift a file already held on an untouched row is excluded; a row whose code file resolves nowhere stays quiet (the hook cannot prove the drift).
