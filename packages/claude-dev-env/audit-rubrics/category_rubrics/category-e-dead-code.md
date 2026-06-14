# Category E — Dead code and unused imports

**What this category audits:** imports the diff adds but leaves unreferenced (dead imports), functions defined but never called, code made unreachable by a prior return or raise (dead returns), conditions that are always true or always false (dead branches), parameters that are accepted but never used (dead parameters), local variables assigned but never read (dead locals), removed-but-not-deleted symbols.

**Examples of Category E findings:**
- A new `import` line with zero corresponding references in the file.
- A defined helper function whose call sites the diff also removed.
- Code after an unconditional `return` or `raise`.
- A condition like `if False:` or `while True: ... return` where the loop body always returns immediately.
- An accepted parameter that the function body never uses.
- A local variable assigned and never read afterward in the same function.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category E)

| ID | Axis name | Concrete checks |
|---|---|---|
| E1 | New imports without references | Every `import X` and `from X import Y` introduced by the diff has at least one usage in the same file. |
| E2 | Functions / methods defined but never called | Internal helpers defined in this PR with no call sites in this PR or elsewhere. |
| E3 | Code after unconditional return / raise / exit | Statements following a top-level `return`, `raise`, `sys.exit`, `os._exit` that cannot execute. |
| E4 | Always-true / always-false conditions | `if True:` / `if False:` / conditions provably constant given context. |
| E5 | Unused parameters and locals | Parameters declared but never read inside the function body; local variables assigned but never read afterward in the same scope. |
| E6 | Removed-but-not-deleted symbol references | Symbols renamed/removed elsewhere with stale import or call sites left behind. |
| E7 | Test fixtures / helpers defined but never used | Pytest fixtures, test data builders, mock factories with no callers. |
| E8 | Stub / placeholder code without TODO | `pass`, `...`, `raise NotImplementedError` left without explanation or tracking. |
| E9 | Constants-module exports with no importer | A module-level `UPPER_SNAKE` constant added to a `*_constants.py` / `config/` module that no module in the repo imports and that the constants file itself never references. The file-global use-count gate exempts a constants module because every name it exports legitimately carries zero in-file references, so a genuinely dead export slips past the write-time gate. Distinguish dead from live by grepping the whole repo for each constant name: a sibling such as `MEDIUM_TERMINAL` imported by a consumer module is live; a `MEDIUM_TEXT` that no `from ... import` line and no in-file reference names is dead (CODE_RULES 9.8). Remove the dead export. |

---

## Sample prompt

The reusable Variant C template for Category E is in [`../prompts/category-e-dead-code.md`](../prompts/category-e-dead-code.md). Inline your artifact under `## Source material` and adapt the sub-bucket bullets to your project.

For a literal worked example using PR #394, see [`category-a-api-contracts.md`](category-a-api-contracts.md). Category E walks for that diff:
- E1: every import (`argparse`, `os`, `sys`, `time`, `DEFAULT_AGE_SECONDS`, `DEFAULT_POLL_INTERVAL` in main script; `datetime`, `os`, `subprocess`, `sys`, `tempfile`, `time`, `Path`, `sweep` in test file) has at least one reference — verified clean.
- E5: `for each_directory_path, _, _ in os.walk(...)` discards two of three tuple elements — intentional, not dead.
- E2: `_log_walk_error` is referenced once (passed to `os.walk`); `_build_parser` and `sweep` and `main` all have call sites.
