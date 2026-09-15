---
paths:
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/*.test.*"
  - "**/*.spec.*"
  - "**/conftest.py"
  - "**/tests/**"
---

# Testing Standards

> **Reference:** TEST_QUALITY.md - Load when writing or reviewing tests.

## Complete Mocks for Testability

**Mocks must include all fields the component actually uses.**

If a component renders field X, the mock must have field X with a valid value.
Incomplete mocks make it impossible to distinguish "broken code" from "missing data".

## Tests Exercise Real Behavior

Tests exercise real behavior, real data, and production code paths. A test that asserts on a stand-in for the production path proves the stand-in works.

## No Gate Holds the Test-First Order

`tdd_enforcer.py` once required a fresh, failing test before a production module was written. Nothing runs it now, and the staged policy lint carries no replacement. Hold the red-green-refactor order yourself, and let review check it on the diff.

`hooks/observability/test_failure_recorder.py` still runs on every Bash call. It records a single unchained pytest run that names a test file path and reports a failing exit status, storing the command, that exit status, and the path in the content-hash store. `content_hash_store.py`'s module docstring holds the full contract. No gate reads that store today, so the record serves as history rather than a precondition.
