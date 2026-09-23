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

Red, green, refactor is the default loop for a bug fix and for new behavior. The TDD skill (`pstack:tdd`) carries the procedure, and no hook or lint checks the order. A prototype may run ahead of its tests and adds them before the pull request goes ready. A bug fix ships with a test that reproduces the bug. Review reads the tests on the diff.

## A Fix Carries Its Proof Test

The `Fix test proof` job in `.github/workflows/pr-check.yml` runs `_shared/pr-loop/scripts/fix_pr_test_proof.py` on every pull request whose title starts with `fix`. A fix that changes production code must change at least one Python or Node test that fails on the base and passes on the head. Node tests are files ending in `.test.mjs`, `.test.js`, or `.test.cjs`, and the job runs them with `node --test`. A fix that changes only docs or CI config passes. A fix proven by a PowerShell test needs a Python or Node test beside it.
