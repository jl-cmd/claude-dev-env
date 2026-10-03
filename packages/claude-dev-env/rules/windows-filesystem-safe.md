---
paths:
  - "**/*.py"
  - "**/*.mjs"
  - "**/*.js"
  - "**/*.ts"
---

# Windows Filesystem Safety

Call `shutil.rmtree` with an `onexc` (Python 3.12 and later) or `onerror` handler that runs `os.chmod(target_path, stat.S_IWRITE)` and retries. `ignore_errors=True` leaves read-only trees on disk. In Node, call `mkdirSync(targetPath, { recursive: true })` on a path that may exist. Import the shared `force_rmtree` handler trio from its one shared Windows-filesystem module.

**Enforcement:** the staged policy lint's `rmtree-safety` rule, which returns the full `force_rmtree` code. CI runs it against the merge base.

**Full text:** [`docs/rule-guides/windows-filesystem-safe.md`](../docs/rule-guides/windows-filesystem-safe.md).
