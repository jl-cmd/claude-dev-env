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

## The File-Level TDD Gate Reads Content, Not the Clock

`tdd_enforcer.py` remembers each candidate test's last-observed content hash, so a touch does not count. A first sighting needs content HEAD does not have yet, not only a fresh, real test.
