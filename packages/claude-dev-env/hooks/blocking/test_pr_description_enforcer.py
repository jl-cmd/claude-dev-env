"""Unit tests for pr-description-enforcer PreToolUse hook."""

import importlib.util
import inspect
import io
import json
import pathlib
import re as _re
import sys
from unittest.mock import patch

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

from blocking._gh_body_arg_utils import get_logical_first_line, iter_significant_tokens

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


@pytest.fixture(autouse=True)
def _isolate_readability_state(tmp_path_factory, monkeypatch):
    """Redirect the three readability state files to per-test temp paths for every test.

    Tests that need the strike-counter behavior re-monkeypatch the same attributes to a fresh
    directory where the enabled file is absent (which defaults to enabled=True). This default
    keeps the readability check off for every other test in the file.
    """
    per_test_state_dir = tmp_path_factory.mktemp("readability_state")
    strike_path = per_test_state_dir / "strikes.json"
    override_path = per_test_state_dir / "overrides.json"
    enabled_path = per_test_state_dir / "enabled.json"
    enabled_path.write_text(json.dumps({"enabled": False}))
    monkeypatch.setattr(hook_module, "READABILITY_STATE_FILE", strike_path)
    monkeypatch.setattr(hook_module, "READABILITY_THRESHOLD_OVERRIDE_FILE", override_path)
    monkeypatch.setattr(hook_module, "READABILITY_ENABLED_STATE_FILE", enabled_path)

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

LEGACY_DESCRIPTION_WHY_HOW_BODY = (
    "## Description\n\nFixes a real bug in the authentication module that affected production users.\n\n"
    "## Why\n\nThe defect surfaced in production and customers reported repeated sign-in failures.\n\n"
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


def test_validate_blocks_literal_empty_body() -> None:
    """A literal `gh pr create --body ""` must NOT skip enforcement. Empty-body
    extraction returns "" (distinct from shell-var's None), so the validator
    runs and blocks via the substantive-prose check. Conflating the two
    previously allowed `--body ""` to bypass validation entirely."""
    violations = validate_pr_body("")
    assert violations, (
        "Empty PR body must produce at least one violation (typically substantive "
        f"prose); got an empty list, which would let `--body \"\"` bypass enforcement."
    )


def test_validate_passes_anthropic_standard_body() -> None:
    assert validate_pr_body(VALID_BODY) == []


def test_validate_passes_legacy_description_why_how_body() -> None:
    """Existing Description/Why/How bodies must still pass -- the relaxed rule only widens what's accepted."""
    assert validate_pr_body(LEGACY_DESCRIPTION_WHY_HOW_BODY) == []


def test_validate_passes_sectionless_prose_body() -> None:
    """Anthropic's trivial-PR shape is one sentence with no headers."""
    body = (
        "Pin third-party GitHub Actions references to immutable commit SHAs "
        "so a tag move cannot redirect CI to attacker-controlled code."
    )
    assert validate_pr_body(body) == []


def test_validate_blocks_skeleton_body_with_only_headers_and_bullets() -> None:
    """Sections + bullets without any prose Why is rejected -- the substantive-prose check catches this."""
    body = (
        "## Summary\n\n"
        "## Changes\n\n"
        "- `a`\n"
        "- `b`\n"
        "- `c`\n"
    )
    violations = validate_pr_body(body)
    assert any("substantive prose" in each_violation.lower() for each_violation in violations)


def test_validate_blocks_blockquoted_headings_with_no_real_prose() -> None:
    """Regression: blockquote markers must strip BEFORE heading stripping.

    A line like `> ## Summary` starts with `>`, so `^#+[ \\t].*$` cannot match it
    in heading position. If blockquote markers are stripped after, the bare
    `## Summary` text survives into the prose stream and inflates the count.
    Correct order strips `> ` first, then the line becomes a real heading and
    drops out, leaving an effectively empty body below the 40-character minimum.
    """
    body = "> ## Summary\n> ## Why\n> ## How"
    violations = validate_pr_body(body)
    assert any("substantive prose" in each_violation.lower() for each_violation in violations)


def test_validate_passes_prose_after_bare_hashes_with_no_space() -> None:
    """Bug regression: `##\\n` followed by prose must not have its prose eaten by the heading regex.

    The previous pattern `^#+\\s.*$` matched `\\s` against the newline, then `.*$` greedily
    consumed the next line. The fix restricts the whitespace class to `[ \\t]` so only true
    headings (`## text`) match, leaving prose-after-bare-hashes intact for substantive-prose counting.
    """
    body = (
        "##\nThis is real prose that should not be eaten by the heading regex, "
        "it should pass the 40-character minimum."
    )
    assert validate_pr_body(body) == []


def test_validate_blocks_vague_language() -> None:
    body = VALID_BODY + "\nFixed bug in the auth module.\n"
    violations = validate_pr_body(body)
    assert any("Vague language" in each_violation for each_violation in violations)


def _has_vague_language_violation(all_violations: list[str]) -> bool:
    return any("Vague language" in each_violation for each_violation in all_violations)


def test_vague_language_inside_fenced_code_block_is_exempt() -> None:
    body = (
        "The allocator now bounds retries so a runaway request cannot exhaust the "
        "connection pool under sustained load.\n\n"
        "```bash\ngit commit -m \"fixed bug in parser\"\n```\n"
    )
    assert not _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_inside_inline_code_span_is_exempt() -> None:
    body = (
        "This change documents the historical commit message `fixed bug` referenced "
        "in the changelog and rewrites the surrounding allocator narrative for clarity.\n"
    )
    assert not _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_inside_blockquote_line_is_exempt() -> None:
    body = (
        "> The reviewer wrote: minor changes were requested here.\n\n"
        "The allocator rewrite removes the unbounded retry loop and adds a hard ceiling "
        "so a single client cannot starve the pool.\n"
    )
    assert not _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_inside_markdown_table_is_exempt() -> None:
    body = (
        "The commit-message guide contrasts weak and strong messages so contributors "
        "learn the difference before opening a pull request.\n\n"
        "| Bad message | Good message |\n"
        "| --- | --- |\n"
        "| fixed bug | bound retry loop in allocator |\n"
        "| update code | rename pool field to active_count |\n"
    )
    assert not _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_in_bare_prose_still_blocks() -> None:
    body = (
        "The allocator rewrite removes the unbounded retry loop and adds a hard "
        "ceiling so a single client cannot starve the pool. Fixed bug in the parser.\n"
    )
    assert _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_inside_heading_is_exempt() -> None:
    body = (
        "## Fixed bug in the allocator\n\n"
        "The allocator rewrite removes the unbounded retry loop and adds a hard "
        "ceiling so a single client cannot starve the connection pool.\n"
    )
    assert not _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_in_single_pipe_prose_line_still_blocks() -> None:
    body = (
        "The allocator rewrite removes the unbounded retry loop and adds a hard "
        "ceiling so a single client cannot starve the connection pool.\n\n"
        "| fixed bug\n"
    )
    assert _has_vague_language_violation(validate_pr_body(body))


def test_validate_blocks_short_body() -> None:
    violations = validate_pr_body("Too short.")
    assert any("substantive prose" in each_violation.lower() for each_violation in violations)


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


def test_read_body_file_rejects_relative_path_traversal(tmp_path, monkeypatch) -> None:
    import importlib.util, pathlib, sys
    _HOOK_DIR = pathlib.Path(__file__).parent
    if str(_HOOK_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOK_DIR))
    spec = importlib.util.spec_from_file_location('pde', _HOOK_DIR / 'pr_description_enforcer.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    import os, pytest
    sentinel_directory = tmp_path / 'sentinel'
    sentinel_directory.mkdir()
    working_directory = tmp_path / 'workdir'
    working_directory.mkdir()
    sentinel_file = sentinel_directory / 'secret.txt'
    sentinel_file.write_text('secret')
    monkeypatch.chdir(working_directory)
    rel_path = os.path.relpath(str(sentinel_file))
    assert '..' in rel_path, 'chdir to a sibling of the sentinel must produce a traversal relpath'
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
    with pytest.raises(ValueError):
        list(iter_significant_tokens('gh pr create --title="unclosed --body real_body'))


def test_scan_raw_tokens_does_not_false_match_body_in_title_value(tmp_path: pathlib.Path) -> None:
    """--title 'using --body-file is required' must not match --body-file inside the title value."""
    body_file = tmp_path / "real_body.md"
    body_file.write_text(VALID_BODY)
    command = f'gh pr create --title "using --body-file is required" --body-file {body_file}'
    result = extract_body_from_command(command)
    assert result == VALID_BODY


def _build_heavy_body(opening_header: str, testing_header: str) -> str:
    intro_text = (
        "Adds shape-aware validation across the pr-description-enforcer pipeline. "
        "The change unifies the body audit with the Anthropic claude-code style "
        "so heavy PRs carry both an opening header and a testing header."
    )
    return (
        f"{intro_text}\n\n"
        f"{opening_header}\n\n"
        "The earlier flow rejected too many valid bodies on equivalence checks "
        "across the three shape categories described in the guide. The fix "
        "restructures the path around shape detection and surfaces the missing "
        "category in the block message so the agent can correct it on first try.\n\n"
        f"{testing_header}\n\n"
        "- `pytest packages/claude-dev-env/hooks/blocking/test_pr_description_enforcer.py`\n"
        "- Manual smoke test against the implementation PR with a sample heavy body\n"
        "- Run the readability check across the full corpus to confirm thresholds hold\n"
    )


def test_compute_pr_body_shape_trivial() -> None:
    """A short single-sentence body with zero headers classifies as Trivial."""
    body = "Pin third-party GitHub Actions references to immutable commit SHAs."
    assert hook_module._compute_pr_body_shape(body) == "trivial"


def test_compute_pr_body_shape_standard() -> None:
    """A medium body with one ## header below the Heavy threshold classifies as Standard."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits. The pull engine compares the last-modified marker "
        "before deciding whether to apply a remote record.\n\n"
        "## Changes\n\n"
        "- `pullEngine.ts`: compare lastModified before overwriting\n"
        "- `pullEngine.test.ts`: 3 new cases\n"
    )
    assert hook_module._compute_pr_body_shape(body) == "standard"


def test_compute_pr_body_shape_heavy() -> None:
    """A long body with two Heavy-detection headers classifies as Heavy."""
    body = _build_heavy_body("## Problem", "## Test plan")
    assert hook_module._compute_pr_body_shape(body) == "heavy"


def test_validate_heavy_body_passes_with_problem_and_test_plan() -> None:
    body = _build_heavy_body("## Problem", "## Test plan")
    assert validate_pr_body(body) == []


def test_validate_heavy_body_blocks_when_testing_category_missing() -> None:
    """Heavy body containing two opening-category headers but no testing-category header is blocked."""
    intro_text = (
        "Adds shape-aware validation across the pr-description-enforcer pipeline. "
        "The change unifies the body audit with the Anthropic claude-code style. "
        "The block reason names the missing category for the agent to fix on first try."
    )
    body = (
        f"{intro_text}\n\n"
        "## Summary\n\n"
        "Adds a check that heavy bodies carry both an opening header and a testing header. "
        "The substantive prose lives outside the bullet section so the audit treats the body "
        "as the heavy shape rather than the standard shape under the length threshold.\n\n"
        "## Problem\n\n"
        "The earlier flow rejected too many valid bodies on equivalence checks "
        "across the three shape categories described in the guide. The fix "
        "restructures the path around shape detection and surfaces the missing "
        "category in the block message so the agent can correct it without iterating.\n\n"
        "## Changes\n\n"
        "- `validator.py`: shape detection at the head of the audit pipeline\n"
        "- `enforcer.py`: dispatch the shape-aware checks before the substantive-prose audit\n"
    )
    violations = validate_pr_body(body)
    assert any("testing" in each_violation.lower() for each_violation in violations)


def test_validate_trivial_body_blocks_summary_header() -> None:
    """A Trivial-sized body that opens with `## Summary` is blocked as ceremony."""
    body = "## Summary\n\nPin Bun to 1.3.14."
    violations = validate_pr_body(body)
    assert any(
        "ceremony" in each_violation.lower() or "trivial" in each_violation.lower()
        for each_violation in violations
    )


def test_validate_trivial_body_blocks_test_plan_header() -> None:
    """A Trivial-sized body that opens with `## Test plan` must trip the
    ceremony-on-Trivial block. The guide says Trivial bodies have zero headers,
    so the enforcer must catch every heading variant — not just the six
    `Summary|Why|Overview|Description|Intro|TL;DR` originally enumerated."""
    body = "## Test plan\n\nPin Bun to 1.3.14."
    violations = validate_pr_body(body)
    assert any(
        "ceremony" in each_violation.lower() or "trivial" in each_violation.lower()
        for each_violation in violations
    ), f"Trivial body opening with `## Test plan` must trip ceremony block; got {violations!r}"


def test_first_non_empty_line_helper_is_removed() -> None:
    """`_first_non_empty_line` was the basis of the prior ceremony-on-Trivial
    check, which now uses `_iter_section_headers`. The helper has no remaining
    call sites; pin its removal so it cannot drift back as dead code."""
    assert not hasattr(hook_module, "_first_non_empty_line"), (
        "_first_non_empty_line must be removed; the ceremony-on-Trivial check "
        "now reads through _iter_section_headers instead."
    )


def test_validate_trivial_body_blocks_test_plan_after_prose() -> None:
    """The doc promises "Zero `##` headers" on Trivial bodies. The earlier check
    only inspected the first non-empty line, so prose followed by `## Test plan`
    slipped through. Tighten the check to reject ANY heading in a Trivial-sized
    body so the guide and the enforcer agree."""
    body = (
        "Pin Bun to 1.3.14.\n\n"
        "## Test plan\n\n"
        "- bun test\n"
    )
    violations = validate_pr_body(body)
    assert any(
        "ceremony" in each_violation.lower() or "trivial" in each_violation.lower()
        for each_violation in violations
    ), f"Trivial body with later `## Test plan` must trip the block; got {violations!r}"


def test_validate_trivial_body_blocks_h1_header() -> None:
    """A Trivial-sized body opening with an `# Overview` h1 must also block, since
    Trivial shape allows zero structural headers of any level."""
    body = "# Overview\n\nPin Bun to 1.3.14."
    violations = validate_pr_body(body)
    assert any(
        "ceremony" in each_violation.lower() or "trivial" in each_violation.lower()
        for each_violation in violations
    ), f"Trivial body opening with h1 must trip ceremony block; got {violations!r}"


def test_validate_standard_body_allows_summary_header() -> None:
    """A Standard-sized body that opens with `## Summary` passes the ceremony check."""
    body = (
        "## Summary\n\n"
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits. The pull engine compares the last-modified marker "
        "before applying a remote record.\n\n"
        "## Changes\n\n"
        "- `pullEngine.ts`: compare lastModified before overwriting\n"
        "- `pullEngine.test.ts`: 3 new cases\n"
    )
    violations = validate_pr_body(body)
    assert not any(
        "ceremony" in each_violation.lower() or "trivial" in each_violation.lower()
        for each_violation in violations
    )


def test_validate_blocks_self_closing_fixes_reference() -> None:
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nFixes #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    )


def test_validate_blocks_self_closing_resolves_reference() -> None:
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nResolves #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    )


def test_validate_blocks_lowercase_self_closing_fixes_reference() -> None:
    """GitHub treats closing keywords (Fixes/Closes/Resolves) case-insensitively, so
    a body opening with `fixes #<own-PR>` (lowercase) auto-closes the PR on merge
    just like the capitalized form. The enforcer must catch both."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nfixes #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    ), f"lowercase fixes self-reference must trip the block; got {violations!r}"


def test_validate_blocks_self_closing_fix_singular_reference() -> None:
    """GitHub recognizes nine closing keywords (close/closes/closed,
    fix/fixes/fixed, resolve/resolves/resolved). The bare-stem variants
    `Fix #N`, `Close #N`, `Resolve #N` close the PR on merge just like the
    plural forms, so the enforcer must catch every variant."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nFix #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    ), f"`Fix #<own-PR>` self-reference must trip the block; got {violations!r}"


def test_validate_blocks_self_closing_closed_past_tense_reference() -> None:
    """`Closed #<own-PR>` (past tense) closes the PR on merge; the enforcer
    must catch every closing-keyword variant including past tense."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nClosed #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    ), f"`Closed #<own-PR>` self-reference must trip the block; got {violations!r}"


def test_validate_blocks_self_closing_resolved_past_tense_reference() -> None:
    """`Resolved #<own-PR>` closes the PR on merge."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nResolved #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    ), f"`Resolved #<own-PR>` self-reference must trip the block; got {violations!r}"


def test_validate_blocks_uppercase_self_closing_closes_reference() -> None:
    """All-caps `CLOSES #<own-PR>` also auto-closes on GitHub; the enforcer must
    catch every case variant the same way GitHub does."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nCLOSES #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    ), f"all-caps CLOSES self-reference must trip the block; got {violations!r}"


def test_validate_allows_fixes_reference_to_different_pr() -> None:
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nFixes #467.\n"
    )
    violations = validate_pr_body(body, pr_number=999)
    assert not any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    )


def test_validate_blocks_this_pr_opening() -> None:
    body = (
        "This PR adds a timestamp check to prevent background data pulls from "
        "overwriting recent local edits. The pull engine compares the "
        "last-modified marker before applying a remote record."
    )
    violations = validate_pr_body(body)
    assert any("this pr" in each_violation.lower() for each_violation in violations)


def test_validate_blocks_this_pr_opening_with_non_allowlisted_verb() -> None:
    """The guide describes any `This PR ...` opening as a hard block, but
    `THIS_PR_OPENING_PATTERN` previously only matched a short allowlist of
    verbs (adds|fixes|updates|does|is|was|will|removes|tightens|ports|refactors).
    Variants like `This PR introduces`, `This PR improves`, `This PR enables`
    slipped through and broke the documented contract. Catch any
    `This PR` opening regardless of the following verb."""
    body = (
        "This PR introduces a multi-tier caching layer that wraps the existing "
        "request pipeline and improves median latency on the hot path."
    )
    violations = validate_pr_body(body)
    assert any("this pr" in each_violation.lower() for each_violation in violations), (
        f"`This PR introduces` opening must trip the block regardless of verb; got {violations!r}"
    )


def test_validate_blocks_this_pr_opening_with_improves() -> None:
    body = (
        "This PR improves the request batching algorithm so the dispatcher "
        "coalesces idempotent calls before the network round-trip."
    )
    violations = validate_pr_body(body)
    assert any("this pr" in each_violation.lower() for each_violation in violations), (
        f"`This PR improves` opening must trip the block; got {violations!r}"
    )


def test_validate_allows_imperative_opening() -> None:
    body = (
        "Adds a timestamp check to prevent background data pulls from "
        "overwriting recent local edits. The pull engine compares the "
        "last-modified marker before applying a remote record."
    )
    violations = validate_pr_body(body)
    assert not any("this pr" in each_violation.lower() for each_violation in violations)


def _readability_failing_body() -> str:
    """A Heavy-classified body whose intro sentence dramatically exceeds the
    max-sentence-words threshold. Wraps the long sentence in `## Problem` and
    `## Test plan` headers so the Heavy required-header check is satisfied
    and only the readability violation fires; otherwise the missing-header
    violations would inflate the result list and mask readability regressions
    behind broad `any()` substring matches."""
    return (
        "## Problem\n\n"
        "Adds a multi-step coordination protocol that traverses the entire "
        "request lifecycle through every middleware layer in the system, ensuring that "
        "downstream consumers observe a perfectly consistent ordering guarantee across "
        "all participating subsystems including the queueing component and the storage "
        "subsystem and the notification dispatch path that fans out to subscribers "
        "across every channel registered against the tenant scope including email and "
        "push and webhook delivery surfaces simultaneously in one transactional unit.\n\n"
        "## Test plan\n\n"
        "- `pytest packages/claude-dev-env/hooks/blocking/test_pr_description_enforcer.py`\n"
    )


def test_readability_strike_one_emits_metric_violation(readability_state_paths_enabled) -> None:
    body = _readability_failing_body()
    violations = validate_pr_body(body)
    assert any(
        "readability" in each_violation.lower() or "sentence" in each_violation.lower()
        for each_violation in violations
    )
    assert not any(
        "--readability-loosen" in each_violation for each_violation in violations
    )
    assert hook_module._read_strike_count() == 1


def test_readability_strike_two_still_metric_violation(readability_state_paths_enabled) -> None:
    body = _readability_failing_body()
    validate_pr_body(body)
    violations = validate_pr_body(body)
    assert hook_module._read_strike_count() == 2
    assert not any("--readability-loosen" in each_violation for each_violation in violations)


def test_readability_strike_three_fires_escape_hatch(readability_state_paths_enabled) -> None:
    body = _readability_failing_body()
    validate_pr_body(body)
    validate_pr_body(body)
    violations = validate_pr_body(body)
    assert hook_module._read_strike_count() == 3
    assert any("--readability-loosen" in each_violation for each_violation in violations)
    assert any("--readability-disable" in each_violation for each_violation in violations)
    assert any("--readability-reset" in each_violation for each_violation in violations)


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


def test_loosen_cap_errors_on_fourth_invocation(readability_state_paths_enabled) -> None:
    assert hook_module._apply_readability_loosen() == "ok"
    assert hook_module._apply_readability_loosen() == "ok"
    assert hook_module._apply_readability_loosen() == "ok"
    fourth_outcome = hook_module._apply_readability_loosen()
    assert fourth_outcome == "cap_reached"


def test_loosen_flesch_floor_cap_errors(readability_state_paths_enabled) -> None:
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    floor_value = hook_module.READABILITY_MIN_FLESCH_FLOOR
    payload = {
        "flesch_min": floor_value,
        "max_sentence_words": 30,
        "avg_sentence_words": 20,
        "loosens_used": 0,
    }
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(payload))
    assert hook_module._apply_readability_loosen() == "floor_reached"


def test_loosen_max_sentence_ceiling_cap_errors(readability_state_paths_enabled) -> None:
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    ceiling_value = hook_module.READABILITY_MAX_SENTENCE_WORDS_CEILING
    payload = {
        "flesch_min": 50,
        "max_sentence_words": ceiling_value,
        "avg_sentence_words": 20,
        "loosens_used": 0,
    }
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(payload))
    assert hook_module._apply_readability_loosen() == "ceiling_reached"


def test_loosen_avg_sentence_ceiling_cap_errors(readability_state_paths_enabled) -> None:
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    ceiling_value = hook_module.READABILITY_AVG_SENTENCE_WORDS_CEILING
    payload = {
        "flesch_min": 50,
        "max_sentence_words": 30,
        "avg_sentence_words": ceiling_value,
        "loosens_used": 0,
    }
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(payload))
    assert hook_module._apply_readability_loosen() == "ceiling_reached"


def test_strip_leading_hash_lines_helper_is_removed() -> None:
    """The unused leading-hash stripper must not exist as a module attribute."""
    assert not hasattr(hook_module, "_strip_leading_hash_lines")


def test_strip_markdown_ceremony_returns_stripped_prose() -> None:
    """The shared markdown stripper removes fences, inline code, blockquotes,
    headings, bullets, bold, emphasis, and Markdown link targets, leaving the
    underlying prose intact."""
    body = "\n".join(
        [
            "# Heading text",
            "> blockquoted content",
            "- bullet content",
            "**bold body**",
            "*emphasized body*",
            "[link label](https://example.com)",
            "`inline code body`",
            "```",
            "fenced code body",
            "```",
            "plain prose line",
        ]
    )
    stripped = hook_module._strip_markdown_ceremony(body)
    assert "Heading text" not in stripped
    assert "blockquoted content" in stripped
    assert "bullet content" in stripped
    assert "bold body" in stripped
    assert "emphasized body" in stripped
    assert "link label" in stripped
    assert "plain prose line" in stripped
    assert "inline code body" not in stripped
    assert "fenced code body" not in stripped
    assert "https://example.com" not in stripped


def test_strip_markdown_ceremony_used_by_substantive_prose_count() -> None:
    """_count_substantive_prose_chars is consistent with the shared stripper:
    its returned count matches len of the whitespace-collapsed stripped body."""
    body = "# Heading\n\nA single paragraph of prose with **bold** and `code` words."
    stripped = hook_module._strip_markdown_ceremony(body)
    collapsed = _re.sub(r"\s+", " ", stripped).strip()
    assert hook_module._count_substantive_prose_chars(body) == len(collapsed)


def test_threshold_override_file_widens_max_sentence_words(readability_state_paths_enabled) -> None:
    """When max_sentence_words override is 50, the loaded thresholds reflect that value."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    payload = {
        "flesch_min": 30,
        "max_sentence_words": 50,
        "avg_sentence_words": 40,
        "loosens_used": 0,
    }
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(payload))
    thresholds = hook_module._load_readability_thresholds()
    assert thresholds.max_sentence_words == 50
    assert thresholds.flesch_min == 30
    assert thresholds.avg_sentence_words == 40


def test_loosen_writes_expected_scaled_thresholds(readability_state_paths_enabled) -> None:
    """First loosen invocation scales flesch by 0.9 and sentence widths by 10/9."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    assert hook_module._apply_readability_loosen() == "ok"
    written_payload = json.loads(override_path.read_text())
    assert written_payload["flesch_min"] == 45
    assert written_payload["max_sentence_words"] == 32
    assert written_payload["avg_sentence_words"] == 20
    assert written_payload["loosens_used"] == 1


def test_dispatch_loosen_writes_success_to_output_stream(readability_state_paths_enabled) -> None:
    """The loosen handler writes its success message to the supplied output stream."""
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        hook_module._dispatch_cli_flag(
            "--readability-loosen",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 0
    assert "readability thresholds loosened 10%\n" == output_stream.getvalue()
    assert error_stream.getvalue() == ""


def test_dispatch_loosen_cap_writes_to_error_stream(readability_state_paths_enabled) -> None:
    """When the loosen cap is hit, the handler writes the corrective message to error stream."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps({"loosens_used": hook_module.READABILITY_LOOSEN_CAP}))
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        hook_module._dispatch_cli_flag(
            "--readability-loosen",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 1
    assert "loosen cap reached" in error_stream.getvalue()
    assert output_stream.getvalue() == ""


def test_dispatch_loosen_floor_writes_to_error_stream(readability_state_paths_enabled) -> None:
    """When the floor is reached, the handler writes the corrective message to error stream."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    floor_payload = {
        "flesch_min": hook_module.READABILITY_MIN_FLESCH_FLOOR,
        "max_sentence_words": 30,
        "avg_sentence_words": 20,
        "loosens_used": 0,
    }
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps(floor_payload))
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        hook_module._dispatch_cli_flag(
            "--readability-loosen",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 1
    assert "floor/ceiling" in error_stream.getvalue()
    assert output_stream.getvalue() == ""


def test_dispatch_reset_writes_success_to_output_stream(readability_state_paths_enabled) -> None:
    """The reset handler writes its success message to the supplied output stream."""
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        hook_module._dispatch_cli_flag(
            "--readability-reset",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 0
    assert "readability strike counter and override thresholds reset\n" == output_stream.getvalue()
    assert error_stream.getvalue() == ""


def test_dispatch_disable_writes_success_to_output_stream(readability_state_paths_enabled) -> None:
    """The disable handler writes its success message to the supplied output stream."""
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        hook_module._dispatch_cli_flag(
            "--readability-disable",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 0
    assert "readability check disabled\n" == output_stream.getvalue()
    assert error_stream.getvalue() == ""


def test_dispatch_enable_writes_success_to_output_stream(readability_state_paths_enabled) -> None:
    """The enable handler writes its success message to the supplied output stream."""
    output_stream = io.StringIO()
    error_stream = io.StringIO()
    with pytest.raises(SystemExit) as exit_info:
        hook_module._dispatch_cli_flag(
            "--readability-enable",
            output_stream=output_stream,
            error_stream=error_stream,
        )
    assert exit_info.value.code == 0
    assert "readability check enabled\n" == output_stream.getvalue()
    assert error_stream.getvalue() == ""


def test_shape_classifier_uses_substantive_chars_not_raw_length() -> None:
    """Shape classifier and ceremony-on-Trivial check must agree on the metric used
    against TRIVIAL_BODY_CHAR_THRESHOLD. A body whose raw length passes the
    threshold but whose substantive prose does not (e.g. tiny prose with a large
    fenced code block) is genuinely Trivial in shape -- not Standard."""
    tiny_prose_with_large_code_fence = "Done.\n\n```\n" + ("x" * 300) + "\n```"
    assert len(tiny_prose_with_large_code_fence) >= hook_module.TRIVIAL_BODY_CHAR_THRESHOLD
    assert hook_module._count_substantive_prose_chars(tiny_prose_with_large_code_fence) < hook_module.TRIVIAL_BODY_CHAR_THRESHOLD
    assert hook_module._compute_pr_body_shape(tiny_prose_with_large_code_fence) == "trivial"


def _build_main_hook_input(command: str) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def _run_main_and_capture_decision(hook_input: dict[str, object]) -> str:
    captured_stdout = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(hook_input))):
        with patch("sys.stdout", captured_stdout):
            try:
                hook_module.main()
            except SystemExit:
                pass
    return captured_stdout.getvalue()


def test_body_contains_any_header_rejects_plural_extension() -> None:
    """`_body_contains_any_header` must enforce a word boundary after the
    canonical header text. `## Problems` (plural) extends the canonical
    word and must NOT satisfy `## Problem`, otherwise the Heavy
    required-header check is weaker than the documented contract."""
    body_with_plural_extension = "## Problems\n\nDetails follow."
    candidate_set = frozenset({"## Problem"})
    assert not hook_module._body_contains_any_header(body_with_plural_extension, candidate_set), (
        "`## Problems` must NOT satisfy `## Problem` (different header)"
    )


def test_body_contains_any_header_accepts_punctuation_suffix() -> None:
    """The boundary rule must still accept canonical headers followed by
    non-word punctuation: colon, em-dash, parenthesis, trailing whitespace.
    Reviewers write `## Problem (context)` and `## Test plan: scope` —
    these must continue to satisfy the canonical headers."""
    candidate_set = frozenset({"## Problem"})
    for each_body in [
        "## Problem\n\nDetails.",
        "## Problem:\n\nDetails.",
        "## Problem (context)\n\nDetails.",
        "## Problem — context\n\nDetails.",
    ]:
        assert hook_module._body_contains_any_header(each_body, candidate_set), (
            f"`{each_body!r}` must satisfy `## Problem` (punctuation/space follows)"
        )


def test_body_contains_any_header_rejects_alphanumeric_suffix() -> None:
    """`## Problem2`, `## ProblemX`, `## Problem_one` are different headers
    and must not match `## Problem`."""
    candidate_set = frozenset({"## Problem"})
    for each_body in [
        "## Problem2\n\nDetails.",
        "## ProblemX\n\nDetails.",
        "## Problem_one\n\nDetails.",
    ]:
        assert not hook_module._body_contains_any_header(each_body, candidate_set), (
            f"`{each_body!r}` must NOT satisfy `## Problem` (alphanumeric continuation)"
        )


def test_read_strike_count_clamps_negative_to_zero(readability_state_paths_enabled) -> None:
    """A corrupted strike-count JSON state with a negative integer must not
    silently bypass escalation. Reads clamp to >= 0 so subsequent increments
    walk the strike threshold from a sane baseline."""
    strike_path, _override_path, _enabled_path = readability_state_paths_enabled
    strike_path.parent.mkdir(parents=True, exist_ok=True)
    strike_path.write_text(json.dumps({"strikes": -5}))
    assert hook_module._read_strike_count() == 0, (
        "negative strikes must clamp to 0"
    )


def test_increment_strike_count_clamps_negative_starting_value(readability_state_paths_enabled) -> None:
    """`_increment_strike_count` must not propagate a corrupted negative
    starting value. The new count after one increment from a negative
    baseline is exactly 1, not (negative + 1)."""
    strike_path, _override_path, _enabled_path = readability_state_paths_enabled
    strike_path.parent.mkdir(parents=True, exist_ok=True)
    strike_path.write_text(json.dumps({"strikes": -3}))
    new_count_after_increment = hook_module._increment_strike_count()
    assert new_count_after_increment == 1, (
        f"increment from negative starting value must clamp first; got {new_count_after_increment}"
    )


def test_read_loosens_used_clamps_negative_to_zero(readability_state_paths_enabled) -> None:
    """A corrupted `loosens_used` JSON state with a negative integer must
    not silently bypass the loosen cap. Reads clamp to >= 0 so the cap
    check enforces the documented ceiling."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(json.dumps({"loosens_used": -2}))
    assert hook_module._read_loosens_used() == 0, (
        "negative loosens_used must clamp to 0"
    )


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
        "docstring must not claim `\"\"` represents shell-var bodies; that case now returns None. "
        f"Source still contains the stale phrase: {source_text!r}"
    )


def test_stdlib_imports_form_one_isort_sorted_block() -> None:
    """Ruff's `I` (isort) rule treats a blank line as a section break, so
    `import shlex` sitting alone after a blank line would fail I001. Pin
    that the stdlib imports at the head of `pr_description_enforcer.py`
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
        if not each_line.startswith("import ") and not each_line.startswith("from ") and each_line.strip() != "":
            break
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


def test_command_carries_body_flag_detects_body_file() -> None:
    """`--body-file` detection must continue to work after the redundant
    explicit check is removed. The shorter `--body` substring still catches
    `--body-file` because `--body` is a prefix of `--body-file`."""
    assert hook_module._command_carries_body_flag('gh pr create --body-file body.md')
    assert hook_module._command_carries_body_flag('gh pr create --body-file=body.md')
    assert hook_module._command_carries_body_flag('gh pr edit 1 -F body.md')
    assert hook_module._command_carries_body_flag('gh pr edit 1 -F=body.md')


def test_command_carries_body_flag_does_not_double_check_body_file() -> None:
    """Pin that the function does NOT execute a redundant `--body-file in command`
    check. `--body` is a substring of `--body-file`, so the longer form is
    matched implicitly by the shorter check. Pin the source so the dead branch
    cannot drift back."""
    source_text = inspect.getsource(hook_module._command_carries_body_flag)
    assert source_text.count('"--body-file"') == 0, (
        f"`--body-file` substring check is redundant with `--body`; remove it. Source:\n{source_text}"
    )


def test_main_blocks_gh_pr_edit_short_body_flag() -> None:
    """gh pr edit 123 -b "short" must be caught -- the short -b flag is a valid alias for --body."""
    command = 'gh pr edit 123 -b "Too short."'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output
    assert "substantive prose" in decision_output.lower()


def test_main_blocks_gh_pr_edit_body_file_short_flag(tmp_path) -> None:
    """gh pr edit 123 -F body.md must be caught -- -F is the short alias for --body-file."""
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    command = f'gh pr edit 123 -F {body_file}'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output
    assert "substantive prose" in decision_output.lower()


def test_main_blocks_gh_pr_edit_body_file_long_flag(tmp_path) -> None:
    """gh pr edit 123 --body-file body.md must also be caught (was missing from is_pr_edit detection)."""
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    command = f'gh pr edit 123 --body-file {body_file}'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output


def test_main_blocks_gh_pr_create_body_file_short_flag(tmp_path) -> None:
    """gh pr create -F body.md must be caught -- -F is the short alias for --body-file."""
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    command = f'gh pr create --title "T" -F {body_file}'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output


def test_main_blocks_gh_pr_create_body_file_long_flag(tmp_path) -> None:
    """gh pr create --body-file body.md must be caught -- was missing from is_pr_create detection."""
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    command = f'gh pr create --title "T" --body-file {body_file}'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output


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
    command = 'gh pr edit --body-file body.md 472'
    assert hook_module._extract_pr_number_from_command(command) == 472


def test_extract_pr_number_skips_body_file_short_flag_value() -> None:
    """gh pr edit -F body.md 472 must return 472 -- -F short alias must also skip its value."""
    command = 'gh pr edit -F body.md 472'
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
    assert hook_module._command_carries_body_flag('gh pr edit 123 -F=body.md') is True


def test_main_blocks_gh_pr_edit_short_body_equals_form() -> None:
    """gh pr edit 123 -b="short" must be caught -- the -b= equals form was bypassing
    the pre-filter and silently approving short bodies."""
    command = 'gh pr edit 123 -b="Too short."'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output
    assert "substantive prose" in decision_output.lower()


def test_main_blocks_gh_pr_edit_short_body_file_equals_form(tmp_path) -> None:
    """gh pr edit 123 -F=body.md must be caught -- the -F= equals form was bypassing the pre-filter."""
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    command = f'gh pr edit 123 -F={body_file}'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output


def test_iter_section_headers_ignores_headings_inside_fenced_code_blocks() -> None:
    """Headings nested inside ``` ... ``` fences are example content, not body headers.
    The shape classifier and the Heavy required-header check must agree with the markdown
    stripper -- the body of this very test demonstrates the regression."""
    body = (
        "Intro paragraph that does not classify the body.\n\n"
        "```\n"
        "## Problem\n"
        "## Test plan\n"
        "```\n"
    )
    headers = hook_module._iter_section_headers(body)
    assert headers == [], f"Expected zero headers (fenced content), got {headers}"
    assert hook_module._compute_pr_body_shape(body) != "heavy", (
        "Body with only fenced example headers must not classify as heavy"
    )
    assert hook_module._body_contains_any_header(
        body, hook_module.ALL_HEAVY_OPENING_HEADERS
    ) is False, "Heavy opening-header check must not see fenced example content"


def test_build_short_failing_body_helper_is_removed() -> None:
    """The unused test helper `_build_short_failing_body` had zero call sites and
    must not be re-introduced."""
    test_module = sys.modules[__name__]
    assert not hasattr(test_module, "_build_short_failing_body"), (
        "_build_short_failing_body was re-introduced; it has no callers in this test file."
    )


def test_strike_count_rejects_boolean_value_as_strikes(readability_state_paths_enabled) -> None:
    """A corrupted strikes.json with `{"strikes": true}` must not be silently
    accepted as the integer 1. Python's `bool` is a subclass of `int`, so a bare
    `isinstance(value, int)` guard lets a malformed payload disable strike
    behavior without warning. The reader must explicitly exclude bool values."""
    strike_path, _override_path, _enabled_path = readability_state_paths_enabled
    strike_path.write_text('{"strikes": true}')
    assert hook_module._read_strike_count() == 0


def test_loosens_used_rejects_boolean_value(readability_state_paths_enabled) -> None:
    """`{"loosens_used": true}` must read as the default 0, not coerce the bool
    to 1 via the `isinstance(x, int)` quirk that accepts bool."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    override_path.write_text('{"loosens_used": true}')
    assert hook_module._read_loosens_used() == 0


def test_readability_thresholds_reject_boolean_values(readability_state_paths_enabled) -> None:
    """A threshold field set to a boolean must fall back to the default integer,
    not silently coerce True to 1 or False to 0 via Python's bool-is-int quirk."""
    _strike_path, override_path, _enabled_path = readability_state_paths_enabled
    override_path.write_text(
        '{"flesch_min": true, "max_sentence_words": false, "avg_sentence_words": true}'
    )
    thresholds = hook_module._load_readability_thresholds()
    assert thresholds.flesch_min == hook_module.DEFAULT_READABILITY_THRESHOLDS.flesch_min
    assert thresholds.max_sentence_words == hook_module.DEFAULT_READABILITY_THRESHOLDS.max_sentence_words
    assert thresholds.avg_sentence_words == hook_module.DEFAULT_READABILITY_THRESHOLDS.avg_sentence_words


def test_single_use_helper_constants_are_inlined() -> None:
    """`_vowel_set`, `_sentence_split_pattern`, and `_all_cli_flag_tokens` each
    had exactly one consumer in production. The file-global-constants rule
    requires either a second caller or a move out of module scope; inlining
    into the single consumer is the chosen resolution. Pin that the three
    names are no longer module attributes so they cannot drift back."""
    for each_name in ("_vowel_set", "_sentence_split_pattern", "_all_cli_flag_tokens"):
        assert not hasattr(hook_module, each_name), (
            f"{each_name} must be inlined into its single consumer, not "
            "carried as a file-global constant."
        )


def test_readability_violation_strings_match_agent_doc_format() -> None:
    """The agent SKILL example shows the canonical readability message format
    (`Readability: longest sentence is N words (maximum 28); split or rewrite
    the longest sentence`). The hook's `_evaluate_readability_metrics` must
    emit the same `maximum N` / `split or rewrite` wording so users see the
    exact form documented in the agent file."""
    text_with_long_sentence = (
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
        "nu xi omicron pi rho sigma tau upsilon phi chi psi omega aleph "
        "beth gimel daleth he waw zayin heth teth yodh kaph lamedh mem nun."
    )
    messages_via_eval = hook_module._evaluate_readability_metrics(
        text_with_long_sentence, hook_module.DEFAULT_READABILITY_THRESHOLDS
    )
    joined_messages = "\n".join(messages_via_eval)
    assert "(maximum" in joined_messages, (
        f"Readability messages must use `maximum N` wording (matching agent doc); "
        f"got: {joined_messages!r}"
    )
    assert "split or rewrite the longest sentence" in joined_messages, (
        f"Longest-sentence message must end with `split or rewrite the longest sentence`; "
        f"got: {joined_messages!r}"
    )


def test_long_body_without_heavy_headers_still_classifies_heavy() -> None:
    """The Heavy required-header check in `validate_pr_body` only runs when
    `_compute_pr_body_shape` returns HEAVY. Previously the classifier required
    BOTH length >= 500 chars AND >= 2 heavy detection headers, which meant a
    long body missing the required headers entirely was classified Standard
    and silently bypassed the missing-header enforcement. Length alone must
    drive the HEAVY classification so the validator can enforce the rule."""
    long_body_with_no_heavy_headers = (
        "Refactors the request-pipeline batcher to coalesce idempotent calls "
        "before the network round-trip. The change touches the dispatcher, the "
        "retry loop, the error normalizer, and three downstream consumers. "
        "Every test in the integration suite continues to pass without "
        "modification because the public contract is unchanged.\n\n"
        "The new coalescer reads a per-call digest, looks up an in-flight slot "
        "indexed by that digest, and appends the caller's promise to the slot "
        "instead of dispatching a duplicate request. Once the network response "
        "arrives, every queued promise resolves with the same value. Error "
        "responses propagate to every queued promise so retry logic stays "
        "consistent with the prior contract.\n"
    )
    assert (
        hook_module._count_substantive_prose_chars(long_body_with_no_heavy_headers)
        >= hook_module.HEAVY_MIN_BODY_CHARS_FOR_CLASSIFICATION
    )
    assert hook_module._compute_pr_body_shape(long_body_with_no_heavy_headers) == hook_module.HEAVY_SHAPE


def test_validate_heavy_body_without_required_headers_blocks() -> None:
    """End-to-end: a long body without `## Problem|Summary` or `## Test plan|...`
    must trip the Heavy missing-header violation. Previously the classifier
    bypassed Heavy classification because the body lacked the headers we were
    trying to require — a circular self-bypass."""
    long_body_missing_heavy_headers = (
        "Refactors the request-pipeline batcher to coalesce idempotent calls "
        "before the network round-trip. The change touches the dispatcher, the "
        "retry loop, the error normalizer, and three downstream consumers. "
        "Every test in the integration suite continues to pass without "
        "modification because the public contract is unchanged.\n\n"
        "The new coalescer reads a per-call digest, looks up an in-flight slot "
        "indexed by that digest, and appends the caller's promise to the slot "
        "instead of dispatching a duplicate request. Once the network response "
        "arrives, every queued promise resolves with the same value. Error "
        "responses propagate to every queued promise so retry logic stays "
        "consistent with the prior contract.\n"
    )
    violations = validate_pr_body(long_body_missing_heavy_headers)
    assert any("heavy" in each_violation.lower() for each_violation in violations), (
        f"Long body missing Heavy headers must trip the required-header check; got {violations!r}"
    )


def test_compute_pr_body_shape_uses_named_shape_constants() -> None:
    """`_compute_pr_body_shape` returns the centralised shape names rather than
    inline string literals. Confirm the constants flow through end-to-end."""
    trivial_body = "Bump bun to 1.3.14."
    assert hook_module._compute_pr_body_shape(trivial_body) == hook_module.TRIVIAL_SHAPE


def test_compute_flesch_reading_ease_uses_named_constants() -> None:
    """`_compute_flesch_reading_ease` must reference the named Flesch constants
    rather than embed the magic literals 206.835 / 1.015 / 84.6 / 100.0 inline.
    Smoke-test the empty-input path returns the perfect-score default."""
    perfect_score = hook_module._compute_flesch_reading_ease("")
    assert perfect_score == hook_module.FLESCH_PERFECT_SCORE
    perfect_score_no_words = hook_module._compute_flesch_reading_ease("   ")
    assert perfect_score_no_words == hook_module.FLESCH_PERFECT_SCORE


def test_iter_section_headers_docstring_matches_actual_pattern() -> None:
    """`_iter_section_headers` uses `HEADING_LINE_PATTERN = ^#+`, so it returns
    every ATX heading level (`#`, `##`, `###`...), not just `##`. The docstring
    must describe that actual contract so callers cannot be misled."""
    docstring = hook_module._iter_section_headers.__doc__ or ""
    assert "every ATX heading" in docstring or "any heading level" in docstring, (
        f"_iter_section_headers docstring must document that it matches every "
        f"heading level (`HEADING_LINE_PATTERN` is `^#+`); got: {docstring!r}"
    )


def test_extract_readability_target_text_strips_fences_before_finding_header() -> None:
    """`_extract_readability_target_text` must strip fenced code blocks before
    searching for the first structural header. Otherwise a fenced example like
    ```\\n## Problem\\n``` is matched as the first header and the intro / section
    boundaries collapse to bogus values."""
    body = (
        "Intro paragraph that should be the intro for readability analysis.\n\n"
        "```\n## Problem\n```\n\n"
        "## RealHeader\n\n"
        "Real first-section prose for readability measurement.\n"
    )
    target_text = hook_module._extract_readability_target_text(body)
    assert "Intro paragraph" in target_text, (
        f"Intro paragraph must survive; got {target_text!r}"
    )
    assert "Real first-section prose" in target_text, (
        f"First real section prose must follow; got {target_text!r}"
    )


@pytest.fixture
def readability_state_paths_enabled(tmp_path, monkeypatch):
    """Redirect the three readability state files to per-test temp paths while keeping
    readability enabled. The autouse `_isolate_readability_state` fixture disables
    readability by default for unrelated tests; tests exercising strike-counter or
    dispatch behavior need it ON, so this fixture re-points the three state paths
    WITHOUT stubbing _is_readability_enabled.

    Returns:
        Tuple of (strike_path, override_path, enabled_path).
    """
    strike_path = tmp_path / "strikes.json"
    override_path = tmp_path / "overrides.json"
    enabled_path = tmp_path / "enabled.json"
    monkeypatch.setattr(hook_module, "READABILITY_STATE_FILE", strike_path)
    monkeypatch.setattr(hook_module, "READABILITY_THRESHOLD_OVERRIDE_FILE", override_path)
    monkeypatch.setattr(hook_module, "READABILITY_ENABLED_STATE_FILE", enabled_path)
    return strike_path, override_path, enabled_path
