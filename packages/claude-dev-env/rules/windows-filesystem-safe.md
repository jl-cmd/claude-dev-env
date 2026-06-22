# Windows Filesystem Safety

Never call `shutil.rmtree` with `ignore_errors=True` — Windows `ReadOnly` files (e.g. `.git/objects/pack/`) raise `PermissionError`, the flag swallows it, and the tree silently stays on disk. Use an `onexc` (Python >= 3.12) / `onerror` handler that runs `os.chmod(target_path, stat.S_IWRITE)` then retries the removal function the failure interrupted.

In Node, call `mkdirSync(targetPath, { recursive: true })` on possibly-existing paths — `ReadOnly` directories break the non-recursive form. When the call must be non-recursive, strip the attribute first (`(Get-Item $path -Force).Attributes = "Directory"` / `os.chmod(path, stat.S_IWRITE)`).

The `windows_rmtree_blocker.py` PreToolUse hook (Write/Edit/Bash) blocks the unsafe rmtree pattern and returns the full `force_rmtree` safe-pattern code.

Define the safe handler trio (`_strip_read_only_and_retry`, `_force_remove_tree` / `force_rmtree`, and the `inspect.signature` onexc/onerror guard) once in a shared Windows-filesystem utility module, and import it from every call site. A second local copy drifts from the first — a fix lands in one and the other keeps the bug (CODE_RULES.md section 3, Reuse before create). The `duplicate_rmtree_helper_blocker.py` PreToolUse hook (Write/Edit) blocks a local re-definition of any trio member outside the shared home and points the writer at the import. This complements the same-directory `check_duplicate_function_body_across_files` gate, which a copy between two distant packages slips past.
