# Windows Filesystem Safety

**When this applies:** Any code that recursively deletes directory trees, or that creates directories on Windows where the path may already exist with a `ReadOnly` attribute set.

## Rule 1 — Never use `shutil.rmtree(..., ignore_errors=True)`

`shutil.rmtree` on Windows raises `PermissionError` when it encounters a file carrying the `ReadOnly` attribute (`FILE_ATTRIBUTE_READONLY`). Linux never hits this case because `unlink` on Linux only requires write on the parent directory, not on the file itself. With `ignore_errors=True` the failure is swallowed and the tree stays on disk — cleanup *looks* successful but pruned nothing.

Tests run inside `pytest`'s `tmp_path` do not exercise the regression path because tmp directories do not carry the attribute. The only place this surfaces is real Windows checkouts (notably git working trees, where `.git/objects/pack/` files are read-only by design).

### Tell-tale sign

`rmtree`-based cleanup that "succeeds" against a real Windows directory but the count of removed entries is zero.

### Safe pattern (inline `force_rmtree`)

Replace `ignore_errors=True` with an `onexc`/`onerror` handler that strips the attribute and retries the same syscall:

```python
import os
import shutil
import stat
import sys


def _strip_read_only_and_retry(removal_function, target_path, *_exc_info):
    try:
        os.chmod(target_path, stat.S_IWRITE)
        removal_function(target_path)
    except OSError:
        pass


def force_rmtree(target_path: str) -> None:
    handler_kw = (
        {"onexc": _strip_read_only_and_retry}
        if sys.version_info >= (3, 12)
        else {"onerror": _strip_read_only_and_retry}
    )
    try:
        shutil.rmtree(target_path, **handler_kw)
    except OSError:
        pass
```

Two things to know about the handler:

- `*_exc_info` collapses the signature difference. `onerror` passes `(type, value, traceback)`; `onexc` (Python 3.12+) passes a single exception. The variadic absorbs both.
- `removal_function` is whichever syscall `rmtree` was attempting when it failed — `os.unlink` for files, `os.rmdir` for directories. Re-calling it after `chmod` finishes the work that originally failed.

### One-liner safe pattern (when shell context demands it)

If a skill or runbook genuinely needs a one-line shell invocation, the equivalent without `ignore_errors=True` is:

```bash
python -c "import os, shutil, stat, sys; h = lambda f, p, *_: (os.chmod(p, stat.S_IWRITE), f(p)); shutil.rmtree(r'<path>', **({'onexc': h} if sys.version_info >= (3, 12) else {'onerror': h}))"
```

Prefer the multi-line `force_rmtree` helper — the one-liner is hard to read and easy to mis-quote.

## Rule 2 — `mkdirSync` without `{ recursive: true }` on possibly-existing paths

Windows directories can also carry the `ReadOnly` attribute (e.g. anything Claude Code creates under `~/.claude/teams/<name>/`, `~/.claude/session-env/<id>/`). The attribute does not break `shutil.rmtree` directly — it breaks Node's `fs.mkdirSync` when called *without* `{ recursive: true }` on a path that already exists.

### Safe pattern

```javascript
import { mkdirSync } from 'node:fs';

mkdirSync(targetPath, { recursive: true });
```

`recursive: true` makes `mkdirSync` idempotent — it succeeds whether the directory exists or not, and skips the attribute check on the existing path.

### When you cannot use `{ recursive: true }`

If the call must be non-recursive for reasons specific to that code path (the existing `bin/git_hooks_installer.mjs` uses `recursive: false` deliberately to assert non-existence), strip the attribute first:

```powershell
(Get-Item $path -Force).Attributes = "Directory"
```

```python
os.chmod(path, stat.S_IWRITE)
```

…and only then call the non-recursive `mkdir`.

## Enforcement

A `PreToolUse` hook (`windows_rmtree_blocker.py`) blocks any `Write`, `Edit`, or `Bash` invocation whose payload contains `shutil.rmtree(..., ignore_errors=True)` and returns this rule's safe pattern as the corrective message.
