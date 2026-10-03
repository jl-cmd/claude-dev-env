---
paths:
  - "**/*.md"
  - "**/*.py"
  - "**/*.mjs"
  - "**/*.js"
  - "**/*.ts"
  - "**/*.ps1"
  - "**/*.sh"
---

# Documentation Inventory Integrity

A doc that inventories code stays in step with the code, in the same change:

1. Every bare filename a per-directory `CLAUDE.md` names in a table cell or a fenced run command exists in its subtree.
2. A package `README.md` Layout table, `CLAUDE.md` "Key files" list, or skill `SKILL.md` Layout table names each new production file and says what it does. Broaden the purpose sentence and the file's description when its responsibility grows.
3. An env-var table row names a code file that reads the variable.

**Enforcement:** `repository_checks/claude_md.py`, `repository_checks/package_inventory.py`, and `repository_checks/env_var_documentation.py`. Run `python packages/claude-dev-env/scripts/repository_policy.py` before you commit. CI runs the same command.

**Full text:** [`docs/rule-guides/doc-inventory-integrity.md`](../docs/rule-guides/doc-inventory-integrity.md).
