# Windows Filesystem Safety

Never call `shutil.rmtree` with `ignore_errors=True` — Windows `ReadOnly` files (e.g. `.git/objects/pack/`) raise `PermissionError`, the flag swallows it, and the tree silently stays on disk. Use an `onexc` (Python >= 3.12) / `onerror` handler that runs `os.chmod(target_path, stat.S_IWRITE)` then retries the removal function the failure interrupted.

In Node, call `mkdirSync(targetPath, { recursive: true })` on possibly-existing paths — `ReadOnly` directories break the non-recursive form. When the call must be non-recursive, strip the attribute first (`(Get-Item $path -Force).Attributes = "Directory"` / `os.chmod(path, stat.S_IWRITE)`).

The `windows_rmtree_blocker.py` PreToolUse hook (Write/Edit/Bash) blocks the unsafe rmtree pattern and returns the full `force_rmtree` safe-pattern code.
