"""Tests for check_docstring_delegation_summary_enumeration_drift (O6).

A thin wrapper docstring that enumerates its actions and points at the home
of the real body drifts when the same-named function in that named neighbor
carries a summary enumeration omitting one of those actions. The gate fires
from both sides: saving the wrapper compares it against the named neighbor on
disk, and saving the delegated body compares it against every neighboring
wrapper docstring pointing at it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def check_docstring_delegation_summary_enumeration_drift(
    content: str, file_path: str
) -> list[str]:
    return code_rules_enforcer.check_docstring_delegation_summary_enumeration_drift(
        content, file_path
    )


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"
TARGET_FLOW_STEM = "listing_edit_flow"
PROCESSOR_FILE_NAME = "portal_processor.py"


def _drifted_processor_source() -> str:
    return (
        "class PortalProcessor:\n"
        "    async def _refresh_store_sections(self, page: object) -> bool:\n"
        '        """Apply App Info, Russia, review note, publication edits;'
        " full doc on ``listing_edit_flow``.\"\"\"\n"
        "        return await _refresh_store_sections(self, page)\n"
    )


def _matching_processor_source() -> str:
    return (
        "class PortalProcessor:\n"
        "    async def _refresh_store_sections(self, page: object) -> bool:\n"
        '        """Apply Russia, review note, publication edits;'
        " full doc on ``listing_edit_flow``.\"\"\"\n"
        "        return await _refresh_store_sections(self, page)\n"
    )


def _target_flow_source() -> str:
    return (
        "async def _refresh_store_sections(processor: object, page: object) -> bool:\n"
        '    """Apply Russia uncheck, review note, and Publication edits.\n'
        "\n"
        "    The App Info edit runs earlier in the binary phase and never\n"
        "    repeats here.\n"
        '    """\n'
        "    return True\n"
    )


def _target_flow_plain_summary() -> str:
    return (
        "async def _refresh_store_sections(processor: object, page: object) -> bool:\n"
        '    """Drive one theme end to end."""\n'
        "    return True\n"
    )


def _create_target_flow(directory: Path, source: str) -> Path:
    created_path = directory / (TARGET_FLOW_STEM + ".py")
    created_path.write_text(source, encoding="utf-8")
    return created_path


def test_should_flag_listed_action_absent_from_the_named_neighbor(tmp_path: Path) -> None:
    _create_target_flow(tmp_path, _target_flow_source())
    checked_path = str(tmp_path / PROCESSOR_FILE_NAME)
    issues = check_docstring_delegation_summary_enumeration_drift(
        _drifted_processor_source(), checked_path
    )
    assert any("App Info" in each for each in issues), (
        f"Expected 'App Info' to be flagged, got: {issues!r}"
    )


def test_should_pass_matching_summaries(tmp_path: Path) -> None:
    _create_target_flow(tmp_path, _target_flow_source())
    checked_path = str(tmp_path / PROCESSOR_FILE_NAME)
    issues = check_docstring_delegation_summary_enumeration_drift(
        _matching_processor_source(), checked_path
    )
    assert issues == [], f"Aligned summaries pass, got: {issues!r}"


def test_should_flag_saved_body_that_strands_a_pointing_neighbor(tmp_path: Path) -> None:
    checked_path = tmp_path / PROCESSOR_FILE_NAME
    checked_path.write_text(_drifted_processor_source(), encoding="utf-8")
    created_path = str(tmp_path / (TARGET_FLOW_STEM + ".py"))
    issues = check_docstring_delegation_summary_enumeration_drift(
        _target_flow_source(), created_path
    )
    assert any(
        "App Info" in each and PROCESSOR_FILE_NAME in each for each in issues
    ), f"Expected the stranded caller to be flagged, got: {issues!r}"


def test_should_pass_plain_one_purpose_summary(tmp_path: Path) -> None:
    _create_target_flow(tmp_path, _target_flow_plain_summary())
    checked_path = str(tmp_path / PROCESSOR_FILE_NAME)
    issues = check_docstring_delegation_summary_enumeration_drift(
        _drifted_processor_source(), checked_path
    )
    assert issues == [], (
        f"A comma-free summary compares against nothing, got: {issues!r}"
    )


def test_should_pass_when_the_named_neighbor_does_not_exist(tmp_path: Path) -> None:
    checked_path = str(tmp_path / PROCESSOR_FILE_NAME)
    issues = check_docstring_delegation_summary_enumeration_drift(
        _drifted_processor_source(), checked_path
    )
    assert issues == [], f"Nothing on disk to compare against, got: {issues!r}"


def test_should_pass_single_listed_action(tmp_path: Path) -> None:
    _create_target_flow(tmp_path, _target_flow_source())
    solo_source = (
        "class PortalProcessor:\n"
        "    async def _refresh_store_sections(self, page: object) -> bool:\n"
        '        """Apply the App Info edit;'
        " full doc on ``listing_edit_flow``.\"\"\"\n"
        "        return await _refresh_store_sections(self, page)\n"
    )
    checked_path = str(tmp_path / PROCESSOR_FILE_NAME)
    issues = check_docstring_delegation_summary_enumeration_drift(
        solo_source, checked_path
    )
    assert issues == [], f"A lone named action never fires, got: {issues!r}"


def test_should_skip_strict_test_paths(tmp_path: Path) -> None:
    _create_target_flow(tmp_path, _target_flow_source())
    skipped_path = str(tmp_path / "test_portal_processor.py")
    issues = check_docstring_delegation_summary_enumeration_drift(
        _drifted_processor_source(), skipped_path
    )
    assert issues == [], f"Exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_docstring_delegation_summary_enumeration_drift(
        _drifted_processor_source(), HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully(tmp_path: Path) -> None:
    checked_path = str(tmp_path / PROCESSOR_FILE_NAME)
    issues = check_docstring_delegation_summary_enumeration_drift(
        "def fetch(\n", checked_path
    )
    assert issues == [], f"A syntax error yields no issues, got: {issues!r}"


def test_should_handle_unparseable_neighbor(tmp_path: Path) -> None:
    _create_target_flow(tmp_path, "def broken(\n")
    checked_path = str(tmp_path / PROCESSOR_FILE_NAME)
    issues = check_docstring_delegation_summary_enumeration_drift(
        _drifted_processor_source(), checked_path
    )
    assert issues == [], f"Unparseable neighbors yield no issues, got: {issues!r}"


def test_validate_content_surfaces_the_drift(tmp_path: Path) -> None:
    _create_target_flow(tmp_path, _target_flow_source())
    checked_path = str(tmp_path / PROCESSOR_FILE_NAME)
    issues = validate_content(_drifted_processor_source(), checked_path, old_content="")
    matching_issues = [each for each in issues if "App Info" in each and "O6" in each]
    assert matching_issues, (
        f"Expected validate_content to surface the O6 finding, got: {issues!r}"
    )


def _drifted_processor_source_with_wrapped_summary() -> str:
    return (
        "class PortalProcessor:\n"
        "    async def _refresh_store_sections(self, page: object) -> bool:\n"
        '        """Apply App Info, Russia, review note, publication\n'
        " edits; full doc on ``listing_edit_flow``.\"\"\"\n"
        "        return await _refresh_store_sections(self, page)\n"
    )


def test_should_flag_listed_action_when_the_summary_wraps_a_physical_line(
    tmp_path: Path,
) -> None:
    _create_target_flow(tmp_path, _target_flow_source())
    checked_path = str(tmp_path / PROCESSOR_FILE_NAME)
    issues = check_docstring_delegation_summary_enumeration_drift(
        _drifted_processor_source_with_wrapped_summary(), checked_path
    )
    assert any("App Info" in each for each in issues), (
        f"A summary wrapped onto a second physical line still names 'App Info', "
        f"got: {issues!r}"
    )
