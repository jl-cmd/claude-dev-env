"""Unit tests for pr-description-enforcer PreToolUse hook."""

import importlib.util
import io
import json
import pathlib
import sys
from unittest.mock import patch

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

from _gh_body_arg_utils import get_logical_first_line

hook_spec = importlib.util.spec_from_file_location(
    "pr_description_enforcer",
    _HOOK_DIR / "pr_description_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
extract_body_from_command = hook_module.extract_body_from_command
validate_pr_body = hook_module.validate_pr_body

VALID_BODY = (
    "## Description\n\nThis PR fixes a real bug.\n\n"
    "## Why\n\nBecause it was broken in production.\n\n"
    "## How\n\nRefactored the auth module to handle edge cases correctly.\n"
)


def test_extract_body_from_body_string() -> None:
    command = 'gh pr create --title "T" --body "Description and some text."'
    assert "Description" in extract_body_from_command(command)


def test_extract_body_from_body_file_space_form(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text(VALID_BODY)
    command = f'gh pr create --title "T" --body-file {body_file}'
    assert extract_body_from_command(command) == VALID_BODY


def test_extract_body_from_body_file_equals_form(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text(VALID_BODY)
    command = f'gh pr create --title "T" --body-file="{body_file}"'
    assert extract_body_from_command(command) == VALID_BODY


def test_extract_body_from_body_file_equals_form_with_spaces(
    tmp_path: pathlib.Path,
) -> None:
    """Quoted --body-file=VALUE with spaces in path must be reassembled, not truncated."""
    body_file = tmp_path / "my body with spaces.md"
    body_file.write_text(VALID_BODY)
    command = f'gh pr create --title "T" --body-file="{body_file}"'
    assert extract_body_from_command(command) == VALID_BODY


def test_extract_body_file_missing_path_returns_none() -> None:
    command = 'gh pr create --title "T" --body-file /nonexistent/path.md'
    assert extract_body_from_command(command) is None


def test_extract_body_file_shell_variable_returns_none() -> None:
    """Shell variables like $bodyPath can't be resolved at hook time -- return None to skip enforcement."""
    command = 'gh pr create --title "T" --body-file $bodyPath'
    assert extract_body_from_command(command) is None


def test_extract_body_file_no_false_positive_in_title() -> None:
    command = 'gh pr create --title "use --body-file /tmp/x.md" --body "actual body"'
    extracted_body = extract_body_from_command(command)
    assert extracted_body == "actual body"


def test_no_false_positive_body_in_title_string_value() -> None:
    command = 'gh pr create --title \'use --body "x"\' --body "actual body"'
    assert extract_body_from_command(command) == "actual body"


def test_extract_body_from_body_equals_double_quote_form() -> None:
    command = 'gh pr create --title "T" --body="Some body text here."'
    assert extract_body_from_command(command) == "Some body text here."


def test_extract_body_from_body_equals_single_quote_form() -> None:
    command = "gh pr create --title 'T' --body='Some body text here.'"
    assert extract_body_from_command(command) == "Some body text here."


def test_extract_body_equals_shell_var_returns_empty() -> None:
    """Shell variable like --body=$bodyText cannot be resolved at hook time -- approve safely."""
    command = 'gh pr create --title "T" --body=$bodyText'
    assert extract_body_from_command(command) == ""


def test_extract_short_flag_equals_form() -> None:
    command = 'gh pr create --title "T" -b="Some body text here."'
    assert extract_body_from_command(command) == "Some body text here."


def test_extract_short_flag_shell_var_returns_empty() -> None:
    """Shell variable like -b=$var cannot be resolved at hook time -- approve safely."""
    command = 'gh pr create --title "T" -b=$bodyVar'
    assert extract_body_from_command(command) == ""


def test_validate_passes_complete_body() -> None:
    assert validate_pr_body(VALID_BODY) == []


def test_validate_blocks_missing_sections() -> None:
    violations = validate_pr_body("Some body text without required sections.\n" * 5)
    assert any(
        "Missing required section" in each_violation for each_violation in violations
    )


def test_validate_blocks_vague_language() -> None:
    body = VALID_BODY + "\nFixed bug in the auth module.\n"
    violations = validate_pr_body(body)
    assert any("Vague language" in each_violation for each_violation in violations)


def test_validate_blocks_short_body() -> None:
    violations = validate_pr_body("Too short.")
    assert any("too short" in each_violation.lower() for each_violation in violations)


def test_body_file_content_validated(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    body = extract_body_from_command(
        f'gh pr create --title "T" --body-file {body_file}'
    )
    assert body == "Too short."
    violations = validate_pr_body(body)
    assert violations


def test_extract_body_string_value_skips_body_file_path_token() -> None:
    command = 'gh pr create --body-file --body "actual text"'
    assert extract_body_from_command(command) is None


def test_get_logical_first_line_does_not_join_bash_command_substitution() -> None:
    command = 'VAR=`cmd`\ngh pr create --body "text"'
    assert get_logical_first_line(command) == "VAR=`cmd`"


def test_get_logical_first_line_joins_powershell_backtick_continuation() -> None:
    command = 'Some-Command -Param `\n"value"'
    assert get_logical_first_line(command) == 'Some-Command -Param "value"'


def test_main_does_not_block_when_dash_b_only_appears_in_word() -> None:
    hook_input = {
        "tool_name": "Bash",
        "tool_input": {"command": 'gh pr create --title "fix sub-branch handling"'},
    }
    captured_stdout = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(hook_input))):
        with patch("sys.stdout", captured_stdout):
            try:
                hook_module.main()
            except SystemExit:
                pass
    assert "deny" not in captured_stdout.getvalue()


def test_main_does_not_block_when_no_body_flag_present() -> None:
    hook_input = {
        "tool_name": "Bash",
        "tool_input": {"command": 'gh pr create --title "My PR"'},
    }
    captured_stdout = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(hook_input))):
        with patch("sys.stdout", captured_stdout):
            try:
                hook_module.main()
            except SystemExit:
                pass
    assert "deny" not in captured_stdout.getvalue()


def test_extract_body_from_body_file_short_F_form(tmp_path: pathlib.Path) -> None:
    """`gh pr create -F PATH` (short form of --body-file) must read the file."""
    body_file = tmp_path / "body.md"
    body_file.write_text(VALID_BODY)
    command = f'gh pr create --title "T" -F {body_file}'
    assert extract_body_from_command(command) == VALID_BODY


def test_extract_body_ignores_body_inside_title_quoted_value() -> None:
    """Migration to shared iterator: `--title "contains --body here"` must not false-match."""
    command = 'gh pr create --title "contains --body here" --body-file /tmp/real.md'
    extracted_body = extract_body_from_command(command)
    assert extracted_body is None or extracted_body == ""


def test_extract_body_reassembles_split_quoted_equals_value() -> None:
    """`--body="has multiple spaces inside"` must reassemble across posix=False tokens."""
    command = 'gh pr create --title "T" --body="this body has multiple words"'
    assert extract_body_from_command(command) == "this body has multiple words"


def test_read_body_file_rejects_relative_path_traversal(tmp_path) -> None:
    import importlib.util, pathlib, sys
    _HOOK_DIR = pathlib.Path(__file__).parent
    if str(_HOOK_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOK_DIR))
    spec = importlib.util.spec_from_file_location('pde', _HOOK_DIR / 'pr_description_enforcer.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    import os, pytest
    sentinel_file = tmp_path / 'secret.txt'
    sentinel_file.write_text('secret')
    try:
        rel_path = os.path.relpath(str(sentinel_file))
    except ValueError:
        pytest.skip('tmp_path on different drive than cwd; relpath undefined on Windows')
    if '..' not in rel_path:
        pytest.skip('file is under cwd, not a traversal case')
    with pytest.raises(m.PathTraversalError):
        m._read_body_file_contents(rel_path)


def test_read_body_file_allows_absolute_path_outside_cwd(tmp_path) -> None:
    import importlib.util, pathlib, sys
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location('pde2', _HOOK_DIR / 'pr_description_enforcer.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    body_file = tmp_path / 'body.md'
    body_file.write_text('hello')
    result = m._read_body_file_contents(str(body_file))
    assert result == 'hello'


def test_reassemble_split_quoted_value_returns_none_for_unclosed_quote() -> None:
    import importlib.util, pathlib, sys
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location('pde3', _HOOK_DIR / 'pr_description_enforcer.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    result = m._reassemble_split_quoted_value("'unclosed", [])
    assert result is None


def test_extract_body_returns_none_for_unclosed_quote_value() -> None:
    result = extract_body_from_command("gh pr create --title T --body='unclosed")
    assert result is None



def test_body_file_stdin_sentinel_returns_none() -> None:
    """--body-file - (stdin sentinel) must return None so enforcer skips validation."""
    command = 'gh pr create --title "T" --body-file -'
    assert extract_body_from_command(command) is None


def test_body_file_shell_variable_returns_none() -> None:
    """--body-file $VAR cannot be audited at hook time -- must return None, not empty string."""
    command = 'gh pr create --title "T" --body-file $BODY_VAR'
    assert extract_body_from_command(command) is None


def test_body_file_path_traversal_returns_none() -> None:
    """Path traversal rejection must return None so enforcer does not raise false positive."""
    import os
    import importlib.util
    import pathlib
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location('pde_t', _HOOK_DIR / 'pr_description_enforcer.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    result = m._resolve_body_file_value("../../../etc/passwd")
    assert result is None


def test_main_allows_through_stdin_sentinel_body_file() -> None:
    """--body-file - must not be blocked (stdin body is unauditable)."""
    import io
    import json
    from unittest.mock import patch
    hook_input = {
        "tool_name": "Bash",
        "tool_input": {"command": 'gh pr create --title "T" --body-file -'},
    }
    captured_stdout = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(hook_input))):
        with patch("sys.stdout", captured_stdout):
            try:
                hook_module.main()
            except SystemExit:
                pass
    assert "deny" not in captured_stdout.getvalue()


def test_read_body_file_rejects_absolute_symlink_outside_cwd(tmp_path: pathlib.Path) -> None:
    """Absolute symlink pointing outside cwd must raise PathTraversalError."""
    import importlib.util
    import pytest
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location('pde_sym', _HOOK_DIR / 'pr_description_enforcer.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    target_file = tmp_path / "secret.txt"
    target_file.write_text("secret content")
    link_path = tmp_path / "evil_link"
    try:
        link_path.symlink_to(target_file)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    with pytest.raises(m.PathTraversalError):
        m._read_body_file_contents(str(link_path))


def test_read_body_file_allows_real_absolute_file_inside_cwd(tmp_path: pathlib.Path) -> None:
    """Real absolute file path that exists must be read successfully."""
    import importlib.util
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location('pde_abs', _HOOK_DIR / 'pr_description_enforcer.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    body_file = tmp_path / "body.md"
    body_file.write_text("hello body")
    result = m._read_body_file_contents(str(body_file))
    assert result == "hello body"


def test_read_body_file_allows_in_cwd_symlink_pointing_into_cwd(tmp_path: pathlib.Path) -> None:
    """Symlink inside cwd pointing to another file inside cwd must be readable."""
    import importlib.util
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location('pde_inlink', _HOOK_DIR / 'pr_description_enforcer.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    real_file = tmp_path / "real.md"
    real_file.write_text("real content")
    link_file = tmp_path / "link.md"
    try:
        link_file.symlink_to(real_file)
    except (OSError, NotImplementedError):
        import pytest
        pytest.skip("symlinks not supported on this platform")
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        result = m._read_body_file_contents(str(link_file))
    assert result == "real content"


def test_iter_significant_tokens_unclosed_quote_raises_value_error() -> None:
    """Unclosed quoted value in a value-taking flag raises ValueError so callers block conservatively.

    For equals-form: --title="unclosed raises ValueError (unclosed quote not in remaining tokens).
    For space-form: shlex.split itself raises ValueError before iter_significant_tokens is entered.
    Both paths result in ValueError propagating to callers.
    """
    import pytest
    from _gh_body_arg_utils import iter_significant_tokens
    with pytest.raises(ValueError):
        list(iter_significant_tokens('gh pr create --title="unclosed --body real_body'))


def test_scan_raw_tokens_does_not_false_match_body_in_title_value(tmp_path: pathlib.Path) -> None:
    """--title 'using --body-file is required' must not match --body-file inside the title value."""
    body_file = tmp_path / "real_body.md"
    body_file.write_text(VALID_BODY)
    command = f'gh pr create --title "using --body-file is required" --body-file {body_file}'
    result = extract_body_from_command(command)
    assert result == VALID_BODY


def test_extract_body_returns_none_for_unclosed_quote_value() -> None:
    result = extract_body_from_command("gh pr create --title T --body='unclosed")
    assert result is None
