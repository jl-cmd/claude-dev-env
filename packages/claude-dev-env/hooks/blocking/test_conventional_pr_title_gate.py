"""Unit tests for conventional_pr_title_gate PreToolUse hook."""

import importlib.util
import io
import json
import pathlib
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "conventional_pr_title_gate",
    _HOOK_DIR / "conventional_pr_title_gate.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

_matches_gh_pr_title_subcommand = hook_module._matches_gh_pr_title_subcommand
_parsed_command_tokens = hook_module._parsed_command_tokens
_extract_flag_value = hook_module._extract_flag_value
_is_conventional_commit_title = hook_module._is_conventional_commit_title
_repo_enforces_semantic_pr_titles = hook_module._repo_enforces_semantic_pr_titles

_SEMANTIC_WORKFLOW_TEXT = (
    "name: PR checks\n"
    "on:\n"
    "  pull_request:\n"
    "jobs:\n"
    "  validate:\n"
    "    steps:\n"
    "      - uses: amannn/action-semantic-pull-request@v5\n"
)

_PLAIN_WORKFLOW_TEXT = (
    "name: Tests\non:\n  push:\njobs:\n  test:\n    steps:\n      - run: npm test\n"
)


def _init_repo_with_workflow(repo_root: pathlib.Path, workflow_text: str) -> None:
    subprocess.run(["git", "init", str(repo_root)], capture_output=True, check=True)
    workflows_directory = repo_root / ".github" / "workflows"
    workflows_directory.mkdir(parents=True)
    (workflows_directory / "pr-check.yml").write_text(workflow_text, encoding="utf-8")


def _run_hook_with_stdin_text(stdin_text: str) -> tuple[str, str, int]:
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    exit_code = 0
    sys.stdin = io.StringIO(stdin_text)
    try:
        with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
            try:
                hook_module.main()
            except SystemExit as exit_signal:
                exit_code = exit_signal.code or 0
    finally:
        sys.stdin = sys.__stdin__
    return captured_stdout.getvalue(), captured_stderr.getvalue(), exit_code


def _run_hook(hook_input: dict) -> tuple[str, int]:
    stdout_text, _stderr_text, exit_code = _run_hook_with_stdin_text(json.dumps(hook_input))
    return stdout_text, exit_code


def test_matches_gh_pr_create_with_title() -> None:
    assert _matches_gh_pr_title_subcommand('gh pr create --title "add x"')


def test_matches_gh_pr_edit_with_title() -> None:
    assert _matches_gh_pr_title_subcommand('gh pr edit 10 --title "add x"')


def test_does_not_match_gh_pr_comment() -> None:
    assert not _matches_gh_pr_title_subcommand('gh pr comment 10 --body "LGTM"')


def test_does_not_match_unrelated_command() -> None:
    assert not _matches_gh_pr_title_subcommand("gh pr list --repo owner/repo")


def test_extract_flag_value_space_form() -> None:
    all_tokens = _parsed_command_tokens('gh pr create --title "feat: add x" --draft')
    assert all_tokens is not None
    assert _extract_flag_value(all_tokens, "--title", "-t") == "feat: add x"


def test_extract_flag_value_equals_form() -> None:
    all_tokens = _parsed_command_tokens('gh pr create --title="fix: broken thing" --draft')
    assert all_tokens is not None
    assert _extract_flag_value(all_tokens, "--title", "-t") == "fix: broken thing"


def test_extract_flag_value_short_form() -> None:
    all_tokens = _parsed_command_tokens('gh pr create -t "chore: bump deps"')
    assert all_tokens is not None
    assert _extract_flag_value(all_tokens, "--title", "-t") == "chore: bump deps"


def test_extract_flag_value_returns_none_when_absent() -> None:
    all_tokens = _parsed_command_tokens("gh pr create --draft")
    assert all_tokens is not None
    assert _extract_flag_value(all_tokens, "--title", "-t") is None


def test_parsed_command_tokens_returns_none_on_unparseable_command() -> None:
    assert _parsed_command_tokens("gh pr create --title 'unmatched quote here") is None


def test_is_conventional_commit_title_accepts_plain_type() -> None:
    assert _is_conventional_commit_title("feat: add the thing")


def test_is_conventional_commit_title_accepts_scope_and_breaking_marker() -> None:
    assert _is_conventional_commit_title("feat(hooks)!: drop the old flag")


def test_is_conventional_commit_title_rejects_non_conventional_title() -> None:
    assert not _is_conventional_commit_title("add the thing")


def test_repo_enforces_semantic_pr_titles_true_for_marker_workflow(tmp_path: pathlib.Path) -> None:
    repo_root = tmp_path / "semantic_repo"
    _init_repo_with_workflow(repo_root, _SEMANTIC_WORKFLOW_TEXT)
    assert _repo_enforces_semantic_pr_titles(str(repo_root))


def test_repo_enforces_semantic_pr_titles_false_for_plain_workflow(tmp_path: pathlib.Path) -> None:
    repo_root = tmp_path / "plain_repo"
    _init_repo_with_workflow(repo_root, _PLAIN_WORKFLOW_TEXT)
    assert not _repo_enforces_semantic_pr_titles(str(repo_root))


def test_repo_enforces_semantic_pr_titles_false_when_no_workflows_directory(
    tmp_path: pathlib.Path,
) -> None:
    repo_root = tmp_path / "no_workflows_repo"
    subprocess.run(["git", "init", str(repo_root)], capture_output=True, check=True)
    assert not _repo_enforces_semantic_pr_titles(str(repo_root))


def test_main_blocks_non_conventional_title_in_semantic_ci_repo(
    tmp_path: pathlib.Path,
) -> None:
    repo_root = tmp_path / "semantic_repo"
    _init_repo_with_workflow(repo_root, _SEMANTIC_WORKFLOW_TEXT)
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Bash",
            "cwd": str(repo_root),
            "tool_input": {"command": 'gh pr create --title "add the thing"'},
        }
    )
    assert exit_code == 0
    response_payload = json.loads(stdout_text)
    decision_block = response_payload["hookSpecificOutput"]
    assert decision_block["permissionDecision"] == "deny"
    assert "conventional-pr-title" in decision_block["permissionDecisionReason"]


def test_main_allows_conventional_title_in_semantic_ci_repo(tmp_path: pathlib.Path) -> None:
    repo_root = tmp_path / "semantic_repo"
    _init_repo_with_workflow(repo_root, _SEMANTIC_WORKFLOW_TEXT)
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Bash",
            "cwd": str(repo_root),
            "tool_input": {"command": 'gh pr create --title "feat(hooks): add the thing"'},
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_conventional_title_with_scope_and_breaking_marker(
    tmp_path: pathlib.Path,
) -> None:
    repo_root = tmp_path / "semantic_repo"
    _init_repo_with_workflow(repo_root, _SEMANTIC_WORKFLOW_TEXT)
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Bash",
            "cwd": str(repo_root),
            "tool_input": {"command": 'gh pr create --title "feat(x)!: drop y"'},
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_junk_title_when_no_semantic_marker(tmp_path: pathlib.Path) -> None:
    repo_root = tmp_path / "plain_repo"
    _init_repo_with_workflow(repo_root, _PLAIN_WORKFLOW_TEXT)
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Bash",
            "cwd": str(repo_root),
            "tool_input": {"command": 'gh pr create --title "add the thing"'},
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_non_gh_pr_create_command(tmp_path: pathlib.Path) -> None:
    repo_root = tmp_path / "semantic_repo"
    _init_repo_with_workflow(repo_root, _SEMANTIC_WORKFLOW_TEXT)
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Bash",
            "cwd": str(repo_root),
            "tool_input": {"command": "gh pr list --repo owner/repo"},
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_gh_pr_create_with_no_title(tmp_path: pathlib.Path) -> None:
    repo_root = tmp_path / "semantic_repo"
    _init_repo_with_workflow(repo_root, _SEMANTIC_WORKFLOW_TEXT)
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Bash",
            "cwd": str(repo_root),
            "tool_input": {"command": "gh pr create --draft"},
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_when_repo_flag_present(tmp_path: pathlib.Path) -> None:
    repo_root = tmp_path / "semantic_repo"
    _init_repo_with_workflow(repo_root, _SEMANTIC_WORKFLOW_TEXT)
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Bash",
            "cwd": str(repo_root),
            "tool_input": {"command": 'gh pr create --repo owner/other --title "add the thing"'},
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_non_bash_tool() -> None:
    stdout_text, exit_code = _run_hook(
        {"tool_name": "Write", "tool_input": {"content": "add the thing"}}
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_with_empty_stdin_exits_silently() -> None:
    stdout_text, stderr_text, exit_code = _run_hook_with_stdin_text("")
    assert exit_code == 0
    assert stdout_text == ""
    assert stderr_text == ""


def test_main_with_invalid_json_stdin_exits_silently() -> None:
    stdout_text, stderr_text, exit_code = _run_hook_with_stdin_text("{broken")
    assert exit_code == 0
    assert stdout_text == ""
    assert stderr_text == ""
