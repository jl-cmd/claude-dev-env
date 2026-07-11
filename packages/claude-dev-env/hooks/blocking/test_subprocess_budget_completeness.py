"""Unit tests for the subprocess_budget_completeness PreToolUse hook."""

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
from collections.abc import Iterator

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "subprocess_budget_completeness",
    _HOOK_DIR / "subprocess_budget_completeness.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

find_undercounted_budget = hook_module.find_undercounted_budget
format_block_message = hook_module.format_block_message
resolved_content = hook_module.resolved_content


@pytest.fixture
def production_module_path() -> Iterator[pathlib.Path]:
    with tempfile.TemporaryDirectory(prefix="budget_completeness_") as production_dir:
        yield pathlib.Path(production_dir) / "timing_module.py"

_BUDGET_FLAGS_GIT_TIMEOUT_OMISSION = """
import subprocess

PYTHON_FORMAT_TIMEOUT_SECONDS = 12


def worst_case_python_format_seconds() -> int:
    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    return fix_phase_seconds + format_phase_seconds


def is_untracked_in_git(file_path: str) -> bool:
    git_check = subprocess.run(["git", "ls-files", file_path], timeout=5)
    return git_check.returncode != 0


def run_format(file_path: str) -> None:
    subprocess.run(["ruff", "format", file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)


def main(file_path: str) -> None:
    if is_untracked_in_git(file_path):
        return
    run_format(file_path)
"""

_BUDGET_COUNTS_EVERY_TIMEOUT = """
import subprocess

PYTHON_FORMAT_TIMEOUT_SECONDS = 12
GIT_CHECK_TIMEOUT_SECONDS = 5


def worst_case_python_format_seconds() -> int:
    git_check_seconds = GIT_CHECK_TIMEOUT_SECONDS
    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    return git_check_seconds + fix_phase_seconds + format_phase_seconds


def is_untracked_in_git(file_path: str) -> bool:
    git_check = subprocess.run(["git", "ls-files", file_path], timeout=GIT_CHECK_TIMEOUT_SECONDS)
    return git_check.returncode != 0


def run_format(file_path: str) -> None:
    subprocess.run(["ruff", "format", file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)


def main(file_path: str) -> None:
    if is_untracked_in_git(file_path):
        return
    run_format(file_path)
"""

_NO_BUDGET_FUNCTION = """
import subprocess


def is_untracked_in_git(file_path: str) -> bool:
    git_check = subprocess.run(["git", "ls-files", file_path], timeout=5)
    return git_check.returncode != 0
"""

_BUDGET_OMITS_A_NAMED_CONSTANT_TIMEOUT = """
import subprocess

PYTHON_FORMAT_TIMEOUT_SECONDS = 12
GIT_CHECK_TIMEOUT_SECONDS = 5


def worst_case_python_format_seconds() -> int:
    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    return fix_phase_seconds + format_phase_seconds


def is_untracked_in_git(file_path: str) -> bool:
    git_check = subprocess.run(["git", "ls-files", file_path], timeout=GIT_CHECK_TIMEOUT_SECONDS)
    return git_check.returncode != 0


def run_format(file_path: str) -> None:
    subprocess.run(["ruff", "format", file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)


def main(file_path: str) -> None:
    if is_untracked_in_git(file_path):
        return
    run_format(file_path)
"""

_BUDGET_COUNTS_VIA_ANNOTATED_CONSTANTS = """
import subprocess

PYTHON_FORMAT_TIMEOUT_SECONDS: int = 12
GIT_CHECK_TIMEOUT_SECONDS: int = 5


def worst_case_python_format_seconds() -> int:
    git_check_seconds = GIT_CHECK_TIMEOUT_SECONDS
    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    return git_check_seconds + fix_phase_seconds + format_phase_seconds


def is_untracked_in_git(file_path: str) -> bool:
    git_check = subprocess.run(["git", "ls-files", file_path], timeout=5)
    return git_check.returncode != 0


def run_format(file_path: str) -> None:
    subprocess.run(["ruff", "format", file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)


def main(file_path: str) -> None:
    if is_untracked_in_git(file_path):
        return
    run_format(file_path)
"""

_BUDGET_PLUS_UNREACHABLE_NETWORK_PROBE = """
import subprocess

PYTHON_FORMAT_TIMEOUT_SECONDS = 12


def worst_case_format_phase_seconds() -> int:
    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    return fix_phase_seconds + format_phase_seconds


def run_format(file_path: str) -> None:
    subprocess.run(["ruff", "format", file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)


def unrelated_network_probe() -> int:
    completed_probe = subprocess.run(["curl", "https://example.test"], timeout=30)
    return completed_probe.returncode


def main(file_path: str) -> None:
    run_format(file_path)
"""

_INTERIOR_BUDGET_SUBSTRING_NOT_A_TOTAL = """
import subprocess


def audit_budget_report() -> int:
    return run_auditor()


def run_auditor() -> int:
    completed_audit = subprocess.run(["auditor"], timeout=30)
    return completed_audit.returncode


def main() -> int:
    return audit_budget_report()
"""


_ASYNC_BUDGET_OMITS_ASYNC_WRAPPER_TIMEOUT = """
import subprocess

PYTHON_FORMAT_TIMEOUT_SECONDS = 12


def worst_case_python_format_seconds() -> int:
    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    return fix_phase_seconds + format_phase_seconds


async def is_untracked_in_git(file_path: str) -> bool:
    git_check = subprocess.run(["git", "ls-files", file_path], timeout=5)
    return git_check.returncode != 0


def run_format(file_path: str) -> None:
    subprocess.run(["ruff", "format", file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)


async def main(file_path: str) -> None:
    if await is_untracked_in_git(file_path):
        return
    run_format(file_path)
"""

_ASYNC_BUDGET_HELPER_OMITS_A_TIMEOUT = """
import subprocess


def run_auditor() -> int:
    completed_audit = subprocess.run(["auditor"], timeout=30)
    return completed_audit.returncode


async def worst_case_seconds() -> int:
    return 5


def main() -> int:
    return run_auditor()
"""

_ASYNC_MAIN_NARROWS_REACHABLE_SET = """
import subprocess

PYTHON_FORMAT_TIMEOUT_SECONDS = 12


def worst_case_format_phase_seconds() -> int:
    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    return fix_phase_seconds + format_phase_seconds


def run_format(file_path: str) -> None:
    subprocess.run(["ruff", "format", file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)


def unrelated_network_probe() -> int:
    completed_probe = subprocess.run(["curl", "https://example.test"], timeout=30)
    return completed_probe.returncode


async def main(file_path: str) -> None:
    run_format(file_path)
"""


def test_flags_async_subprocess_wrapper_that_omits_a_reachable_timeout() -> None:
    undercounted_budget = find_undercounted_budget(_ASYNC_BUDGET_OMITS_ASYNC_WRAPPER_TIMEOUT)
    assert undercounted_budget is not None
    function_name, omitted_values = undercounted_budget
    assert function_name == "worst_case_python_format_seconds"
    assert omitted_values == {5}


def test_flags_async_budget_helper_that_omits_a_reachable_timeout() -> None:
    undercounted_budget = find_undercounted_budget(_ASYNC_BUDGET_HELPER_OMITS_A_TIMEOUT)
    assert undercounted_budget is not None
    function_name, omitted_values = undercounted_budget
    assert function_name == "worst_case_seconds"
    assert omitted_values == {30}


def test_async_main_narrows_the_reachable_set() -> None:
    assert find_undercounted_budget(_ASYNC_MAIN_NARROWS_REACHABLE_SET) is None


def test_block_message_appends_the_seconds_unit_to_every_omitted_value() -> None:
    block_message = format_block_message("module.py", "worst_case_seconds", {5, 12, 30})
    assert "5s, 12s, 30s" in block_message


def test_flags_budget_helper_that_omits_a_reachable_subprocess_timeout() -> None:
    undercounted_budget = find_undercounted_budget(_BUDGET_FLAGS_GIT_TIMEOUT_OMISSION)
    assert undercounted_budget is not None
    function_name, omitted_literals = undercounted_budget
    assert function_name == "worst_case_python_format_seconds"
    assert omitted_literals == {5}


def test_passes_budget_helper_that_counts_every_subprocess_timeout() -> None:
    assert find_undercounted_budget(_BUDGET_COUNTS_EVERY_TIMEOUT) is None


def test_passes_module_without_a_budget_function() -> None:
    assert find_undercounted_budget(_NO_BUDGET_FUNCTION) is None


def test_passes_module_with_no_subprocess_calls() -> None:
    only_a_budget_function = "def worst_case_seconds() -> int:\n    return 5 + 12\n"
    assert find_undercounted_budget(only_a_budget_function) is None


def test_flags_budget_that_omits_a_named_constant_subprocess_timeout() -> None:
    undercounted_budget = find_undercounted_budget(_BUDGET_OMITS_A_NAMED_CONSTANT_TIMEOUT)
    assert undercounted_budget is not None
    function_name, omitted_values = undercounted_budget
    assert function_name == "worst_case_python_format_seconds"
    assert omitted_values == {5}


def test_passes_budget_that_accounts_via_annotated_module_constants() -> None:
    assert find_undercounted_budget(_BUDGET_COUNTS_VIA_ANNOTATED_CONSTANTS) is None


def test_passes_budget_with_unreachable_unrelated_subprocess_probe() -> None:
    assert find_undercounted_budget(_BUDGET_PLUS_UNREACHABLE_NETWORK_PROBE) is None


def test_ignores_function_whose_name_merely_contains_the_budget_substring() -> None:
    assert find_undercounted_budget(_INTERIOR_BUDGET_SUBSTRING_NOT_A_TOTAL) is None


_STRAY_LITERAL_EQUAL_TO_OMITTED_TIMEOUT = """
import subprocess


def worst_case_seconds() -> int:
    retry_attempts = 5
    fix_phase_seconds = 12
    format_phase_seconds = 12
    if retry_attempts < 0:
        return 0
    return fix_phase_seconds + format_phase_seconds


def is_untracked_in_git(file_path: str) -> bool:
    git_check = subprocess.run(["git", "ls-files", file_path], timeout=5)
    return git_check.returncode != 0


def main(file_path: str) -> bool:
    return is_untracked_in_git(file_path)
"""


def test_flags_when_a_stray_literal_equals_the_omitted_subprocess_timeout() -> None:
    undercounted_budget = find_undercounted_budget(_STRAY_LITERAL_EQUAL_TO_OMITTED_TIMEOUT)
    assert undercounted_budget is not None
    function_name, omitted_values = undercounted_budget
    assert function_name == "worst_case_seconds"
    assert omitted_values == {5}


_BARE_RUN_IMPORT_OMITS_A_REACHABLE_TIMEOUT = """
from subprocess import run

PYTHON_FORMAT_TIMEOUT_SECONDS = 12


def worst_case_seconds() -> int:
    return PYTHON_FORMAT_TIMEOUT_SECONDS


def run_format(file_path: str) -> None:
    run(["ruff", "format", file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)


def probe() -> int:
    completed_probe = run(["curl", "https://example.test"], timeout=99)
    return completed_probe.returncode


def main(file_path: str) -> int:
    run_format(file_path)
    return probe()
"""


def test_flags_bare_run_call_from_subprocess_import_run() -> None:
    undercounted_budget = find_undercounted_budget(_BARE_RUN_IMPORT_OMITS_A_REACHABLE_TIMEOUT)
    assert undercounted_budget is not None
    function_name, omitted_values = undercounted_budget
    assert function_name == "worst_case_seconds"
    assert omitted_values == {99}


def test_resolved_content_reconstructs_the_full_file_for_an_edit(
    tmp_path: pathlib.Path,
) -> None:
    edited_module_path = tmp_path / "timing_module.py"
    old_helper_body = '    git_check = subprocess.run(["git", "ls-files", file_path])\n'
    new_helper_body = '    git_check = subprocess.run(["git", "ls-files", file_path], timeout=45)\n'
    edited_module_path.write_text(
        _BUDGET_COUNTS_EVERY_TIMEOUT.replace(
            '    git_check = subprocess.run(["git", "ls-files", file_path],'
            " timeout=GIT_CHECK_TIMEOUT_SECONDS)\n",
            old_helper_body,
        ),
        encoding="utf-8",
    )
    reconstructed_content = resolved_content(
        {
            "file_path": str(edited_module_path),
            "old_string": old_helper_body,
            "new_string": new_helper_body,
        }
    )
    assert "timeout=45" in reconstructed_content
    assert "def worst_case_python_format_seconds" in reconstructed_content


def test_edit_flags_new_timeout_added_to_a_non_budget_helper(tmp_path: pathlib.Path) -> None:
    edited_module_path = tmp_path / "timing_module.py"
    edited_module_path.write_text(_BUDGET_COUNTS_EVERY_TIMEOUT, encoding="utf-8")
    old_helper_line = (
        '    git_check = subprocess.run(["git", "ls-files", file_path],'
        " timeout=GIT_CHECK_TIMEOUT_SECONDS)\n"
    )
    new_helper_line = (
        '    git_check = subprocess.run(["git", "ls-files", file_path], timeout=45)\n'
    )
    reconstructed_content = resolved_content(
        {
            "file_path": str(edited_module_path),
            "old_string": old_helper_line,
            "new_string": new_helper_line,
        }
    )
    undercounted_budget = find_undercounted_budget(reconstructed_content)
    assert undercounted_budget is not None
    function_name, omitted_values = undercounted_budget
    assert function_name == "worst_case_python_format_seconds"
    assert omitted_values == {45}


def test_edit_passes_single_helper_when_full_file_budget_is_complete(
    tmp_path: pathlib.Path,
) -> None:
    edited_module_path = tmp_path / "timing_module.py"
    edited_module_path.write_text(_BUDGET_COUNTS_EVERY_TIMEOUT, encoding="utf-8")
    old_helper_line = '    return git_check.returncode != 0\n'
    new_helper_line = '    return git_check.returncode != 0  # checked\n'
    reconstructed_content = resolved_content(
        {
            "file_path": str(edited_module_path),
            "old_string": old_helper_line,
            "new_string": new_helper_line,
        }
    )
    assert find_undercounted_budget(reconstructed_content) is None


def test_resolved_content_returns_empty_when_edit_old_string_is_absent(
    tmp_path: pathlib.Path,
) -> None:
    edited_module_path = tmp_path / "timing_module.py"
    edited_module_path.write_text(_BUDGET_COUNTS_EVERY_TIMEOUT, encoding="utf-8")
    reconstructed_content = resolved_content(
        {
            "file_path": str(edited_module_path),
            "old_string": "no such line in the file\n",
            "new_string": "replacement\n",
        }
    )
    assert reconstructed_content == ""


def _run_hook_on_content(content: str) -> subprocess.CompletedProcess[str]:
    hook_input = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "packages/example/timing_module.py", "content": content},
        }
    )
    return subprocess.run(
        [sys.executable, str(_HOOK_DIR / "subprocess_budget_completeness.py")],
        input=hook_input,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_full_hook_denies_write_with_undercounted_budget() -> None:
    completed_hook = _run_hook_on_content(_BUDGET_FLAGS_GIT_TIMEOUT_OMISSION)
    assert completed_hook.returncode == 0
    hook_output = json.loads(completed_hook.stdout)
    decision = hook_output["hookSpecificOutput"]["permissionDecision"]
    assert decision == "deny"
    assert "5s" in hook_output["hookSpecificOutput"]["permissionDecisionReason"]


def test_full_hook_allows_write_with_complete_budget() -> None:
    completed_hook = _run_hook_on_content(_BUDGET_COUNTS_EVERY_TIMEOUT)
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_full_hook_ignores_a_non_string_file_path() -> None:
    hook_input = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": 5, "content": _BUDGET_FLAGS_GIT_TIMEOUT_OMISSION},
        }
    )
    completed_hook = subprocess.run(
        [sys.executable, str(_HOOK_DIR / "subprocess_budget_completeness.py")],
        input=hook_input,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_full_hook_exempts_test_files_from_the_budget_gate() -> None:
    hook_input = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "packages/example/test_timing_module.py",
                "content": _BUDGET_FLAGS_GIT_TIMEOUT_OMISSION,
            },
        }
    )
    completed_hook = subprocess.run(
        [sys.executable, str(_HOOK_DIR / "subprocess_budget_completeness.py")],
        input=hook_input,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_full_hook_denies_edit_that_adds_a_timeout_to_a_non_budget_helper(
    production_module_path: pathlib.Path,
) -> None:
    edited_module_path = production_module_path
    edited_module_path.write_text(_BUDGET_COUNTS_EVERY_TIMEOUT, encoding="utf-8")
    old_helper_line = (
        '    git_check = subprocess.run(["git", "ls-files", file_path],'
        " timeout=GIT_CHECK_TIMEOUT_SECONDS)\n"
    )
    new_helper_line = (
        '    git_check = subprocess.run(["git", "ls-files", file_path], timeout=45)\n'
    )
    hook_input = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(edited_module_path),
                "old_string": old_helper_line,
                "new_string": new_helper_line,
            },
        }
    )
    completed_hook = subprocess.run(
        [sys.executable, str(_HOOK_DIR / "subprocess_budget_completeness.py")],
        input=hook_input,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed_hook.returncode == 0
    hook_output = json.loads(completed_hook.stdout)
    assert hook_output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "45s" in hook_output["hookSpecificOutput"]["permissionDecisionReason"]
