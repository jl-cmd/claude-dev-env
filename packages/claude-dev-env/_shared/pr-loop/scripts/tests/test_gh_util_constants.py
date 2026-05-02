"""Tests for gh_util_constants.py extracted constant set."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "config" / "gh_util_constants.py"
    specification = importlib.util.spec_from_file_location(
        "config.gh_util_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_default_timeout_seconds_is_typed_integer() -> None:
    assert isinstance(constants_module.DEFAULT_TIMEOUT_SECONDS, int)
    assert constants_module.DEFAULT_TIMEOUT_SECONDS == 30


def test_default_retries_is_typed_integer() -> None:
    assert isinstance(constants_module.DEFAULT_RETRIES, int)
    assert constants_module.DEFAULT_RETRIES == 2


def test_default_backoff_seconds_is_typed_float() -> None:
    assert isinstance(constants_module.DEFAULT_BACKOFF_SECONDS, float)


def test_exponential_backoff_base_is_typed_integer() -> None:
    assert isinstance(constants_module.EXPONENTIAL_BACKOFF_BASE, int)
    assert constants_module.EXPONENTIAL_BACKOFF_BASE == 2


def test_gh_timeout_return_code_is_typed_integer() -> None:
    assert isinstance(constants_module.GH_TIMEOUT_RETURN_CODE, int)
    assert constants_module.GH_TIMEOUT_RETURN_CODE == 124


def test_inline_review_comments_path_template_renders() -> None:
    rendered = constants_module.INLINE_REVIEW_COMMENTS_PATH_TEMPLATE.format(
        owner="acme", repo="lib", pull_number=7
    )
    assert rendered == "/repos/acme/lib/pulls/7/comments"


def test_all_transient_error_markers_is_tuple() -> None:
    assert isinstance(constants_module.ALL_TRANSIENT_ERROR_MARKERS, tuple)
    assert "timeout" in constants_module.ALL_TRANSIENT_ERROR_MARKERS


def test_all_auth_error_markers_is_tuple() -> None:
    assert isinstance(constants_module.ALL_AUTH_ERROR_MARKERS, tuple)
    assert "authentication failed" in constants_module.ALL_AUTH_ERROR_MARKERS
