# Env-Var Summary Table Names a Code File That Reads the Variable

**When this applies:** Any Write, Edit, or MultiEdit to a markdown (`.md`) file that carries an environment-variable summary table — a markdown table whose rows pair a `` `VARIABLE` `` name with the `` `code/file.py` `` that reads it.

## Rule

Every row in an env-var summary table names a code file whose source references the variable. A row pairs an UPPER_SNAKE variable with a code-file path, written as `` | `GOOGLE_APPLICATION_CREDENTIALS` | `auth/google_auth.py` | ... | ``, and the named file reads that variable. When the file exists yet its source never mentions the variable name, the row is stale: the table points a reader at a consumer relationship the code does not have, so a reader trusts the doc to behavior the code dropped.

When a code change removes the last read of a variable from a file, the same change drops or corrects the table row that names that file. The doc and the code move together in one commit.

## What the gate checks

The `env_var_table_code_drift_blocker.py` hook runs on every Write, Edit, and MultiEdit whose target is a `.md` file. It:

1. Reads the content the tool would leave on disk, skipping lines inside a fenced code block.
2. Collects each table row whose first cell names an UPPER_SNAKE variable and whose later cell names a code file with a recognized extension (`.py`, `.mjs`, `.js`, `.ts`, `.ps1`, `.sh`).
3. Resolves the named code file under the repository root (the nearest `.git`-bearing ancestor of the markdown file) and reads its source.
4. Blocks the write when the file resolves yet its source never references the variable name. For an Edit, drift the file already held on an untouched row is excluded, so only drift the edit introduces is reported.

The check stays quiet for a row whose code file resolves nowhere under the repository root (it cannot prove the drift), a row whose second cell holds no code-file path, a table row inside a fenced code block, and any test file.

## Why this is a hook, not a lint pass

An env-var table that names a file whose source skips the variable reads as a correct map of which code consumes which setting, while pointing one row at behavior the code dropped. A reader trusting the row chases a setting the file ignores, and the gap survives review because the table still looks complete. Catching it as the doc is written keeps the table and the code in step.
