# Public-Function Paired-Test Coverage

**When this applies:** Either side of a paired module/test pair, so the check fires whichever file the write touches:

- A Write or Edit to a production Python module that already has a dedicated stem-matched test file — `test_<stem>.py` beside the module or under an ancestor `tests/` directory — whose paired suite already exercises at least one of the module's public functions.
- A Write or Edit to a stem-matched test file (`test_<stem>.py` or `<stem>_test.py`) whose paired production module exists on disk and whose post-edit suite already exercises at least one of that module's public functions.

## Rule

Every public function a production module defines is exercised by a test in the module's paired test suite. The suite proves the module is unit-tested function by function, so a public entry point the suite omits is a forgotten test: a reader who trusts the suite to cover the module's public surface misses that gap.

When you add a public function to a module whose test suite already covers a sibling public function, add a behavioral test that calls the new function and asserts on its return value or side effect — in the same change that adds the function. This is the function-level half of the project rule "Every new production code path gets a paired behavioral test ... call the path and assert on what it does."

## What the gate checks

Two complementary checks in `code_rules_paired_test.py` (both dispatched from `code_rules_enforcer.py`) cover the two write orders.

`check_public_function_missing_paired_test` runs on a production Python write or edit and flags a public function when all of these hold:

1. The target is production code — not a test module, hook infrastructure, config module, migration, workflow registry, or `__init__.py`.
2. A stem-matched test file (`test_<stem>.py` or `<stem>_test.py`) exists for the module.
3. That suite already references at least one public function the module defines — the signature of a maintained per-function suite rather than a placeholder or unrelated test file.
4. The public function is referenced by no test file in the directory that holds the stem-matched test.

`check_test_file_omits_module_public_function` runs on a stem-matched test-file write or edit and closes the reverse order, in which the production module is written before its test file exists. It resolves the production module the written `test_<stem>.py` or `<stem>_test.py` file pairs with — beside the test file, or in the parent of the `tests/` directory that holds it — reads that module from disk, and flags every public function the post-edit suite references nowhere, subject to the same established-suite precondition (the suite already covers at least one of the module's public functions). A production module that is itself exempt — a test module, hook infrastructure, config module, migration, workflow registry, or `__init__.py` — is skipped.

A public function counts as covered when its name appears — imported, called, or named — in any `test_*.py` or `*_test.py` file in the suite directory, so a function exercised by a differently-named sibling test still counts. `main` and underscore-prefixed functions are never required to carry a test.

## Relationship to the file-level TDD gate

`tdd_enforcer.py` requires a fresh test file to exist before a production module is written; it judges coverage one file at a time. This check judges coverage one function at a time for a module that already carries such a test file. The two compose: the file-level gate ensures a test file exists, and this check ensures that file covers every public function the module exposes.

## Why this is a hook, not a lint pass

A public function with no test reads as covered when the module's test file sits right beside it and exercises its siblings. The gap survives review because the suite looks complete. Catching it as the function is written keeps the module's public surface and its test suite in step.
