"""Unit tests for pr-description-enforcer PR-number and body-flag detection."""

import importlib.util
import inspect
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_ROOT = _HOOK_DIR.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

pr_number_spec = importlib.util.spec_from_file_location(
    "pr_description_pr_number",
    _HOOK_DIR / "pr_description_pr_number.py",
)
assert pr_number_spec is not None
assert pr_number_spec.loader is not None
hook_module = importlib.util.module_from_spec(pr_number_spec)
pr_number_spec.loader.exec_module(hook_module)


def test_extract_pr_number_from_gh_pr_edit() -> None:
    command = 'gh pr edit 467 --body "some body text here"'
    assert hook_module._extract_pr_number_from_command(command) == 467


def test_extract_pr_number_from_gh_pr_comment() -> None:
    command = 'gh pr comment 467 --body "some comment body"'
    assert hook_module._extract_pr_number_from_command(command) == 467


def test_extract_pr_number_from_gh_pr_create_returns_none() -> None:
    command = 'gh pr create --repo jl-cmd/claude-code-config --body "some body"'
    assert hook_module._extract_pr_number_from_command(command) is None


def test_extract_pr_number_from_malformed_command_returns_none() -> None:
    command = 'gh pr edit --body "body without positional"'
    assert hook_module._extract_pr_number_from_command(command) is None


def test_extract_pr_number_does_not_pick_up_number_in_title() -> None:
    command = 'gh pr edit 467 --title "PR 999 was bad" --body "some body"'
    assert hook_module._extract_pr_number_from_command(command) == 467


def test_command_carries_body_flag_detects_body_file() -> None:
    """`--body-file` detection must continue to work after the redundant
    explicit check is removed. The shorter `--body` substring still catches
    `--body-file` because `--body` is a prefix of `--body-file`."""
    assert hook_module._command_carries_body_flag("gh pr create --body-file body.md")
    assert hook_module._command_carries_body_flag("gh pr create --body-file=body.md")
    assert hook_module._command_carries_body_flag("gh pr edit 1 -F body.md")
    assert hook_module._command_carries_body_flag("gh pr edit 1 -F=body.md")


def test_command_carries_body_flag_does_not_double_check_body_file() -> None:
    """Pin that the function does NOT execute a redundant `--body-file in command`
    check. `--body` is a substring of `--body-file`, so the longer form is
    matched implicitly by the shorter check. Pin the source so the dead branch
    cannot drift back."""
    source_text = inspect.getsource(hook_module._command_carries_body_flag)
    assert source_text.count('"--body-file"') == 0, (
        f"`--body-file` substring check is redundant with `--body`; remove it. Source:\n{source_text}"
    )


def test_resolve_positional_pr_number_accepts_bare_integer() -> None:
    assert hook_module._resolve_positional_pr_number("467") == 467


def test_resolve_positional_pr_number_accepts_pr_url() -> None:
    assert hook_module._resolve_positional_pr_number("https://github.com/o/r/pull/467") == 467


def test_resolve_positional_pr_number_rejects_non_pr_url() -> None:
    assert hook_module._resolve_positional_pr_number("https://github.com/o/r/issues/467") is None


def test_resolve_positional_pr_number_rejects_shell_variable() -> None:
    assert hook_module._resolve_positional_pr_number("$PR_NUMBER") is None


def test_extract_pr_number_skips_repo_value_flag() -> None:
    """gh pr edit --repo owner/r 467 --body "x" must return 467 -- the --repo value must be skipped."""
    command = 'gh pr edit --repo owner/r 467 --body "x"'
    assert hook_module._extract_pr_number_from_command(command) == 467


def test_extract_pr_number_from_pr_url_positional() -> None:
    """gh pr edit https://github.com/o/r/pull/467 --body "x" must return 467 -- URL form is valid."""
    command = 'gh pr edit https://github.com/o/r/pull/467 --body "x"'
    assert hook_module._extract_pr_number_from_command(command) == 467


def test_extract_pr_number_from_pr_url_after_repo_flag() -> None:
    """Combined: --repo flag plus URL positional must still resolve to the URL's PR number."""
    command = 'gh pr edit --repo owner/r https://github.com/o/r/pull/999 --body "x"'
    assert hook_module._extract_pr_number_from_command(command) == 999


def test_extract_pr_number_skips_repo_equals_form() -> None:
    """gh pr edit --repo=owner/r 467 --body "x" must return 467 -- the equals-form must also be handled."""
    command = 'gh pr edit --repo=owner/r 467 --body "x"'
    assert hook_module._extract_pr_number_from_command(command) == 467


def test_extract_pr_number_from_pr_url_with_trailing_query_string() -> None:
    """A PR URL with a `?diff=split` or other trailing query/fragment must still resolve.
    The trailing group `(?:[/?#].*)?` in the URL regex is what makes this work."""
    command = 'gh pr edit https://github.com/o/r/pull/467?diff=split --body "x"'
    assert hook_module._extract_pr_number_from_command(command) == 467


def test_extract_pr_number_skips_body_long_flag_value() -> None:
    """gh pr edit --body "Fixes #999" 472 must return 472 -- the --body value must not
    be treated as a positional argument. Without skipping body-flag values, the body
    text would be parsed as the positional slot and PR-number extraction would fail."""
    command = 'gh pr edit --body "Fixes #999" 472'
    assert hook_module._extract_pr_number_from_command(command) == 472


def test_extract_pr_number_skips_body_short_flag_value() -> None:
    """gh pr edit -b 'Fixes #999' 472 must return 472 -- short -b alias must also skip its value."""
    command = 'gh pr edit -b "Fixes #999" 472'
    assert hook_module._extract_pr_number_from_command(command) == 472


def test_extract_pr_number_skips_body_file_long_flag_value() -> None:
    """gh pr edit --body-file body.md 472 must return 472 -- --body-file value must skip."""
    command = "gh pr edit --body-file body.md 472"
    assert hook_module._extract_pr_number_from_command(command) == 472


def test_extract_pr_number_skips_body_file_short_flag_value() -> None:
    """gh pr edit -F body.md 472 must return 472 -- -F short alias must also skip its value."""
    command = "gh pr edit -F body.md 472"
    assert hook_module._extract_pr_number_from_command(command) == 472


def test_extract_pr_number_skips_body_equals_form() -> None:
    """gh pr edit --body="Fixes #999" 472 must return 472 -- equals-form has the value
    attached to the same token, so only the flag token itself should be skipped."""
    command = 'gh pr edit --body="Fixes #999" 472'
    assert hook_module._extract_pr_number_from_command(command) == 472


def test_command_carries_body_flag_short_b_equals_form() -> None:
    """`-b=value` short form must be detected by the pre-filter; previous version only
    checked the space-separated `-b ` substring and silently bypassed the equals form."""
    assert hook_module._command_carries_body_flag('gh pr edit 123 -b="x"') is True


def test_command_carries_body_flag_short_F_equals_form() -> None:
    """`-F=path` short form must be detected by the pre-filter."""
    assert hook_module._command_carries_body_flag("gh pr edit 123 -F=body.md") is True
