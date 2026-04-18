"""Tests for validator path verification script."""

import pytest

from .verify_paths import extract_validator_paths


def test_extract_validator_paths_finds_validator_references() -> None:
    """Test that validator references are extracted from markdown content."""
    content = """
    **Validator:** `validators/import_checks.py`
    Some text here.
    **Validator:** `validators/style_checks.py`
    """

    result = extract_validator_paths(content)

    assert "import_checks.py" in result
    assert "style_checks.py" in result


def test_extract_validator_paths_deduplicates() -> None:
    """Test that duplicate validator references are deduplicated."""
    content = """
    **Validator:** `validators/import_checks.py`
    **Validator:** `validators/import_checks.py`
    **Validator:** `validators/import_checks.py`
    """

    result = extract_validator_paths(content)

    assert result.count("import_checks.py") == 1
