---
paths:
  - "**/*.py"
---

# Public-Function Paired-Test Coverage

**When this applies:** Writing a production Python module whose stem-matched test file (`test_<stem>.py` or `<stem>_test.py`) already exercises it, or writing that test file.

Every public function such a module defines gets a behavioral test in its paired suite. When you add a public function there, add a test that calls it and asserts on its return value or side effect in the same change. `main` and underscore-prefixed functions need none.

**Enforcement:** `check_public_function_missing_paired_test` and `check_test_file_omits_module_public_function` in `code_rules_paired_test.py`, which the staged policy lint runs through `code_rules_enforcer.py`. Both record smells per [`flag-non-breaking-findings.md`](flag-non-breaking-findings.md).

**Full text:** [`docs/rule-guides/paired-test-coverage.md`](../docs/rule-guides/paired-test-coverage.md).
