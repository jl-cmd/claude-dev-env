# Testing Standards

> **Reference:** TEST_QUALITY.md - Load when writing or reviewing tests.

@${CLAUDE_PLUGIN_ROOT}/docs/TEST_QUALITY.md

## Complete Mocks for Testability

**Mocks must include all fields the component actually uses.**

If a component renders field X, the mock must have field X with a valid value.
Incomplete mocks make it impossible to distinguish "broken code" from "missing data".
