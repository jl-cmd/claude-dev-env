"""Unit and integration tests for the volatile_path_in_post_blocker PreToolUse hook."""

import importlib.util
import json
import pathlib
import subprocess
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "volatile_path_in_post_blocker",
    _HOOK_DIR / "volatile_path_in_post_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

scan_text_for_volatile_marker = hook_module.scan_text_for_volatile_marker
extract_gh_post_body_texts = hook_module.extract_gh_post_body_texts
extract_mcp_body_texts = hook_module.extract_mcp_body_texts
_collect_body_texts = hook_module._collect_body_texts


def _body_names_volatile_path(tool_name: str, tool_input: dict[str, object]) -> bool:
    all_body_texts = _collect_body_texts(tool_name, tool_input)
    return hook_module._first_volatile_marker(all_body_texts) is not None


def test_scan_detects_job_scratch_path_backslash() -> None:
    text = r"See C:\Users\jon\.claude-editor\jobs\95762cea\tmp\staging\contact_sheet.png"
    assert scan_text_for_volatile_marker(text) == ".claude-editor/jobs/"


def test_scan_detects_job_scratch_path_forward_slash() -> None:
    text = "artifact at /home/user/.claude-editor/jobs/abc/tmp/out.png"
    assert scan_text_for_volatile_marker(text) == ".claude-editor/jobs/"


def test_scan_detects_worktree_path() -> None:
    text = r"edited .claude\worktrees\feature\file.py"
    assert scan_text_for_volatile_marker(text) == ".claude/worktrees/"


def test_scan_detects_appdata_temp_case_insensitive() -> None:
    text = r"C:\Users\jon\AppData\Local\Temp\bugteam\worktree"
    assert scan_text_for_volatile_marker(text) == "appdata/local/temp"


def test_scan_detects_unix_tmp() -> None:
    assert scan_text_for_volatile_marker("output written to /tmp/run/out.log") == "/tmp/"


def test_scan_detects_percent_temp_token() -> None:
    assert scan_text_for_volatile_marker("saved to %TEMP%\\out.txt") == "%temp%"


def test_scan_detects_env_temp_token() -> None:
    assert scan_text_for_volatile_marker("path is $env:TEMP\\out.txt") == "$env:temp"


def test_scan_detects_claude_job_dir_token() -> None:
    assert scan_text_for_volatile_marker("see $CLAUDE_JOB_DIR/staging/report.md") == "$claude_job_dir"


def test_scan_clean_body_returns_none() -> None:
    text = "The failing table is pasted below:\n| case | result |\n| a | pass |"
    assert scan_text_for_volatile_marker(text) is None


def test_gh_comment_with_job_scratch_path_is_blocked() -> None:
    command = (
        'gh pr comment 669 --body "Contact sheet at '
        r'C:\Users\jon\.claude-editor\jobs\95762cea\tmp\staging\contact_sheet.png"'
    )
    assert _body_names_volatile_path("Bash", {"command": command})


def test_gh_comment_with_clean_body_is_allowed() -> None:
    command = 'gh pr comment 669 --body "All checks pass. Table pasted inline above."'
    assert not _body_names_volatile_path("Bash", {"command": command})


def test_gh_pr_create_short_flag_blocked() -> None:
    command = 'gh pr create --title "T" -b "logs under /tmp/run/out.log"'
    assert _body_names_volatile_path("Bash", {"command": command})


def test_gh_issue_create_body_equals_form_blocked() -> None:
    command = 'gh issue create --title "T" --body="dump in %TEMP%\\dump.json"'
    assert _body_names_volatile_path("Bash", {"command": command})


def test_body_file_content_is_scanned_and_blocked(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text(
        "Artifact: $CLAUDE_JOB_DIR/tmp/contact_sheet.png",
        encoding="utf-8",
    )
    command = f"gh pr comment 669 --body-file {body_file}"
    assert _body_names_volatile_path("Bash", {"command": command})


def test_body_file_clean_content_is_allowed(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text("Everything is green. Results inline above.", encoding="utf-8")
    command = f"gh pr comment 669 --body-file {body_file}"
    assert not _body_names_volatile_path("Bash", {"command": command})


def test_non_post_gh_command_is_untouched() -> None:
    assert not _body_names_volatile_path("Bash", {"command": "gh pr list --repo owner/repo"})


def test_gh_pr_view_with_tmp_in_flag_is_untouched() -> None:
    command = "gh pr view 10 --json body --jq .body > /tmp/out.json"
    assert not _body_names_volatile_path("Bash", {"command": command})


def test_substring_mention_of_gh_post_does_not_classify() -> None:
    command = 'echo "example: gh pr comment 42 --body \\"see /tmp/x\\"" >> notes.txt'
    assert not _body_names_volatile_path("Bash", {"command": command})


def test_gh_word_not_first_token_does_not_classify() -> None:
    command = r'echo gh pr comment 42 --body "see C:\.claude-editor\jobs\x"'
    assert not _body_names_volatile_path("Bash", {"command": command})


def test_env_assignment_prefix_still_classifies() -> None:
    command = 'GH_TOKEN=abc gh pr comment 669 --body "log at /tmp/run.log"'
    assert _body_names_volatile_path("Bash", {"command": command})


def test_unparseable_command_is_allowed() -> None:
    assert not _body_names_volatile_path(
        "Bash", {"command": "gh pr comment 1 --body 'unterminated"}
    )


def test_mcp_issue_comment_body_blocked() -> None:
    tool_input: dict[str, object] = {"body": "artifact at $CLAUDE_JOB_DIR/tmp/out.png"}
    assert _body_names_volatile_path("mcp__plugin_github_github__add_issue_comment", tool_input)


def test_mcp_review_comment_param_blocked() -> None:
    tool_input: dict[str, object] = {"comment": r"see .claude\worktrees\x\file"}
    assert _body_names_volatile_path(
        "mcp__plugin_github_github__add_reply_to_pull_request_comment", tool_input
    )


def test_mcp_clean_body_allowed() -> None:
    tool_input: dict[str, object] = {"body": "LGTM, results pasted inline."}
    assert not _body_names_volatile_path("mcp__plugin_github_github__add_issue_comment", tool_input)


def test_mcp_read_tool_without_body_allowed() -> None:
    tool_input: dict[str, object] = {"pullNumber": 10}
    assert not _body_names_volatile_path("mcp__plugin_github_github__pull_request_read", tool_input)


def test_extract_mcp_body_texts_skips_non_string_values() -> None:
    tool_input: dict[str, object] = {"body": None, "comment": 42}
    assert extract_mcp_body_texts(tool_input) == []


def test_extract_gh_post_body_texts_returns_inline_and_file(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "b.md"
    body_file.write_text("file body text", encoding="utf-8")
    command = f'gh pr create --title "T" --body "inline body" --body-file {body_file}'
    all_texts = extract_gh_post_body_texts(command)
    assert "inline body" in all_texts
    assert "file body text" in all_texts


def test_hook_subprocess_denies_volatile_gh_comment() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": 'gh pr comment 669 --body "art at $CLAUDE_JOB_DIR/tmp/x.png"',
        },
    }
    completion = subprocess.run(
        [sys.executable, str(_HOOK_DIR / "volatile_path_in_post_blocker.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    decision = json.loads(completion.stdout)
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_subprocess_allows_clean_gh_comment() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": 'gh pr comment 669 --body "all green, results inline"'},
    }
    completion = subprocess.run(
        [sys.executable, str(_HOOK_DIR / "volatile_path_in_post_blocker.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completion.stdout.strip() == ""
