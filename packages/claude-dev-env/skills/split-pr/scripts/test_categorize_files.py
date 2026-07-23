"""Behavioral tests for path-layer categorization."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from categorize_files import (  # noqa: E402
    annotate_files,
    assign_layer,
    build_slices_from_files,
    normalize_path,
)
from split_pr_scripts_constants.config.categorize_constants import (  # noqa: E402
    LAYER_BACKEND,
    LAYER_DATABASE,
    LAYER_FRONTEND,
    LAYER_OTHER,
    LAYER_TESTS,
)
from split_pr_scripts_constants.config.plan_constants import (  # noqa: E402
    FILE_KEY_LAYER,
    FILE_KEY_PATH,
    SLICE_KEY_FILES,
    SLICE_KEY_LAYER,
)


def test_normalize_path_converts_backslashes() -> None:
    assert normalize_path(r"src\api\x.ts") == "src/api/x.ts"


def test_assign_layer_database_prisma() -> None:
    assert assign_layer("prisma/schema.prisma") == LAYER_DATABASE


def test_assign_layer_backend_api() -> None:
    assert assign_layer("src/api/notifications.ts") == LAYER_BACKEND


def test_assign_layer_frontend_component() -> None:
    assert assign_layer("src/components/Bell.tsx") == LAYER_FRONTEND


def test_assign_layer_tests_pytest_name() -> None:
    assert assign_layer("tests/test_notify.py") == LAYER_TESTS


def test_assign_layer_unknown_is_other() -> None:
    assert assign_layer("random/binary.dat") == LAYER_OTHER


def test_annotate_files_sets_layer() -> None:
    all_annotated = annotate_files([{FILE_KEY_PATH: "src/api/x.ts"}])
    assert all_annotated[0][FILE_KEY_LAYER] == LAYER_BACKEND


def test_build_slices_from_files_orders_layers_and_skips_empty() -> None:
    all_files = annotate_files(
        [
            {FILE_KEY_PATH: "src/components/A.tsx"},
            {FILE_KEY_PATH: "prisma/schema.prisma"},
            {FILE_KEY_PATH: "src/api/b.ts"},
        ]
    )
    all_slices = build_slices_from_files(
        all_files,
        feature_slug="notifications",
        title_prefix="feat",
    )
    assert [each[SLICE_KEY_LAYER] for each in all_slices] == [
        LAYER_DATABASE,
        LAYER_BACKEND,
        LAYER_FRONTEND,
    ]
    assert all_slices[0][SLICE_KEY_FILES] == ["prisma/schema.prisma"]
