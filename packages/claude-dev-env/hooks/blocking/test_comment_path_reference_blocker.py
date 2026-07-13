"""Behavioral tests for the comment path-reference blocker.

Each test builds a small on-disk repository fixture — a ``.git`` marker, a
``shared_utils`` package holding the real test file under ``config/tests``, and a
workflow file whose comment cites collection paths — then drives the production
functions against it, so the check runs over a real directory tree rather than a
stubbed one.
"""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
blocker = importlib.import_module("blocking.comment_path_reference_blocker")

WORKFLOW_RELATIVE_PATH = ".github/workflows/shared-utils-tests.yml"
COLLECTION_COMMENT = (
    "# +64 mailbox-loader change: config/tests/test_mailboxes.py (6) and\n"
    "# tests/test_samsung_sheets.py (58) collected via the testpaths entry.\n"
)


def _build_repository(root_directory: Path, comment_block: str) -> Path:
    """Create a repository fixture and return its workflow file path.

    Args:
        root_directory: The empty directory the fixture is built inside.
        comment_block: The comment lines placed above the workflow job step.

    Returns:
        The path of the workflow file the comment block sits in.
    """
    (root_directory / ".git").mkdir()
    sheets_test_directory = root_directory / "shared_utils" / "config" / "tests"
    sheets_test_directory.mkdir(parents=True)
    (sheets_test_directory / "test_samsung_sheets.py").write_text(
        "def test_x() -> None:\n    assert True\n"
    )
    (sheets_test_directory / "test_mailboxes.py").write_text(
        "def test_y() -> None:\n    assert True\n"
    )
    (root_directory / "shared_utils" / "tests").mkdir(parents=True)
    workflow_file = root_directory / WORKFLOW_RELATIVE_PATH
    workflow_file.parent.mkdir(parents=True)
    workflow_file.write_text(
        comment_block
        + "      - name: Collect\n        working-directory: shared_utils\n        run: pytest\n"
    )
    return workflow_file


def test_flags_path_resolving_nowhere_that_names_a_real_file(tmp_path: Path) -> None:
    """A comment path that resolves nowhere yet names a real file is flagged."""
    workflow_file = _build_repository(tmp_path, COLLECTION_COMMENT)
    findings = blocker.find_unresolved_paths(workflow_file.read_text(), workflow_file.parent)
    assert findings == ["tests/test_samsung_sheets.py"]


def test_accepts_path_that_resolves_under_the_working_directory(tmp_path: Path) -> None:
    """A comment path that resolves under the job working-directory is accepted."""
    corrected_comment = COLLECTION_COMMENT.replace(
        "tests/test_samsung_sheets.py", "config/tests/test_samsung_sheets.py"
    )
    workflow_file = _build_repository(tmp_path, corrected_comment)
    findings = blocker.find_unresolved_paths(workflow_file.read_text(), workflow_file.parent)
    assert findings == []


def test_ignores_path_whose_basename_exists_nowhere(tmp_path: Path) -> None:
    """A comment path whose filename exists nowhere in the tree is left alone."""
    absent_comment = "# see docs/never/made_this_up.py for the mapping\n"
    workflow_file = _build_repository(tmp_path, absent_comment)
    findings = blocker.find_unresolved_paths(workflow_file.read_text(), workflow_file.parent)
    assert findings == []


def test_is_workflow_file_matches_only_workflow_yaml() -> None:
    """The scope predicate accepts workflow YAML and rejects other paths."""
    assert blocker.is_workflow_file("repo/.github/workflows/ci.yml") is True
    assert blocker.is_workflow_file("repo/.github/workflows/ci.yaml") is True
    assert (
        blocker.is_workflow_file("repo/shared_utils/config/tests/test_samsung_sheets.py") is False
    )
    assert blocker.is_workflow_file("repo/docs/notes.md") is False


def _run_main_capturing_decision(payload: dict) -> str:
    """Run the hook main with a simulated stdin payload and return its stdout.

    Args:
        payload: The PreToolUse payload to feed the hook on stdin.

    Returns:
        The text the hook wrote to stdout, empty when it emitted no decision.
    """
    saved_stdin, saved_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps(payload))
    captured_output = io.StringIO()
    sys.stdout = captured_output
    try:
        blocker.main()
    except SystemExit:
        pass
    finally:
        sys.stdin, sys.stdout = saved_stdin, saved_stdout
    return captured_output.getvalue().strip()


def test_main_denies_write_with_unresolved_comment_path(tmp_path: Path) -> None:
    """The hook denies a Write whose workflow comment cites a non-resolving path."""
    workflow_file = _build_repository(tmp_path, COLLECTION_COMMENT)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(workflow_file), "content": workflow_file.read_text()},
    }
    emitted = _run_main_capturing_decision(payload)
    decision = json.loads(emitted)
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        "tests/test_samsung_sheets.py" in decision["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_main_allows_write_with_resolving_comment_path(tmp_path: Path) -> None:
    """The hook allows a Write whose workflow comment cites only resolving paths."""
    corrected_comment = COLLECTION_COMMENT.replace(
        "tests/test_samsung_sheets.py", "config/tests/test_samsung_sheets.py"
    )
    workflow_file = _build_repository(tmp_path, corrected_comment)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(workflow_file), "content": workflow_file.read_text()},
    }
    assert _run_main_capturing_decision(payload) == ""
