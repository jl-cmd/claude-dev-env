"""Unit tests for pr-description-enforcer gh command parsing."""

import importlib.util
import inspect
import os
import pathlib
import sys
from unittest.mock import patch

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_ROOT = _HOOK_DIR.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

from blocking._gh_body_arg_utils import (  # noqa: E402
    get_logical_first_line,
    iter_significant_tokens,
)

parser_spec = importlib.util.spec_from_file_location(
    "pr_description_command_parser",
    _HOOK_DIR / "pr_description_command_parser.py",
)
assert parser_spec is not None
assert parser_spec.loader is not None
hook_module = importlib.util.module_from_spec(parser_spec)
parser_spec.loader.exec_module(hook_module)
extract_body_from_command = hook_module.extract_body_from_command

VALID_BODY = (
    "Allow commas in branch names so PRs whose head branch was generated from "
    "a title or external identifier no longer fail validation before any git "
    "operation.\n\n"
    "Fixes #1300.\n\n"
    "## Changes\n\n"
    "- `src/github/operations/branch.ts`: add `,` to the whitelist regex\n"
    "- `test/branch.test.ts`: 3 new cases covering comma-bearing branch names\n\n"
    "## Test plan\n\n"
    "- `bun test test/branch.test.ts`\n"
    "- `bun run typecheck`\n"
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


def test_extract_body_equals_shell_var_returns_none() -> None:
    """Shell variable like --body=$bodyText cannot be resolved at hook time -- the
    extractor must signal this with None (unauditable), not empty string. An
    empty-string return value is reserved for a literal `--body ""` which should
    still be validated and blocked by the substantive-prose check."""
    command = 'gh pr create --title "T" --body=$bodyText'
    assert extract_body_from_command(command) is None


def test_extract_short_flag_equals_form() -> None:
    command = 'gh pr create --title "T" -b="Some body text here."'
    assert extract_body_from_command(command) == "Some body text here."


def test_extract_short_flag_shell_var_returns_none() -> None:
    """Short-flag shell variable like -b=$var cannot be resolved at hook time --
    the extractor returns None (unauditable). Literal -b="" still returns ""."""
    command = 'gh pr create --title "T" -b=$bodyVar'
    assert extract_body_from_command(command) is None


def test_extract_body_string_value_skips_body_file_path_token() -> None:
    command = 'gh pr create --body-file --body "actual text"'
    assert extract_body_from_command(command) is None


def test_get_logical_first_line_does_not_join_bash_command_substitution() -> None:
    command = 'VAR=`cmd`\ngh pr create --body "text"'
    assert get_logical_first_line(command) == "VAR=`cmd`"


def test_get_logical_first_line_joins_powershell_backtick_continuation() -> None:
    command = 'Some-Command -Param `\n"value"'
    assert get_logical_first_line(command) == 'Some-Command -Param "value"'


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


def test_read_body_file_rejects_relative_path_traversal(tmp_path, monkeypatch) -> None:
    _HOOK_DIR = pathlib.Path(__file__).parent
    if str(_HOOK_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOK_DIR))
    spec = importlib.util.spec_from_file_location(
        "pde", _HOOK_DIR / "pr_description_command_parser.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    sentinel_directory = tmp_path / "sentinel"
    sentinel_directory.mkdir()
    working_directory = tmp_path / "workdir"
    working_directory.mkdir()
    sentinel_file = sentinel_directory / "secret.txt"
    sentinel_file.write_text("secret")
    monkeypatch.chdir(working_directory)
    rel_path = os.path.relpath(str(sentinel_file))
    assert ".." in rel_path, "chdir to a sibling of the sentinel must produce a traversal relpath"
    with pytest.raises(m.PathTraversalError):
        m._read_body_file_contents(rel_path)


def test_read_body_file_allows_absolute_path_outside_cwd(tmp_path) -> None:
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        "pde2", _HOOK_DIR / "pr_description_command_parser.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    body_file = tmp_path / "body.md"
    body_file.write_text("hello")
    result = m._read_body_file_contents(str(body_file))
    assert result == "hello"


def test_reassemble_split_quoted_value_returns_none_for_unclosed_quote() -> None:
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        "pde3", _HOOK_DIR / "pr_description_command_parser.py"
    )
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
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        "pde_t", _HOOK_DIR / "pr_description_command_parser.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    result = m._resolve_body_file_value("../../../etc/passwd")
    assert result is None


def test_read_body_file_rejects_absolute_symlink_outside_cwd(tmp_path: pathlib.Path) -> None:
    """Absolute symlink pointing outside cwd must raise PathTraversalError."""
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        "pde_sym", _HOOK_DIR / "pr_description_command_parser.py"
    )
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
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        "pde_abs", _HOOK_DIR / "pr_description_command_parser.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    body_file = tmp_path / "body.md"
    body_file.write_text("hello body")
    result = m._read_body_file_contents(str(body_file))
    assert result == "hello body"


def test_read_body_file_allows_in_cwd_symlink_pointing_into_cwd(tmp_path: pathlib.Path) -> None:
    """Symlink inside cwd pointing to another file inside cwd must be readable."""
    _HOOK_DIR = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        "pde_inlink", _HOOK_DIR / "pr_description_command_parser.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    real_file = tmp_path / "real.md"
    real_file.write_text("real content")
    link_file = tmp_path / "link.md"
    try:
        link_file.symlink_to(real_file)
    except (OSError, NotImplementedError):
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
    with pytest.raises(ValueError):
        list(iter_significant_tokens('gh pr create --title="unclosed --body real_body'))


def test_scan_raw_tokens_does_not_false_match_body_in_title_value(tmp_path: pathlib.Path) -> None:
    """--title 'using --body-file is required' must not match --body-file inside the title value."""
    body_file = tmp_path / "real_body.md"
    body_file.write_text(VALID_BODY)
    command = f'gh pr create --title "using --body-file is required" --body-file {body_file}'
    result = extract_body_from_command(command)
    assert result == VALID_BODY


def test_scan_raw_tokens_for_body_docstring_reflects_none_for_shell_vars() -> None:
    """`_resolve_body_string_value` now returns `None` for unresolvable
    shell-variable bodies. `_scan_raw_tokens_for_body`'s docstring must
    reflect that contract so future maintainers do not treat `""` as the
    shell-var sentinel; literal-empty bodies still flow into validation."""
    source_text = inspect.getsource(hook_module._scan_raw_tokens_for_body)
    assert "None" in source_text, (
        f"docstring must mention None for shell-var case; got: {source_text!r}"
    )
    assert "shell var" in source_text.lower() or "shell-var" in source_text.lower(), (
        f"docstring must reference shell variables; got: {source_text!r}"
    )
    assert "may be empty for shell vars/sentinels" not in source_text, (
        'docstring must not claim `""` represents shell-var bodies; that case now returns None. '
        f"Source still contains the stale phrase: {source_text!r}"
    )


def test_stdlib_imports_form_one_isort_sorted_block() -> None:
    """Ruff's `I` (isort) rule treats a blank line as a section break, so
    `import shlex` sitting alone after a blank line would fail I001. Pin
    that the stdlib imports at the head of `pr_description_command_parser.py`
    sit in a single sorted block with no internal blank lines."""
    enforcer_source = inspect.getsource(hook_module)
    enforcer_lines = enforcer_source.splitlines()
    leading_stdlib_lines: list[str] = []
    for each_line in enforcer_lines:
        if each_line.startswith("import ") or each_line.startswith("from "):
            leading_stdlib_lines.append(each_line)
            continue
        if each_line.strip() == "":
            if leading_stdlib_lines and leading_stdlib_lines[-1].startswith("from "):
                break
            if leading_stdlib_lines:
                break
            continue
        if not each_line.startswith("import ") and not each_line.startswith("from ") and each_line.strip() != "":
            if leading_stdlib_lines:
                break
            continue
    stdlib_import_names: list[str] = []
    for each_import_line in leading_stdlib_lines:
        if each_import_line.startswith("import "):
            stdlib_import_names.append(each_import_line.split()[1])
    assert "shlex" in stdlib_import_names, (
        "`shlex` must appear in the leading stdlib import block; got: "
        f"{stdlib_import_names!r}"
    )
    assert stdlib_import_names == sorted(stdlib_import_names), (
        "Leading stdlib `import X` statements must be isort-sorted; got: "
        f"{stdlib_import_names!r}"
    )
