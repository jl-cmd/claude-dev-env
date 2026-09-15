---
paths:
  - "**/*.py"
---

# Public-Function Paired-Test Coverage

**When this applies:** Either side of a paired module/test pair, so the check fires whichever file the write touches:

- A Write or Edit to a production Python module that already has a dedicated stem-matched test file — `test_<stem>.py` beside the module or under an ancestor `tests/` directory — whose paired suite already exercises the module, either by covering at least one of its public functions or by referencing one of its private helpers by name.
- A Write or Edit to a stem-matched test file (`test_<stem>.py` or `<stem>_test.py`) whose paired production module exists on disk and whose post-edit suite already exercises at least one of that module's public functions.

## Rule

Every public function a production module defines is exercised by a test in the module's paired test suite. The suite proves the module is unit-tested function by function, so a public entry point the suite omits is a forgotten test: a reader who trusts the suite to cover the module's public surface misses that gap.

When you add a public function to a module whose test suite already exercises that module — covering a sibling public function, or testing one of its private helpers — add a behavioral test that calls the new function and asserts on its return value or side effect — in the same change that adds the function. A suite that exercises only a private helper (such as a color-conversion helper) while leaving the module's public renderers untested is the exact gap this rule closes. This is the function-level half of the project rule "Every new production code path gets a paired behavioral test ... call the path and assert on what it does."

## What the check covers

Two complementary checks in `code_rules_paired_test.py` reach changed files through `code_rules_enforcer.py`, which the staged policy lint runs under its `code-rules` rule. No write-time hook runs them, so run `python packages/claude-dev-env/scripts/cde_lint.py --staged` before you commit. CI runs the same lint against the merge base. The two checks cover the two write orders.

`check_public_function_missing_paired_test` runs on a production Python write or edit and flags a public function when all of these hold:

1. The target is production code — not a test module, hook infrastructure, config module, migration, workflow registry, or `__init__.py`.
2. A stem-matched test file exists for the module — `test_<stem>.py` or `<stem>_test.py` beside the module, or `test_<stem>.py` under an ancestor `tests/` directory.
3. That suite already exercises the module — referencing at least one public function the module defines, or referencing one of its private (underscore-prefixed) helper functions by name — the signature of a maintained per-module suite rather than a placeholder or unrelated test file.
4. The public function is referenced by no test file in the directory that holds the stem-matched test.

`check_test_file_omits_module_public_function` runs on a stem-matched test-file write or edit and closes the reverse order, in which the production module is written before its test file exists. It resolves the production module the written `test_<stem>.py` or `<stem>_test.py` file pairs with — beside the test file, or in the parent of the `tests/` directory that holds it — reads that module from disk, and flags every public function the post-edit suite references nowhere, subject to the same established-suite precondition (the suite already covers at least one of the module's public functions). A production module that is itself exempt — a test module, hook infrastructure, config module, migration, workflow registry, or `__init__.py` — is skipped.

A public function counts as covered when its name appears — imported, called, or named — in any `test_*.py` or `*_test.py` file in the suite directory, so a function exercised by a differently-named sibling test still counts. `main` and underscore-prefixed functions are never required to carry a test.

## Relationship to the file-level TDD order

`tdd_enforcer.py` once required a fresh test file to exist before a production module was written, judging coverage one file at a time. Nothing runs it now, and the staged policy lint carries no replacement, so the test-first order is yours to hold. This check judges coverage one function at a time for a module that already carries such a test file. Write the test file first, and the lint then reports any public function that file leaves uncovered.

## Why this check is mechanical

A public function with no test reads as covered when the module's test file sits right beside it and exercises its siblings. The gap survives review because the suite looks complete. Running the lint on every staged change keeps the module's public surface and its test suite in step.
