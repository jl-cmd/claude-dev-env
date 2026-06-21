"""Same-decision tests for hooks converted to the shared stdin parser.

Each converted hook reads its PreToolUse payload through
``hooks_constants.pre_tool_use_stdin.read_hook_input_dictionary_from_stdin``
rather than a hand-rolled ``json.load(sys.stdin)`` plus ``isinstance(dict)``
guard. The shared parser fails open on empty stdin, malformed JSON, and a
non-object JSON root by returning ``None``; the hand-rolled form these hooks
carried failed open on the same three cases by exiting zero. These tests drive
each real hook script through its production ``__main__`` stdin path over a
corpus that pins those fail-soft edges plus a representative allow payload, so a
conversion that changes any decision is caught.

The deterministic deny payloads for the two Write/Edit blockers whose triggers
need no filesystem or state setup (``md_to_html_blocker``,
``open_questions_in_plans_blocker``) are exercised here too; each remaining
hook's full deny coverage stays in its own suite, which also drives the real
``main()`` and so re-proves the decision after the parser swap.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent

ALL_CONVERTED_HOOK_FILENAMES = (
    "md_to_html_blocker.py",
    "open_questions_in_plans_blocker.py",
    "claude_md_orphan_file_blocker.py",
    "pr_converge_bugteam_enforcer.py",
    "verdict_directory_write_blocker.py",
    "package_inventory_stale_blocker.py",
)

EMPTY_STDIN_PAYLOAD = ""
WHITESPACE_STDIN_PAYLOAD = "   \n\t  "
MALFORMED_JSON_PAYLOAD = "{not valid json"
NON_OBJECT_JSON_ARRAY_PAYLOAD = "[1, 2, 3]"
NON_OBJECT_JSON_SCALAR_PAYLOAD = "42"

ALL_FAIL_SOFT_PAYLOADS = (
    EMPTY_STDIN_PAYLOAD,
    WHITESPACE_STDIN_PAYLOAD,
    MALFORMED_JSON_PAYLOAD,
    NON_OBJECT_JSON_ARRAY_PAYLOAD,
    NON_OBJECT_JSON_SCALAR_PAYLOAD,
)


def _run_hook_script(hook_filename: str, stdin_text: str) -> subprocess.CompletedProcess:
    hook_script_path = _BLOCKING_DIRECTORY / hook_filename
    return subprocess.run(
        [sys.executable, str(hook_script_path)],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(Path.home()),
    )


def _decision_from_stdout(completed: subprocess.CompletedProcess) -> str | None:
    if not completed.stdout.strip():
        return None
    parsed_output = json.loads(completed.stdout)
    return parsed_output["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize("hook_filename", ALL_CONVERTED_HOOK_FILENAMES)
@pytest.mark.parametrize("stdin_text", ALL_FAIL_SOFT_PAYLOADS)
def test_fail_soft_payload_exits_zero_with_no_decision(hook_filename: str, stdin_text: str) -> None:
    completed = _run_hook_script(hook_filename, stdin_text)
    assert completed.returncode == 0, (
        f"{hook_filename} must exit zero on fail-soft stdin; "
        f"got code {completed.returncode}, stderr {completed.stderr!r}"
    )
    assert _decision_from_stdout(completed) is None, (
        f"{hook_filename} must emit no decision on fail-soft stdin; got stdout {completed.stdout!r}"
    )


def test_md_to_html_blocker_still_denies_relative_markdown_write() -> None:
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "notes/topic.md", "content": "# Topic"},
        }
    )
    completed = _run_hook_script("md_to_html_blocker.py", payload)
    assert completed.returncode == 0
    assert _decision_from_stdout(completed) == "deny"


def test_md_to_html_blocker_still_allows_non_markdown_write() -> None:
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "notes/topic.txt", "content": "plain"},
        }
    )
    completed = _run_hook_script("md_to_html_blocker.py", payload)
    assert completed.returncode == 0
    assert _decision_from_stdout(completed) is None


def test_open_questions_blocker_still_denies_plan_with_open_questions(
    tmp_path: Path,
) -> None:
    plan_directory = tmp_path / "docs" / "plans"
    plan_directory.mkdir(parents=True)
    plan_path = plan_directory / "feature.md"
    plan_body = "# Feature Plan\n\n## Open Questions\n\n- What endpoint do we call?\n"
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(plan_path), "content": plan_body},
        }
    )
    completed = _run_hook_script("open_questions_in_plans_blocker.py", payload)
    assert completed.returncode == 0
    assert _decision_from_stdout(completed) == "deny"


def test_open_questions_blocker_still_allows_plan_without_open_questions(
    tmp_path: Path,
) -> None:
    plan_directory = tmp_path / "docs" / "plans"
    plan_directory.mkdir(parents=True)
    plan_path = plan_directory / "feature.md"
    plan_body = "# Feature Plan\n\n## Approach\n\nBuild the thing.\n"
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(plan_path), "content": plan_body},
        }
    )
    completed = _run_hook_script("open_questions_in_plans_blocker.py", payload)
    assert completed.returncode == 0
    assert _decision_from_stdout(completed) is None


def test_package_inventory_blocker_still_denies_uninventoried_new_file(
    tmp_path: Path,
) -> None:
    inventory_body = "# package\n\n| File | Role |\n|---|---|\n| `alpha.py` | A |\n| `beta.py` | B |\n"
    (tmp_path / "README.md").write_text(inventory_body, encoding="utf-8")
    new_file_path = tmp_path / "gamma.py"
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(new_file_path), "content": "x = 1\n"},
        }
    )
    completed = _run_hook_script("package_inventory_stale_blocker.py", payload)
    assert completed.returncode == 0
    assert _decision_from_stdout(completed) == "deny"


def test_package_inventory_blocker_still_allows_inventoried_new_file(
    tmp_path: Path,
) -> None:
    inventory_body = "# package\n\n| File | Role |\n|---|---|\n| `alpha.py` | A |\n| `gamma.py` | G |\n"
    (tmp_path / "README.md").write_text(inventory_body, encoding="utf-8")
    new_file_path = tmp_path / "gamma.py"
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(new_file_path), "content": "x = 1\n"},
        }
    )
    completed = _run_hook_script("package_inventory_stale_blocker.py", payload)
    assert completed.returncode == 0
    assert _decision_from_stdout(completed) is None


def test_converted_hooks_allow_unrelated_tool_name() -> None:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    for each_hook_filename in ALL_CONVERTED_HOOK_FILENAMES:
        completed = _run_hook_script(each_hook_filename, payload)
        assert completed.returncode == 0, (
            f"{each_hook_filename} must exit zero on an unrelated tool; stderr {completed.stderr!r}"
        )


def test_every_converted_hook_imports_shared_parser() -> None:
    for each_hook_filename in ALL_CONVERTED_HOOK_FILENAMES:
        hook_source = (_BLOCKING_DIRECTORY / each_hook_filename).read_text(encoding="utf-8")
        assert "read_hook_input_dictionary_from_stdin" in hook_source, (
            f"{each_hook_filename} must read stdin through the shared parser"
        )
        assert "json.load(sys.stdin)" not in hook_source, (
            f"{each_hook_filename} must not hand-roll json.load(sys.stdin)"
        )


def test_blocking_directory_is_resolvable() -> None:
    assert os.path.isdir(_BLOCKING_DIRECTORY)
