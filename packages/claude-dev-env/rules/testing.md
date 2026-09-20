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

**Mocks must include all fields the component uses.**

If a component renders field X, the mock must have field X with a valid value.
Incomplete mocks make it impossible to distinguish "broken code" from "missing data".

## Tests Exercise Production Behavior

Tests exercise production behavior, production data, and production code paths. A test that asserts on a stand-in for the production path proves the stand-in works.

## No Gate Holds the Test-First Order

`tdd_enforcer.py` once required a fresh, failing test before a production module was written. Nothing runs it now, and the staged policy lint carries no replacement. Hold the red-green-refactor order yourself, and let review check it on the diff.
