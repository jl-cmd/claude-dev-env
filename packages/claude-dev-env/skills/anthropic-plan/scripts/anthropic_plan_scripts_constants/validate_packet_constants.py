"""Constants for the plan packet validator."""

from __future__ import annotations

ALL_REQUIRED_RELATIVE_PATHS: tuple[str, ...] = (
    "README.md",
    "packet.json",
    "context/user-request.md",
    "context/source-map.md",
    "context/current-state.md",
    "context/existing-patterns.md",
    "context/constraints.md",
    "context/glossary.md",
    "spec/scope.md",
    "spec/behavior.md",
    "spec/interfaces.md",
    "spec/data-flow.md",
    "spec/failure-modes.md",
    "spec/acceptance.md",
    "implementation/strategy.md",
    "implementation/steps.md",
    "implementation/tdd-plan.md",
    "implementation/file-plan.md",
    "implementation/refactor-checkpoints.md",
    "validation/validator-report.md",
    "validation/deterministic-checks.md",
    "validation/unresolved-risks.md",
    "validation/reuse-audit.md",
    "handoff/build-prompt.md",
    "handoff/review-prompt.md",
    "handoff/verification-commands.md",
)
MARKDOWN_FILE_SUFFIX: str = ".md"
EXIT_CODE_VALIDATION_FAILED: int = 2
