"""Regression tests: staged validation resolves ruff config from the original path.

The PreToolUse gate stages proposed content to an OS-temp file, so ruff would
discover its config by walking up from that temp path and never reach
``packages/claude-dev-env/hooks/pyproject.toml``. Its ``[tool.ruff.lint]`` selects
B and PL, so a dropped config leaves the staged run less strict than the project.

``validate_proposed_file`` resolves the config from the ORIGINAL target path, so
the project ruff config applies to the staged copy from any working directory.

::

    original path .../validators/config_probe_module.py, DIRTY_SOURCE (assert False)
    flag (defect): staged temp copy -> no [tool.ruff] up-tree -> B011 not selected
    ok  (fixed):   config resolved from original path         -> B011 fires

    original path .../validators/test_config_probe_module.py, same DIRTY_SOURCE
    ok: the test_*.py per-file-ignore reaches the staged copy -> B011 suppressed
"""

from pathlib import Path

import pytest

from .run_all_validators import ValidatorResult, get_project_root, validate_proposed_file

VALIDATORS_DIRECTORY = Path(__file__).parent
NON_TEST_PROBE_PATH = VALIDATORS_DIRECTORY / "config_probe_module.py"
TEST_PROBE_PATH = VALIDATORS_DIRECTORY / "test_config_probe_module.py"

DIRTY_SOURCE = (
    "def probe_condition(observed_total: int) -> None:\n    assert False, observed_total\n"
)


def _ruff_result(all_results: list[ValidatorResult]) -> ValidatorResult:
    """Return the Ruff validator result from a validate_proposed_file run."""
    for each_result in all_results:
        if each_result.name == "Ruff":
            return each_result
    raise AssertionError("no Ruff validator result was produced")


def _working_directory_for(cwd_kind: str, outside_repo_directory: Path) -> Path:
    """Resolve the cwd a parametrized case runs from — repo root or outside it."""
    if cwd_kind == "repo_root":
        project_root = get_project_root()
        assert project_root is not None, "repo root must resolve for this test"
        return project_root
    return outside_repo_directory


@pytest.mark.parametrize("cwd_kind", ["repo_root", "outside_repo"])
def test_staged_non_test_file_reports_b011_from_every_cwd(
    cwd_kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(_working_directory_for(cwd_kind, tmp_path))

    ruff_result = _ruff_result(validate_proposed_file(str(NON_TEST_PROBE_PATH), DIRTY_SOURCE))

    assert "B011" in ruff_result.output


def test_staged_test_file_suppresses_b011_via_per_file_ignore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    non_test_ruff_result = _ruff_result(
        validate_proposed_file(str(NON_TEST_PROBE_PATH), DIRTY_SOURCE)
    )
    test_ruff_result = _ruff_result(validate_proposed_file(str(TEST_PROBE_PATH), DIRTY_SOURCE))

    assert "B011" in non_test_ruff_result.output
    assert "B011" not in test_ruff_result.output
