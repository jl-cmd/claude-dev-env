# Category J — CODE_RULES.md compliance

**What this category audits:** the hook-enforced and rubric-enforced rules from `~/.claude/docs/CODE_RULES.md`. Every PR passes through `code_rules_enforcer.py` at write time; flagging Category J findings during audit prevents fix-loops that the gate would otherwise trigger after the fact.

**Examples of Category J findings:**
- A literal `60` appears in a production function body (magic value rule).
- A new `MAX_RETRIES = 3` declared at module scope outside `config/`.
- A parameter named `ctx` instead of `context` (abbreviation rule).
- A function that returns a value with no return-type annotation.
- A new `# explains the loop logic` comment added to production code.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category J)

| ID | Axis name | Concrete checks |
|---|---|---|
| J1 | Magic values in production function bodies | Literals other than `0`, `1`, `-1` inside production function bodies. Test files exempt. |
| J2 | String-template magic | f-strings whose structural literal text (paths, URLs, patterns) belongs in `config/`. |
| J3 | Constants location | Module-level `UPPER_SNAKE = ...` outside `config/` in production code. Exempt path families: `config/*`, `/migrations/`, `/workflow/`, `_tab.py`, `/states.py`, `/modules.py`, test files. |
| J4 | File-global use-count | A file-global constant referenced by fewer than two methods/functions/classes in the same file. |
| J5 | Abbreviations | `ctx`, `cfg`, `msg`, `btn`, `idx`, `cnt`, `elem`, `val`, `tmp`, `str`, `num`, `arr`, `obj`, `fn`, `cb`, `req`, `res`. (Loop counters `i`/`j`/`k` and `e` for exceptions are exempt.) |
| J6 | Vague names | `result`, `data`, `output`, `response`, `value`, `item`, `temp`, `info`, `stuff`, `thing`. Vague prefixes: `handle`, `process`, `manage`, `do`. |
| J7 | Type hints | Missing type annotation on a parameter or return; presence of `Any` or `# type: ignore`. |
| J8 | New inline comments | New `#` or `//` comments in production code added by this diff. (Existing comments are NEVER removed — Comment Preservation rule.) |
| J9 | Logging format | `log_*(f"...")` rather than `log_*("...", arg)`. |
| J10 | Imports inside functions | `import` statements placed inside function bodies. |
| J11 | sys.path.insert dedup | `sys.path.insert(0, X)` must be guarded by `if X not in sys.path:` (test files exempt). |
| J12 | Hardcoded user paths | String literals naming a specific user's home directory (`C:/Users/jon/...`, `/Users/alice/...`, `/home/bob/...`). Use `pathlib.Path.home()`. |

Test files (`test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*`, `conftest.py`, paths under `/tests/`) are exempt from Category J except where the rule explicitly applies (e.g., J11 on `sys.path.insert`).

---

## Sample prompt

The reusable Variant C template for Category J is in [`../prompts/category-j-code-rules-compliance.md`](../prompts/category-j-code-rules-compliance.md). Inline your artifact under `## Source material` and walk every sub-bucket — many J findings are caught by the write-time hook, but the audit catches the residue.

For a literal worked example using PR #394, see [`category-a-api-contracts.md`](category-a-api-contracts.md). Category J walks for that diff:
- J1: literal `120` in `[int]$AgeSeconds = 120` — already centralized in `config/sweep_config.py:DEFAULT_AGE_SECONDS`. PowerShell side duplicates the value (cross-language drift, see Category K for the conflict-with-existing-code framing).
- J2: f-strings like `f"deleted: {each_directory_path}"` and `f"watching {arguments.root} every {arguments.interval}s"` — the surrounding literal text is descriptive output, not structural; not flagged.
- J3: `_SCRIPTS_DIR` in test file is exempt (test files).
- J7: every parameter and return is annotated; no `Any`, no `# type: ignore`.
- J8: only module-level docstrings; no inline comments added.
