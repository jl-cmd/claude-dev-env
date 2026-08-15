"""Tests for the blast-radius declaration check."""

import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)

from code_rules_blast_radius import check_blast_radius_declared  # noqa: E402

PRODUCTION_PATH = "pipeline/asset_run.py"


def test_should_flag_undeclared_raise_inside_a_loop() -> None:
    """An undeclared raise inside a loop body names no blast radius."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        if not each_member.is_ready:\n"
        "            raise AssetError('member is not ready')\n"
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
    """An ItemBlocked type declares that only this member stops."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        if each_member.is_oversized:\n"
        "            raise AssetItemBlocked('member is one pixel too wide')\n"
    )

    assert check_blast_radius_declared(content, PRODUCTION_PATH) == []


def test_should_accept_a_raise_wrapped_by_a_blast_radius_boundary() -> None:
    """A per-member boundary catching a declared type already parks the failure."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        try:\n"
        "            if each_member.is_oversized:\n"
        "                raise AssetError('member is one pixel too wide')\n"
        "        except AssetItemBlocked as failure:\n"
        "            park(each_member, failure)\n"
    )

    assert check_blast_radius_declared(content, PRODUCTION_PATH) == []


def test_should_ignore_a_raise_outside_every_loop() -> None:
    """A run-level raise sits outside per-member work and needs no declaration."""
    content = (
        "def prepare(manifest):\n"
        "    if manifest is None:\n"
        "        raise AssetError('manifest is absent')\n"
    )

    assert check_blast_radius_declared(content, PRODUCTION_PATH) == []


def test_should_ignore_a_bare_reraise_inside_a_loop() -> None:
    """A bare re-raise propagates an error whose radius is already declared."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        try:\n"
        "            process(each_member)\n"
        "        except AssetItemBlocked:\n"
        "            raise\n"
    )

    assert check_blast_radius_declared(content, PRODUCTION_PATH) == []


def test_should_ignore_test_files() -> None:
    """Test modules raise freely to drive their own scenarios."""
    content = (
        "def test_rejects_bad_member(all_members):\n"
        "    for each_member in all_members:\n"
        "        raise AssetError('boom')\n"
    )

    assert check_blast_radius_declared(content, "pipeline/test_asset_run.py") == []


def test_should_report_every_undeclared_raise_in_one_loop() -> None:
    """Each undeclared raise inside per-member work earns its own advisory line."""
    content = (
        "def run(all_members):\n"
        "    for each_member in all_members:\n"
        "        if each_member.is_missing:\n"
        "            raise AssetError('absent')\n"
        "        if each_member.is_oversized:\n"
        "            raise AssetError('too wide')\n"
    )

    assert len(check_blast_radius_declared(content, PRODUCTION_PATH)) == 2
