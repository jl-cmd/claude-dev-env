"""Tests for the validate_content edit-lane and full-gate phase split."""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import inspect
import re
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import DEFAULT, MagicMock, patch

import pytest


def _load_module_from_path(module_name: str, module_path: Path) -> ModuleType:
    """Load and execute the module found at module_path, under module_name."""
    specification = importlib.util.spec_from_file_location(module_name, module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
_HOOKS_DIRECTORY = _BLOCKING_DIRECTORY.parent
_PACKAGE_ROOT = _HOOKS_DIRECTORY.parent
_PR_LOOP_SCRIPTS_DIRECTORY = str(_PACKAGE_ROOT / "_shared" / "pr-loop" / "scripts")

code_rules_enforcer = _load_module_from_path(
    "code_rules_enforcer", _BLOCKING_DIRECTORY / "code_rules_enforcer.py"
)
validation_phase_constants = _load_module_from_path(
    "validation_phase_constants",
    _HOOKS_DIRECTORY / "hooks_constants" / "validation_phase_constants.py",
)

if _PR_LOOP_SCRIPTS_DIRECTORY not in sys.path:
    sys.path.insert(0, _PR_LOOP_SCRIPTS_DIRECTORY)
enforcer_loading = importlib.import_module("code_rules_gate_parts.enforcer_loading")
gate_running = importlib.import_module("code_rules_gate_parts.gate_running")
repo_test_helpers = importlib.import_module("code_rules_gate_parts.tests._repo_test_helpers")

PRODUCTION_FILE_PATH = "packages/app/services.py"
SAMPLE_PYTHON_CONTENT = "def add_one(value: int) -> int:\n    return value + 1\n"
UNKNOWN_PHASE_NAME = "not_a_real_phase"
HOOK_INFRASTRUCTURE_FILE_PATH = "/repo/packages/claude-dev-env/hooks/blocking/example.py"
_HOOK_MODULE_DUPLICATE_BODY_SOURCE = (
    "def compute_shipping_total(order_total: float, tax_rate: float) -> float:\n"
    "    taxed_total = order_total * (1 + tax_rate)\n"
    "    rounded_total = round(taxed_total, 2)\n"
    "    return rounded_total\n"
)


def test_all_validation_phases_holds_exactly_the_two_phases() -> None:
    assert validation_phase_constants.ALL_VALIDATION_PHASES == {
        validation_phase_constants.EDIT_LANE_PHASE,
        validation_phase_constants.FULL_GATE_PHASE,
    }


def test_unknown_phase_raises_value_error_naming_the_rejected_value() -> None:
    with pytest.raises(ValueError, match=UNKNOWN_PHASE_NAME):
        code_rules_enforcer.validate_content_for_phase(
            SAMPLE_PYTHON_CONTENT, PRODUCTION_FILE_PATH, phase=UNKNOWN_PHASE_NAME
        )


def test_validate_content_for_phase_requires_phase_keyword() -> None:
    with pytest.raises(TypeError):
        code_rules_enforcer.validate_content_for_phase(SAMPLE_PYTHON_CONTENT, PRODUCTION_FILE_PATH)


def _full_gate_only_default_kwargs() -> dict[str, object]:
    return {
        each_name: DEFAULT
        for each_name in validation_phase_constants.ALL_FULL_GATE_ONLY_CHECK_NAMES
    }


def _patched_full_gate_only_checks() -> contextlib.AbstractContextManager[dict[str, MagicMock]]:
    """Return the patch.multiple context manager for the six full-gate-only checks.

    ::

        mypy's patch.multiple stub only accepts an ``Any | str`` target, so a
        dynamically loaded ``ModuleType`` target needs a local type: ignore.
    """
    return patch.multiple(  # type: ignore[call-overload]  # mypy stub rejects ModuleType targets
        code_rules_enforcer, **_full_gate_only_default_kwargs()
    )


def _configure_full_gate_only_mock_returns(all_mocks: dict[str, MagicMock]) -> None:
    for each_name, each_mock in all_mocks.items():
        each_mock.return_value = None if each_name == "advise_cross_skill_duplicate_helper" else []


def test_edit_lane_calls_none_of_the_six_full_gate_only_checks() -> None:
    with _patched_full_gate_only_checks() as all_mocks:
        _configure_full_gate_only_mock_returns(all_mocks)
        code_rules_enforcer.validate_content_for_edit_lane(
            SAMPLE_PYTHON_CONTENT, PRODUCTION_FILE_PATH
        )
        for each_name, each_mock in all_mocks.items():
            assert each_mock.call_count == 0, f"edit lane must not call {each_name}"


def test_full_gate_calls_all_six_full_gate_only_checks() -> None:
    with _patched_full_gate_only_checks() as all_mocks:
        _configure_full_gate_only_mock_returns(all_mocks)
        code_rules_enforcer.validate_content_for_full_gate(
            SAMPLE_PYTHON_CONTENT, PRODUCTION_FILE_PATH
        )
        for each_name, each_mock in all_mocks.items():
            assert each_mock.call_count >= 1, f"full gate must call {each_name}"


def test_both_phases_report_identical_findings_with_the_six_spied_out() -> None:
    with _patched_full_gate_only_checks() as all_mocks:
        _configure_full_gate_only_mock_returns(all_mocks)
        edit_lane_issues = code_rules_enforcer.validate_content_for_edit_lane(
            SAMPLE_PYTHON_CONTENT, PRODUCTION_FILE_PATH
        )
        full_gate_issues = code_rules_enforcer.validate_content_for_full_gate(
            SAMPLE_PYTHON_CONTENT, PRODUCTION_FILE_PATH
        )
    assert edit_lane_issues == full_gate_issues


def test_no_caller_should_reach_a_phase_less_validator() -> None:
    assert not hasattr(code_rules_enforcer, "validate_content"), (
        "validate_content must not survive as a callable on the enforcer module"
    )
    enforcer_source = inspect.getsource(code_rules_enforcer)
    assert re.search(r"\bvalidate_content\(", enforcer_source) is None, (
        "no call site in code_rules_enforcer.py may reach a phase-less validator"
    )


def test_precheck_selects_the_full_gate() -> None:
    precheck_source = inspect.getsource(code_rules_enforcer._run_precheck)
    assert "validate_content_for_full_gate(" in precheck_source, (
        "the --check precheck must run the full-gate verdict"
    )


def test_codex_patch_issues_selects_the_edit_lane() -> None:
    """Pin the apply_patch mutation path to the edit-lane verdict."""
    codex_patch_issues_source = inspect.getsource(code_rules_enforcer._codex_patch_issues)
    assert "validate_content_for_edit_lane(" in codex_patch_issues_source, (
        "the apply_patch branch must run the edit-lane verdict"
    )


def test_forecast_full_file_violations_selects_the_edit_lane() -> None:
    """Pin the full-file forecast pass to the edit-lane verdict."""
    forecast_source = inspect.getsource(code_rules_enforcer._forecast_full_file_violations)
    assert "validate_content_for_edit_lane(" in forecast_source, (
        "the full-file forecast pass must run the edit-lane verdict"
    )


def test_report_blocking_violations_selects_the_edit_lane() -> None:
    """Pin the PreToolUse Write and Edit main path to the edit-lane verdict."""
    report_blocking_violations_source = inspect.getsource(
        code_rules_enforcer._report_blocking_violations
    )
    assert "validate_content_for_edit_lane(" in report_blocking_violations_source, (
        "the PreToolUse Write and Edit main path must run the edit-lane verdict"
    )


def _write_scoped_service_file_with_a_committed_baseline(repository_root: Path) -> Path:
    repo_test_helpers.init_repository(repository_root)
    return repo_test_helpers.write_commit_and_stage_change(
        repository_root,
        "service.py",
        "def read_port() -> int:\n    return 0\n",
        "def read_port() -> int:\n    port_number = 9999\n    return port_number\n",
    )


def test_hook_infrastructure_edit_lane_skips_the_cross_file_duplicate_check() -> None:
    with patch.object(
        code_rules_enforcer, "check_duplicate_function_body_across_files"
    ) as mock_check_duplicate_across_files:
        mock_check_duplicate_across_files.return_value = []
        code_rules_enforcer._hook_infrastructure_blocking_issues(
            SAMPLE_PYTHON_CONTENT,
            HOOK_INFRASTRUCTURE_FILE_PATH,
            phase=validation_phase_constants.EDIT_LANE_PHASE,
        )
    assert mock_check_duplicate_across_files.call_count == 0, (
        "the hook-infrastructure edit lane must not call the cross-file duplicate-body check"
    )


def test_hook_infrastructure_full_gate_calls_the_cross_file_duplicate_check() -> None:
    with patch.object(
        code_rules_enforcer, "check_duplicate_function_body_across_files"
    ) as mock_check_duplicate_across_files:
        mock_check_duplicate_across_files.return_value = []
        code_rules_enforcer._hook_infrastructure_blocking_issues(
            SAMPLE_PYTHON_CONTENT,
            HOOK_INFRASTRUCTURE_FILE_PATH,
            phase=validation_phase_constants.FULL_GATE_PHASE,
        )
    assert mock_check_duplicate_across_files.call_count == 1, (
        "the hook-infrastructure full gate must still call the cross-file duplicate-body check"
    )


def _write_duplicate_helper_pair_under_a_non_test_named_tempdir() -> tuple[Path, str]:
    """Write a hook-infra sibling pair under a ``tempfile.mkdtemp()`` root.

    ``tempfile.mkdtemp()`` names its directory ``tmp<random>``, carrying no
    ``test_`` segment, unlike pytest's own ``tmp_path`` fixture — whose
    directory embeds the test's name and so reads as a test path to
    ``is_test_file``'s full-path substring match, silently exempting every
    check the caller means to exercise.
    """
    base_directory = Path(tempfile.mkdtemp())
    hook_blocking_directory = base_directory / "packages" / "claude-dev-env" / "hooks" / "blocking"
    hook_blocking_directory.mkdir(parents=True)
    (hook_blocking_directory / "shipping_helper.py").write_text(
        _HOOK_MODULE_DUPLICATE_BODY_SOURCE, encoding="utf-8"
    )
    return base_directory, str(hook_blocking_directory / "shipping_target.py")


def test_full_gate_still_catches_a_helper_duplicated_across_two_hook_modules() -> None:
    base_directory, target_path = _write_duplicate_helper_pair_under_a_non_test_named_tempdir()
    try:
        full_gate_issues = code_rules_enforcer._hook_infrastructure_blocking_issues(
            _HOOK_MODULE_DUPLICATE_BODY_SOURCE,
            target_path,
            phase=validation_phase_constants.FULL_GATE_PHASE,
        )
        edit_lane_issues = code_rules_enforcer._hook_infrastructure_blocking_issues(
            _HOOK_MODULE_DUPLICATE_BODY_SOURCE,
            target_path,
            phase=validation_phase_constants.EDIT_LANE_PHASE,
        )
    finally:
        shutil.rmtree(base_directory, ignore_errors=False)

    assert any("duplicates" in each_issue for each_issue in full_gate_issues), (
        "the full gate must still catch a helper duplicated across two hook "
        f"modules, got: {full_gate_issues!r}"
    )
    assert not any("duplicates" in each_issue for each_issue in edit_lane_issues), (
        "the edit lane must not run the cross-file duplicate-body check against "
        f"hook infrastructure, got: {edit_lane_issues!r}"
    )


def test_gate_running_selects_the_full_gate(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    file_path = _write_scoped_service_file_with_a_committed_baseline(repository_root)

    loaded_validate_content = enforcer_loading.load_validate_content_for_full_gate()
    assert loaded_validate_content.__name__ == "validate_content_for_full_gate"

    scoped_violations = gate_running._scoped_violations_for_file(
        validate_content=loaded_validate_content,
        resolved_path=file_path,
        repository_root=repository_root,
        all_added_lines_for_file={2, 3},
        should_read_staged_content=True,
    )
    assert scoped_violations is not None
    blocking_violations, _advisory_violations = scoped_violations
    assert any("9999" in each_issue for each_issue in blocking_violations)
