"""Unit tests for gh-body-arg-blocker PreToolUse hook."""

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "gh_body_arg_blocker",
    _HOOK_DIR / "gh-body-arg-blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
_uses_body_string_arg = hook_module._uses_body_string_arg


def test_blocks_issue_create_with_body_string() -> None:
    assert _uses_body_string_arg('gh issue create --title "T" --body "text"')


def test_blocks_issue_edit_with_body_string() -> None:
    assert _uses_body_string_arg('gh issue edit 42 --body "updated text"')


def test_blocks_issue_comment_with_body_string() -> None:
    assert _uses_body_string_arg('gh issue comment 42 --body "my comment"')


def test_blocks_pr_create_with_body_string() -> None:
    assert _uses_body_string_arg('gh pr create --title "T" --body "desc"')


def test_blocks_pr_edit_with_body_string() -> None:
    assert _uses_body_string_arg('gh pr edit 10 --body "new desc"')


def test_blocks_pr_comment_with_body_string() -> None:
    assert _uses_body_string_arg('gh pr comment 10 --body "LGTM"')


def test_blocks_pr_review_with_body_string() -> None:
    assert _uses_body_string_arg('gh pr review 10 --approve --body "looks good"')


def test_blocks_short_b_flag() -> None:
    assert _uses_body_string_arg('gh pr create --title "T" -b "desc"')


def test_blocks_pr_create_with_body_equals_syntax() -> None:
    assert _uses_body_string_arg('gh pr create --title "T" --body="text"')


def test_blocks_pr_create_with_short_b_equals_syntax() -> None:
    assert _uses_body_string_arg('gh pr create --title "T" -b="text"')


def test_blocks_multiline_bash_continuation_body_on_later_line() -> None:
    command = 'gh pr create \\\n  --title "T" \\\n  --body "text"\n'
    assert _uses_body_string_arg(command)


def test_blocks_multiline_continuation_with_trailing_whitespace() -> None:
    """Continuation marker followed by trailing spaces must still join lines."""
    command = 'gh pr create \\   \n  --title "T" \\   \n  --body "text"\n'
    assert _uses_body_string_arg(command)


def test_blocks_multiline_powershell_continuation_body_on_later_line() -> None:
    """PowerShell backtick continuation lines must be joined before tokenizing."""
    command = 'gh pr create `\n  --title "T" `\n  --body "text"\n'
    assert _uses_body_string_arg(command)


def test_blocks_multiline_powershell_continuation_with_trailing_whitespace() -> None:
    """PowerShell backtick continuation with trailing spaces must still join."""
    command = 'gh pr create `   \n  --title "T" `   \n  --body "text"\n'
    assert _uses_body_string_arg(command)


def test_approves_body_file() -> None:
    assert not _uses_body_string_arg(
        'gh pr create --title "T" --body-file /tmp/body.md'
    )


def test_approves_body_file_equals_syntax() -> None:
    assert not _uses_body_string_arg(
        'gh pr create --title "T" --body-file=/tmp/body.md'
    )


def test_approves_issue_create_with_body_file() -> None:
    assert not _uses_body_string_arg(
        'gh issue create --title "T" --body-file /tmp/body.md'
    )


def test_approves_unrelated_gh_command() -> None:
    assert not _uses_body_string_arg("gh pr list --repo owner/repo")


def test_approves_gh_pr_merge() -> None:
    assert not _uses_body_string_arg("gh pr merge 10 --squash")


def test_approves_empty_command() -> None:
    assert not _uses_body_string_arg("")


def test_no_false_positive_body_in_title_value() -> None:
    """--body inside a quoted --title value must not trigger."""
    assert not _uses_body_string_arg(
        'gh pr create --title "block gh --body string arg" --body-file /tmp/b.md'
    )


def test_no_false_positive_body_as_title_value() -> None:
    """--title "--body" must not trigger; posix=False retains quotes so the value is not a bare flag."""
    assert not _uses_body_string_arg(
        'gh pr create --title "--body" --body-file /tmp/b.md'
    )


def test_no_false_positive_windows_path_in_body_file() -> None:
    """Unquoted Windows path with backslashes in --body-file must be approved without token corruption."""
    assert not _uses_body_string_arg(
        r'gh pr create --title "T" --body-file C:\Users\jon\tmp\body.md'
    )


def test_no_false_positive_heredoc_body_text() -> None:
    """Multiline command where body content mentions --body must not trigger."""
    command = (
        "gh pr create --title 'My PR' --body-file /tmp/body.md\n"
        "# body content below mentions --body for documentation\n"
        '# Use --body-file not --body "string"\n'
    )
    assert not _uses_body_string_arg(command)


def test_no_false_positive_unparseable_command() -> None:
    """Unparseable first line (unmatched quote) falls back to approve."""
    assert not _uses_body_string_arg("gh pr create --title 'unmatched --body oops")
