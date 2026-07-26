"""Path-layer heuristics for file-based PR splits.

Two independent orderings live here. ``ALL_LAYER_ORDER`` is the stacking order
slices are emitted in, running foundation first and leftovers last: database,
contracts, backend, frontend, tests, config, docs, other. ``ALL_LAYER_PATH_RULES``
is match order, most specific pattern first: test and docs paths claim a file
before the database, contracts, backend, frontend, and config patterns see it.
"""

from __future__ import annotations

from .common_constants import PATH_SEPARATOR  # noqa: F401

LAYER_DATABASE = "database"
LAYER_CONTRACTS = "contracts"
LAYER_BACKEND = "backend"
LAYER_FRONTEND = "frontend"
LAYER_TESTS = "tests"
LAYER_CONFIG = "config"
LAYER_DOCS = "docs"
LAYER_OTHER = "other"

ALL_LAYER_ORDER: tuple[str, ...] = (
    LAYER_DATABASE,
    LAYER_CONTRACTS,
    LAYER_BACKEND,
    LAYER_FRONTEND,
    LAYER_TESTS,
    LAYER_CONFIG,
    LAYER_DOCS,
    LAYER_OTHER,
)

ALL_LAYER_PATH_RULES: tuple[tuple[str, str], ...] = (
    (r"(^|/)(__tests?__|tests?|specs?)(/|$)", LAYER_TESTS),
    (r"(^|/)test_[^/]+\.py$", LAYER_TESTS),
    (r"\.(test|spec)\.[a-z0-9]+$", LAYER_TESTS),
    (r"[^/]*_test\.py$", LAYER_TESTS),
    (r"(^|/)docs?(/|$)", LAYER_DOCS),
    (r"\.(md|rst)$", LAYER_DOCS),
    (r"(^|/)(migrations?|prisma|alembic|flyway)(/|$)", LAYER_DATABASE),
    (r"(^|/)db(/|$)", LAYER_DATABASE),
    (r"\.sql$", LAYER_DATABASE),
    (r"(^|/)(types?|contracts?|schemas?)(/|$)", LAYER_CONTRACTS),
    (r"\.proto$", LAYER_CONTRACTS),
    (
        r"(^|/)(api|services?|server|backend|controllers?|middleware|handlers?)(/|$)",
        LAYER_BACKEND,
    ),
    (r"(^|/)hooks/[^/]+/", LAYER_BACKEND),
    (r"(^|/)skills/.+/scripts(/|$)", LAYER_BACKEND),
    (r"(^|/)_shared/.+/scripts(/|$)", LAYER_BACKEND),
    (
        r"(^|/)(components?|pages?|views?|ui|frontend|styles?|contexts?|screens?)(/|$)",
        LAYER_FRONTEND,
    ),
    (r"(^|/)\.github(/|$)", LAYER_CONFIG),
    (
        r"(^|/)(package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|"
        r"tsconfig[^/]*\.json|pyproject\.toml|Cargo\.toml|go\.mod|go\.sum|"
        r"requirements[^/]*\.txt|Pipfile|poetry\.lock|composer\.json)$",
        LAYER_CONFIG,
    ),
)

DEFAULT_LAYER = LAYER_OTHER

PART_SLUG_SEPARATOR = "-part"

ALL_LAYER_STORY_BY_NAME: dict[str, str] = {
    LAYER_DATABASE: "Establish the data foundation",
    LAYER_CONTRACTS: "Add shared types and contracts",
    LAYER_BACKEND: "Implement backend services and API",
    LAYER_FRONTEND: "Add UI components and client surfaces",
    LAYER_TESTS: "Add test coverage for the feature",
    LAYER_CONFIG: "Wire config, packaging, and CI",
    LAYER_DOCS: "Document the feature",
    LAYER_OTHER: "Ship remaining related changes",
}

WHOLE_PR_SLICE_SLUG = "whole-pr"
WHOLE_PR_SLICE_TITLE_STEM = "single reviewable slice"
WHOLE_PR_SLICE_STORY = "Ship the whole pull request as one reviewable slice"

ALL_LAYER_TITLE_STEM_BY_NAME: dict[str, str] = {
    LAYER_DATABASE: "database foundation",
    LAYER_CONTRACTS: "shared contracts",
    LAYER_BACKEND: "backend services",
    LAYER_FRONTEND: "frontend components",
    LAYER_TESTS: "tests",
    LAYER_CONFIG: "config and CI",
    LAYER_DOCS: "docs",
    LAYER_OTHER: "remaining changes",
}
