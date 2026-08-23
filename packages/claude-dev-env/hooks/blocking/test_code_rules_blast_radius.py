"""Tests for the blast-radius declaration check."""

import sys
from pathlib import Path

import pytest

_blocking_directory = str(Path(__file__).resolve().parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)

from code_rules_blast_radius import check_blast_radius_declared  # noqa: E402

PRODUCTION_PATH = "pipeline/asset_run.py"


def test_should_report_a_loop_raise_with_pending_blast_radius_declaration() -> None:
    """A loop-body raise gets an advisory requesting its blast-radius declaration."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        if each_member.requires_preparation:\n"
        "            raise AssetError('member requires preparation')\n"
    )

    all_issues = check_blast_radius_declared(content, PRODUCTION_PATH)

    assert len(all_issues) == 1
    assert "Line 4" in all_issues[0]


def test_should_accept_a_run_fatal_raise_inside_a_loop() -> None:
    """A RunFatal type declares that the whole run ends."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        if each_member.digest_differs:\n"
        "            raise AssetRunFatal('source bytes changed')\n"
    )

    assert check_blast_radius_declared(content, PRODUCTION_PATH) == []


def test_should_accept_an_item_blocked_raise_inside_a_loop() -> None:
    """An ItemBlocked type declares a member-scoped stop."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        if each_member.requires_resize:\n"
        "            raise AssetItemBlocked('member requires resizing')\n"
    )

    assert check_blast_radius_declared(content, PRODUCTION_PATH) == []


def test_should_accept_a_raise_wrapped_by_a_blast_radius_boundary() -> None:
    """A per-member boundary catches a declared type and parks the failure."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        try:\n"
        "            if each_member.requires_resize:\n"
                "                raise AssetItemBlocked('member requires resizing')\n"
        "        except AssetItemBlocked as failure:\n"
        "            park(each_member, failure)\n"
    )

    assert check_blast_radius_declared(content, PRODUCTION_PATH) == []


def test_should_report_runtime_error_with_a_different_declared_handler() -> None:
    """A different declared handler leaves a runtime crash requiring a name."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        try:\n"
        "            raise RuntimeError('code defect')\n"
        "        except AssetItemBlocked:\n"
        "            park(each_member)\n"
    )

    assert len(check_blast_radius_declared(content, PRODUCTION_PATH)) == 1


@pytest.mark.parametrize("raised_type", ["RuntimeError", "TypeError", "AttributeError", "ValueError"])
def test_should_require_corresponding_handler_for_each_explicit_raise(
    raised_type: str,
) -> None:
    """Each explicit raise needs a handler naming that same type."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        try:\n"
        f"            raise {raised_type}('code defect')\n"
        "        except AssetItemBlocked:\n"
        "            park(each_member)\n"
    )

    assert len(check_blast_radius_declared(content, PRODUCTION_PATH)) == 1


def test_should_accept_a_run_level_raise_during_manifest_preparation() -> None:
    """A run-level raise belongs to manifest preparation."""
    content = (
        "def prepare(manifest):\n"
        "    if manifest.requires_preparation:\n"
        "        raise AssetError('manifest requires preparation')\n"
    )

    assert check_blast_radius_declared(content, PRODUCTION_PATH) == []


def test_should_accept_a_bare_reraise_inside_a_loop() -> None:
    """A bare re-raise propagates an error carrying a declared radius."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        try:\n"
        "            process(each_member)\n"
        "        except AssetItemBlocked:\n"
        "            raise\n"
    )

    assert check_blast_radius_declared(content, PRODUCTION_PATH) == []


def test_should_accept_test_files() -> None:
    """Test modules raise freely during scenario coverage."""
    content = (
        "def test_records_member_failure(all_members):\n"
        "    for each_member in all_members:\n"
        "        raise AssetError('member failure')\n"
    )

    assert check_blast_radius_declared(content, "pipeline/test_asset_run.py") == []


def test_should_report_each_loop_raise_with_pending_blast_radius_declaration() -> None:
    """Each loop-body raise gets an advisory requesting its blast-radius declaration."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        if each_member.requires_source:\n"
        "            raise AssetError('member requires a source')\n"
        "        if each_member.requires_resize:\n"
        "            raise AssetError('member requires resizing')\n"
    )

    assert len(check_blast_radius_declared(content, PRODUCTION_PATH)) == 2
