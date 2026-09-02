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

## The File-Level TDD Gate Reads Content

`tdd_enforcer.py` records each candidate test's content hash at every sighting and compares that hash on the next write. A first sighting requires content that differs from HEAD.

## The Gate Reads a Recorded Failing Run First

`hooks/observability/test_failure_recorder.py` runs on every Bash call and records a single unchained pytest run that names a real test file path and reports a failing exit status. It stores the command, that exit status, and the path in the same content-hash store the gate reads. The gate consults that record before its freshness fallback, and honours it while the candidate's content still matches what failed. `content_hash_store.py`'s module docstring holds the full contract.
