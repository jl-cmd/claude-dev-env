---
paths:
  - "**/*.py"
  - "**/*.mjs"
  - "**/*.js"
  - "**/*.ts"
---

# Windows Filesystem Safety

Never call `shutil.rmtree` with `ignore_errors=True` — Windows `ReadOnly` files (e.g. `.git/objects/pack/`) raise `PermissionError`, the flag swallows it, and the tree silently stays on disk. Use an `onexc` (Python >= 3.12) / `onerror` handler that runs `os.chmod(target_path, stat.S_IWRITE)` then retries the removal function the failure interrupted.

In Node, call `mkdirSync(targetPath, { recursive: true })` on possibly-existing paths — `ReadOnly` directories break the non-recursive form. When the call must be non-recursive, strip the attribute first (`(Get-Item $path -Force).Attributes = "Directory"` / `os.chmod(path, stat.S_IWRITE)`).

The staged policy lint carries this check as its `rmtree-safety` rule. It reports the unsafe rmtree pattern and returns the full `force_rmtree` safe-pattern code. Run `python packages/claude-dev-env/scripts/cde_lint.py --staged` before you commit. CI runs the same lint against the merge base.

Define the safe handler trio (`_strip_read_only_and_retry`, `_force_remove_tree` / `force_rmtree`, and the `inspect.signature` onexc/onerror guard) once in a shared Windows-filesystem utility module, and import it from every call site. A second local copy drifts from the first, so a fix lands in one and the other keeps the bug (CODE_RULES.md, CORE PRINCIPLES, "Reuse before create"). The same `rmtree-safety` lint rule reports a local re-definition of any trio member outside the shared home and points the writer at the import. This complements the same-directory `check_duplicate_function_body_across_files` check, which a copy between two distant packages slips past.
