# Category F — Silent failures

**What this category audits:** catch-all except clauses, unconditional success returns, errors logged then swallowed, default fallback values masking failure, async task error swallowing, boolean returns that produce the same value on success and failure, ignored return values from fallible calls, PowerShell `-ErrorAction SilentlyContinue` patterns that hide errors.

**Examples of Category F findings:**
- `except Exception: pass` swallows every error including programming bugs.
- A function returns `True` on the success path and `True` on every error path too.
- An async task error is logged while the caller continues as if it succeeded.
- `subprocess.run(...)` without `check=True` and the return code is never inspected.
- `Get-Command X -ErrorAction SilentlyContinue` followed by `.Source` access — the null is silently absorbed.
- A new write-time gate parses `tool_input` content with `ast.parse`; the dispatcher passes the Edit tool's `new_string` fragment; the partial fragment never parses; `except SyntaxError: return []` silently fires zero findings. The gate appears to ship working tests against full-file fixtures but is dead on every Edit in production.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category F)

| ID | Axis name | Concrete checks |
|---|---|---|
| F1 | Catch-all except clauses | `except:` (bare), `except Exception:`, `except BaseException:` followed by `pass` / `continue` / log-only. |
| F2 | Errors logged then swallowed | `logger.error(...)` followed by `return None` / `return default` without re-raise. |
| F3 | Default fallback values masking failure | `dict.get(key, default)` where the absence of the key is itself a bug; `or default` short-circuits hiding `None`. |
| F4 | Async task error swallowing | `asyncio.create_task(...)` without exception observation; `gather(..., return_exceptions=True)` consumed loosely. |
| F5 | Boolean / status returns identical on success and failure | A function returns `True` on the happy path and `True` on the catch-all error path. |
| F6 | Ignored return values from fallible calls | `subprocess.run` without `check=True` and unchecked `returncode`; `os.write` return value discarded. |
| F7 | PowerShell error-suppression patterns | `-ErrorAction SilentlyContinue` followed by `.Property` access; `2>$null` or `*>$null`; `$?` not consulted. |
| F8 | Test-level swallowing | Tests that catch and log instead of asserting; `pytest.warns` used instead of `pytest.raises`. |
| F9 | Gate-validator self-defeat via parse-failure swallow | A new gate / validator / hook check parses input as code (`ast.parse`) and catches the parse error with `return []` / `return None` / `return True` (clean signal). When the dispatcher feeds the check a partial fragment (e.g., the Edit tool's `new_string` rather than the full file content), the parse always fails and the check silently fires zero findings. The audit teammate lists every new `ast.parse` / `tokenize` / `json.loads` / `yaml.safe_load` call in gate code and asks: does the catch branch produce a clean signal that would mask the gate being broken? |
| F10 | Guard helper returns success-default on unverifiable input | A guard helper / predicate / classifier short-circuits to `True` / `Ok` / the success sentinel when it cannot validate the input shape (missing positional args, wrong arity, unexpected None). Guards must default-deny when they cannot verify; default-allow on unverifiable input masks real violations downstream. |

---

## Sample prompt

The reusable Variant C template for Category F is in [`../prompts/category-f-silent-failures.md`](../prompts/category-f-silent-failures.md). Inline your artifact under `## Source material` and adapt the sub-bucket bullets to your project's error-handling conventions.

For a literal worked example using PR #394, see [`category-a-api-contracts.md`](category-a-api-contracts.md). Category F walks for that diff:
- F1: two `except OSError: pass` blocks at lines 26 and 32 in `sweep_empty_dirs.py` — first absorbs `getctime` failures (probably fine — file gone), second absorbs `rmdir` failures (silently skips non-empty dirs, no log).
- F7: `Get-Command py -ErrorAction SilentlyContinue` plus `.Source` access — the `if ($_py)` guard catches the null. But `Get-Command python` (fallback) lacks `-ErrorAction` — opposite F7 hazard (loud where silent was intended).
- F6: `Unregister-ScheduledTask -ErrorAction SilentlyContinue` — verify the script's intent on missing task.
