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

from _gh_body_arg_utils import iter_significant_tokens


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
    """Unparseable line WITHOUT --body token must approve (out of hook scope)."""
    assert not _uses_body_string_arg("gh pr create --title 'unmatched quote here")


def test_blocks_unparseable_command_when_body_token_present() -> None:
    """C2: shlex-unparseable command on affected subcommand WITH --body must BLOCK.

    A heredoc-style command like `gh pr create --body "$(cat <<EOF...)"` raises
    ValueError in shlex.split(posix=False); silently approving lets the exact
    pattern this hook exists to block slip through. Detect a bare --body literal
    via regex and deny.
    """
    command = 'gh pr create --title "T" --body "$(cat <<EOF\nbody text\nEOF\n)"'
    assert _uses_body_string_arg(command)


def test_blocks_unparseable_command_with_short_b_token_present() -> None:
    """C2 short form: unparseable command (odd single quote) with bare -b must BLOCK."""
    command = "gh pr comment 42 --unterminated 'quote here -b short body text"
    assert _uses_body_string_arg(command)


def test_approves_body_file_dash_stdin_sentinel() -> None:
    """`gh pr create --body-file -` reads body from stdin and is allowed."""
    assert not _uses_body_string_arg("gh pr create --title 'T' --body-file -")


def test_blocks_crlf_line_endings_with_bash_continuation() -> None:
    """CRLF line endings must not break bash continuation joining."""
    command = 'gh pr create \\\r\n  --title "T" \\\r\n  --body "text"\r\n'
    assert _uses_body_string_arg(command)


def test_blocks_continuation_with_tab_after_marker() -> None:
    """Tab whitespace after a continuation marker still counts as continuation."""
    command = 'gh pr create \\\t\n  --title "T" \\\t\n  --body "text"\n'
    assert _uses_body_string_arg(command)


def test_blocks_utf8_body_with_emoji() -> None:
    """UTF-8 body content (emoji) must still be detected as a body string."""
    assert _uses_body_string_arg('gh pr create --title "T" --body "ship it 🚀"')


def test_blocks_pr_review_request_changes_short_b() -> None:
    """gh pr review --request-changes -b "text" must block."""
    assert _uses_body_string_arg(
        'gh pr review 10 --request-changes -b "needs work"'
    )


def test_blocks_empty_body_string() -> None:
    """`gh pr create --body=""` is still a body-string call; must block."""
    assert _uses_body_string_arg('gh pr create --title "T" --body=""')


def test_blocks_body_file_followed_by_body_string() -> None:
    """H5: malformed `gh pr create --body-file --body "text"` must BLOCK.

    Without the flag-shape guard, --body-file consumes --body as its path and
    the real body string slips through as a positional. Treat a value-taking
    flag as value-missing when the next token is itself flag-shaped.
    """
    assert _uses_body_string_arg(
        'gh pr create --body-file --body "real body text"'
    )


def test_blocks_windows_path_with_trailing_backslash_continuation() -> None:
    """C1: prior line ending in `C:\\Users\\jon\\` must still continue lines.

    Naive `count("\\\\") % 2 == 1` mis-classifies this (count=4, even -> no
    continuation) and misses --body on the next line. Counting only the
    trailing run of backslashes correctly identifies a single trailing
    backslash as a continuation marker.
    """
    command = (
        'gh pr create --title C:\\Users\\jon\\ \\\n'
        '  --body "real body text"\n'
    )
    assert _uses_body_string_arg(command)


def test_does_not_join_lines_after_markdown_fence() -> None:
    """C1: a prior line ending in three backticks (count=3, odd) must NOT continue.

    Old logic treated any odd backtick count as a PowerShell continuation; a
    closing markdown fence trailing the line would falsely join the next line.
    The fix requires whitespace before a trailing backtick (PowerShell
    continuation marker is `<space>` + backtick + newline) so a bare ``` line
    end does not continue.
    """
    command = (
        "echo ```\n"
        'gh pr create --title "T" --body "real body text"\n'
    )
    assert _uses_body_string_arg(command) is False


def test_does_not_false_positive_equals_form_in_title_value() -> None:
    """`--title="use --body x"` posix=False keeps the value quoted; must approve."""
    assert not _uses_body_string_arg(
        'gh pr create --title="use --body x" --body-file /tmp/b.md'
    )


def test_blocks_short_body_file_F_then_body_string_later() -> None:
    """`-F /path` (short for --body-file) consumes its value, then --body must still block."""
    assert _uses_body_string_arg(
        'gh pr create -F /tmp/file.md --body "extra body"'
    )


def test_approves_short_body_file_F_alone() -> None:
    """`-F /path` alone must be approved (it is the short form of --body-file)."""
    assert not _uses_body_string_arg(
        'gh pr create --title "T" -F /tmp/file.md'
    )


def test_approves_template_flag_value_does_not_trigger() -> None:
    """`--template path` consumes its value; `--body` inside path must not trigger."""
    assert not _uses_body_string_arg(
        'gh pr create --title "T" --template /tmp/--body-template.md --body-file /tmp/b.md'
    )


def test_approves_recover_flag_value() -> None:
    """`--recover path` is value-taking and must not leak `--body` mis-detection."""
    assert not _uses_body_string_arg(
        'gh pr create --recover /tmp/state.json --body-file /tmp/b.md'
    )


def test_approves_body_file_only_shlex_unparseable() -> None:
    """loop1-1: shlex-unparseable command with only --body-file must NOT block.

    The old \b boundary in _BARE_BODY_TOKEN_PATTERN fired between 'y' and '-'
    in '--body-file', causing any unparseable command containing only --body-file
    (no bare --body) to be incorrectly blocked.
    """
    assert not _uses_body_string_arg(
        "gh pr create --title 'unmatched --body-file /tmp/body.md"
    )


def test_blocks_body_equals_spaced_value() -> None:
    """loop1-3: --body='has space' split by shlex(posix=False) into two tokens.

    shlex.split(posix=False) splits `--body='has space'` into ["--body='has", "space'"].
    The continuation token "space'" must be skipped, not yielded as a significant
    positional — the leading --body='has token must still trigger a block.
    """
    assert _uses_body_string_arg(
        "gh pr create --title 'T' --body='has space'"
    )


def test_blocks_short_b_equals_spaced_value() -> None:
    """loop1-3: -b='has space' split by shlex(posix=False) — continuation token skipped."""
    assert _uses_body_string_arg(
        "gh pr create --title 'T' -b='has space'"
    )


def test_blocks_body_after_unclosed_quoted_title() -> None:
    """loop2-1: unclosed quote in --title= must not consume --body token.

    shlex.split(posix=False) keeps --title="unclosed as one token whose value
    starts with a quote but has no closing match among subsequent tokens.
    count_extra_tokens_to_skip_for_split_quoted_value must return 0 (not the
    full remaining list length) so the following --body flag stays visible.
    """
    assert _uses_body_string_arg(
        'gh pr create --title="unclosed --body "real body"'
    )


def test_space_form_value_flag_remaining_excludes_consumed_value() -> None:
    """loop2-2: remaining_tokens for space-form value flag must not include the consumed value.

    When iter_significant_tokens yields (--title, remaining) for --title MyTitle,
    remaining must contain only tokens after MyTitle — not MyTitle itself.
    """
    all_yielded = list(iter_significant_tokens('gh pr create --title MyTitle --body "desc"'))
    title_remaining = next(remaining for token, remaining in all_yielded if token == "--title")
    assert "MyTitle" not in title_remaining


def test_quoted_value_starts_split_unclosed_single_quote() -> None:
    from _gh_body_arg_utils import _quoted_value_starts_split
    assert _quoted_value_starts_split("'it") is True


def test_quoted_value_starts_split_fully_closed() -> None:
    from _gh_body_arg_utils import _quoted_value_starts_split
    assert _quoted_value_starts_split("'hello'") is False


def test_quoted_value_starts_split_double_quote_unclosed() -> None:
    from _gh_body_arg_utils import _quoted_value_starts_split
    assert _quoted_value_starts_split('"hello') is True


def test_count_extra_tokens_returns_none_when_exhausted() -> None:
    from _gh_body_arg_utils import count_extra_tokens_to_skip_for_split_quoted_value
    result = count_extra_tokens_to_skip_for_split_quoted_value([], "'unclosed")
    assert result is None


def test_count_extra_tokens_returns_none_no_closing_in_remaining() -> None:
    from _gh_body_arg_utils import count_extra_tokens_to_skip_for_split_quoted_value
    result = count_extra_tokens_to_skip_for_split_quoted_value(["word", "another"], "'unclosed")
    assert result is None


def test_count_extra_tokens_returns_zero_for_self_contained() -> None:
    from _gh_body_arg_utils import count_extra_tokens_to_skip_for_split_quoted_value
    result = count_extra_tokens_to_skip_for_split_quoted_value(["next"], "'complete'")
    assert result == 0


def test_all_body_flag_prefixes_used_for_equals_skip() -> None:
    from _gh_body_arg_utils import _all_equals_prefixes_for_skip, all_body_flag_prefixes
    for each_prefix in all_body_flag_prefixes:
        assert each_prefix in _all_equals_prefixes_for_skip

