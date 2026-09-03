"""Tests for fast_save_validators.py -- the in-process save-path validator roster."""

import tempfile
from pathlib import Path

import pytest

from .fast_save_validators import run_fast_save_validators
from .magic_value_checks import validate_file as read_magic_literal_violations
from .react_checks import check_no_class_components
from .test_safety_checks import check_no_skip_decorators

MAGIC_LITERAL_SOURCE = "def compute_total(unit_price: int) -> int:\n    return unit_price * 199\n"
_UNTRACKED_TODO_MARKER = "#" + " TODO"
TODO_SOURCE = f"{_UNTRACKED_TODO_MARKER}: revisit this\ndef clean() -> None:\n    return None\n"
REACT_CLASS_COMPONENT_SOURCE = "class Widget extends Component {\n  render() { return null; }\n}\n"
TEST_SKIP_DECORATOR_SOURCE = (
    "import pytest\n\n\n@pytest.mark.skip\ndef test_something() -> None:\n    pass\n"
)

_ALL_EXPECTED_FAST_SAVE_VALIDATOR_NAMES = frozenset(
    {
        "Python Style",
        "Abbreviations",
        "Magic Values",
        "Security",
        "Code Quality",
        "Python Anti-patterns",
        "Type Safety",
        "Test Safety",
        "Useless Tests",
        "React",
        "PR References",
    }
)


def test_run_fast_save_validators_covers_every_non_mypy_non_ruff_check(
    tmp_path: Path,
) -> None:
    target_file = tmp_path / "legacy_module.py"
    target_file.write_text(MAGIC_LITERAL_SOURCE, encoding="utf-8")

    all_outcomes = run_fast_save_validators([target_file])

    assert {each_outcome.name for each_outcome in all_outcomes} == (
        _ALL_EXPECTED_FAST_SAVE_VALIDATOR_NAMES
    )


def test_run_fast_save_validators_excludes_mypy_and_ruff(tmp_path: Path) -> None:
    target_file = tmp_path / "legacy_module.py"
    target_file.write_text(MAGIC_LITERAL_SOURCE, encoding="utf-8")

    all_outcomes = run_fast_save_validators([target_file])

    assert all(each_outcome.name != "Mypy" for each_outcome in all_outcomes)
    assert all(each_outcome.name != "Ruff" for each_outcome in all_outcomes)


def test_run_fast_save_validators_spawns_no_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_file = tmp_path / "legacy_module.py"
    target_file.write_text(MAGIC_LITERAL_SOURCE, encoding="utf-8")

    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("run_fast_save_validators must not spawn a subprocess")

    monkeypatch.setattr("subprocess.run", _fail_if_called)

    run_fast_save_validators([target_file])


def test_magic_values_outcome_matches_direct_validate_file_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A directory with no "test_"-patterned segment: magic_value_checks exempts
    # any path under one, which pytest's own tmp_path always carries (tmp_path
    # names itself "test_<function name><N>"). tmp_path's own parent carries no
    # such segment. Routing TMPDIR there through monkeypatch, and also passing
    # it as TemporaryDirectory's own ``dir``, keeps the probe from depending on
    # whatever the real process environment happens to hold.
    isolated_root = tmp_path.parent
    monkeypatch.setenv("TMPDIR", str(isolated_root))
    with tempfile.TemporaryDirectory(
        dir=str(isolated_root), prefix="fast_save_probe_"
    ) as workspace_name:
        target_file = Path(workspace_name) / "legacy_module.py"
        target_file.write_text(MAGIC_LITERAL_SOURCE, encoding="utf-8")
        expected_lines = [
            str(each) for each in read_magic_literal_violations(target_file)
        ]
        assert expected_lines != []

        all_outcomes = run_fast_save_validators([target_file])

    magic_values_outcome = next(
        each for each in all_outcomes if each.name == "Magic Values"
    )
    assert magic_values_outcome.output == "\n".join(expected_lines)


def test_todo_comments_do_not_run_on_save_path(tmp_path: Path) -> None:
    target_file = tmp_path / "legacy_module.py"
    target_file.write_text(TODO_SOURCE, encoding="utf-8")
    all_outcomes = run_fast_save_validators([target_file])

    assert all(each.name != "TODO Tracking" for each in all_outcomes)


def test_abbreviations_outcome_reports_clean_for_a_clean_file(tmp_path: Path) -> None:
    target_file = tmp_path / "legacy_module.py"
    target_file.write_text(
        "def add_two_numbers(first: int, second: int) -> int:\n    return first + second\n",
        encoding="utf-8",
    )

    all_outcomes = run_fast_save_validators([target_file])

    abbreviations_outcome = next(
        each for each in all_outcomes if each.name == "Abbreviations"
    )
    assert abbreviations_outcome.passed is True


def test_react_outcome_matches_direct_check_function_call(tmp_path: Path) -> None:
    target_file = tmp_path / "widget.tsx"
    target_file.write_text(REACT_CLASS_COMPONENT_SOURCE, encoding="utf-8")
    expected_violations = check_no_class_components([str(target_file)])
    expected_lines = [f"{each.file}:{each.line}: {each.message}" for each in expected_violations]
    assert expected_lines != []

    all_outcomes = run_fast_save_validators([target_file])

    react_outcome = next(each for each in all_outcomes if each.name == "React")
    assert react_outcome.output == "\n".join(expected_lines)


def test_test_safety_outcome_matches_direct_check_function_calls(
    tmp_path: Path,
) -> None:
    target_file = tmp_path / "test_something.py"
    target_file.write_text(TEST_SKIP_DECORATOR_SOURCE, encoding="utf-8")
    code = target_file.read_text(encoding="utf-8")
    expected_violations = check_no_skip_decorators(code, str(target_file))
    expected_lines = [str(each) for each in expected_violations]
    assert expected_lines != []

    all_outcomes = run_fast_save_validators([target_file])

    test_safety_outcome = next(each for each in all_outcomes if each.name == "Test Safety")
    assert test_safety_outcome.output == "\n".join(expected_lines)


def test_no_matching_files_reports_configured_message(tmp_path: Path) -> None:
    target_file = tmp_path / "widget.tsx"
    target_file.write_text("export const Widget = () => null;\n", encoding="utf-8")

    all_outcomes = run_fast_save_validators([target_file])

    abbreviations_outcome = next(
        each for each in all_outcomes if each.name == "Abbreviations"
    )
    assert abbreviations_outcome.passed is True
    assert abbreviations_outcome.output == "No Python files to check"
