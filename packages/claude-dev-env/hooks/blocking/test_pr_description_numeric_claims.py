"""Unit tests for the PR-body numeric-claim accuracy check."""

import json
import pathlib
import subprocess
import sys

try:
    from blocking.pr_description_numeric_claims import (
        discover_repository_root,
        find_inaccurate_numeric_claims,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from blocking.pr_description_numeric_claims import (
        discover_repository_root,
        find_inaccurate_numeric_claims,
    )


def test_hook_denies_a_gh_pr_create_carrying_a_wrong_test_count(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".git").mkdir()
    suite_directory = tmp_path / "suite"
    suite_directory.mkdir()
    (suite_directory / "test_only.py").write_text(
        "def test_a():\n    assert True\n", encoding="utf-8"
    )
    command = 'gh pr create --title x --body "the suite/ directory holds 7 unit tests"'
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    module_path = pathlib.Path(__file__).parent / "pr_description_numeric_claims.py"
    completed = subprocess.run(
        [sys.executable, str(module_path)],
        input=payload,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert "permissionDecision" in completed.stdout
    assert "deny" in completed.stdout
    assert "7 test" in completed.stdout


def _write_lines(target_path: pathlib.Path, line_count: int) -> None:
    target_path.write_text(
        "".join(f"content_line_{each_index}\n" for each_index in range(line_count)),
        encoding="utf-8",
    )


def _build_tests_directory(repo_root: pathlib.Path, test_function_count: int) -> pathlib.Path:
    tests_directory = repo_root / "packages" / "hooks" / "blocking" / "tdd_enforcer_parts" / "tests"
    tests_directory.mkdir(parents=True)
    body = "".join(
        f"def test_case_{each_index}():\n    assert True\n\n"
        for each_index in range(test_function_count)
    )
    (tests_directory / "test_sample.py").write_text(body, encoding="utf-8")
    return tests_directory


def test_flags_test_count_claim_that_undercounts_the_directory(tmp_path: pathlib.Path) -> None:
    _build_tests_directory(tmp_path, test_function_count=4)
    body = "The `tdd_enforcer_parts/tests/` directory holds 3 unit tests over the modules."

    violations = find_inaccurate_numeric_claims(body, tmp_path)

    assert len(violations) == 1
    assert "test" in violations[0]
    assert "4" in violations[0]


def test_accepts_test_count_claim_that_matches_the_directory(tmp_path: pathlib.Path) -> None:
    _build_tests_directory(tmp_path, test_function_count=4)
    body = "The `tdd_enforcer_parts/tests/` directory holds 4 unit tests over the modules."

    assert find_inaccurate_numeric_claims(body, tmp_path) == []


def test_flags_line_count_claim_matching_no_measurable_state(tmp_path: pathlib.Path) -> None:
    module_path = tmp_path / "packages" / "hooks" / "blocking" / "sample_hook.py"
    module_path.parent.mkdir(parents=True)
    _write_lines(module_path, line_count=10)
    body = "Decomposes the 643-line `blocking/sample_hook.py` into helpers."

    violations = find_inaccurate_numeric_claims(body, tmp_path)

    assert len(violations) == 1
    assert "643" in violations[0]


def test_accepts_line_count_claim_matching_the_working_tree(tmp_path: pathlib.Path) -> None:
    module_path = tmp_path / "packages" / "hooks" / "blocking" / "sample_hook.py"
    module_path.parent.mkdir(parents=True)
    _write_lines(module_path, line_count=10)
    body = "Decomposes the 10-line `blocking/sample_hook.py` into helpers."

    assert find_inaccurate_numeric_claims(body, tmp_path) == []


def test_ignores_a_claim_whose_path_does_not_resolve(tmp_path: pathlib.Path) -> None:
    _build_tests_directory(tmp_path, test_function_count=4)
    body = "This branch touches 9 unit tests in `absent/place/` somewhere."

    assert find_inaccurate_numeric_claims(body, tmp_path) == []


def test_returns_empty_for_a_body_without_numeric_claims(tmp_path: pathlib.Path) -> None:
    _build_tests_directory(tmp_path, test_function_count=4)
    body = "Adds a guard clause and tidies the naming in the submission processor."

    assert find_inaccurate_numeric_claims(body, tmp_path) == []


def test_discover_repository_root_walks_up_to_the_git_ancestor(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".git").mkdir()
    nested_directory = tmp_path / "packages" / "hooks"
    nested_directory.mkdir(parents=True)

    assert discover_repository_root(nested_directory) == tmp_path
