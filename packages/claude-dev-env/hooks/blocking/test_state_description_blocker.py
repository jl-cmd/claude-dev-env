"""Tests for state_description_blocker hook."""

import json
import os
import subprocess
import sys

HOOK_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "state_description_blocker.py"
)

CLEAN_PYTHON = "x = 1  # Uses a default timeout"
CLEAN_MD = "# Config\n\nThe API uses port 8080."
CLEAN_COMMENT = "# Configured with a 30-second timeout"

VIOLATION_INSTEAD_OF_COMMENT = "# Uses X instead of Y"
VIOLATION_PREVIOUSLY_COMMENT = "# Previously configured via Z"
VIOLATION_NOW_USES_COMMENT = "# Now uses the new API client"
VIOLATION_COMMENT_WITH_CLOSE_BLOCK = "# No longer functional — the */ route was deprecated"
VIOLATION_MD_INSTEAD = "# API\n\nUses GraphQL instead of REST."
VIOLATION_MD_PREVIOUSLY = "# Config\n\nPreviously set via env var."
VIOLATION_MD_NOW_USES = "# Auth\n\nNow uses OAuth2."


class _RunHook:
    """Helper to test the hook via subprocess."""

    def __call__(self, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )


_run_hook = _RunHook()


def test_block_clean_python_comment_passes():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": CLEAN_PYTHON,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_clean_markdown_passes():
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/README.md",
            "content": CLEAN_MD,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_clean_comment_passes():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": CLEAN_COMMENT,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_irrelevant_file_passes():
    result = _run_hook(
        "Write",
        {
            "file_path": "data.txt",
            "content": VIOLATION_INSTEAD_OF_COMMENT,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_empty_content_passes():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": "",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_unknown_tool_passes():
    result = _run_hook(
        "Grep",
        {
            "pattern": "foo",
            "path": ".",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_detects_instead_of_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": VIOLATION_INSTEAD_OF_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "instead of" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_previously_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": VIOLATION_PREVIOUSLY_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "previously" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_now_uses_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/client.py",
            "content": VIOLATION_NOW_USES_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "now uses" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_instead_of_in_markdown():
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/api.md",
            "content": VIOLATION_MD_INSTEAD,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_detects_previously_in_markdown():
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/config.md",
            "content": VIOLATION_MD_PREVIOUSLY,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_detects_now_uses_in_markdown():
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/auth.md",
            "content": VIOLATION_MD_NOW_USES,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_detects_edit_new_string():
    result = _run_hook(
        "Edit",
        {
            "file_path": "src/main.py",
            "old_string": "old_comment",
            "new_string": VIOLATION_PREVIOUSLY_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "previously" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_clean_edit_passes():
    result = _run_hook(
        "Edit",
        {
            "file_path": "src/main.py",
            "old_string": "x = 1",
            "new_string": CLEAN_PYTHON,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_system_message_and_suppress_output():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": VIOLATION_INSTEAD_OF_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["suppressOutput"] is True
    assert isinstance(output["systemMessage"], str)
    assert len(output["systemMessage"]) > 0


def test_detects_no_longer_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": "# No longer supports legacy mode",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no longer" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_used_to_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": "# Used to be hardcoded",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "used to" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_switched_to_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": "# Switched to async processing",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "switched to" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_comment_with_close_block_token():
    """A single-line # comment containing */ (e.g. docs referencing a deprecated */ route)
    should still be scanned for violations — the `*/` must not trigger a spurious
    block-comment `continue` that skips the single-line comment check.
    Real pattern: midjourney-docs 'no longer works' + route path with */."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": VIOLATION_COMMENT_WITH_CLOSE_BLOCK,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no longer" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_inline_trailing_comment():
    """A code line with a trailing inline comment containing historical language should
    be blocked. Real pattern: ARCHITECTURE.md 'no longer needed' reference in migration
    context — simulates `x = val  # previously needed but now handled elsewhere`."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": "max_retries = 3  # No longer needed since async retry handles it",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no longer" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_ignores_c_preprocessor_directive():
    """A C/C++ #error directive should NOT be treated as a comment.
    # is not a comment marker in C — startswith should only check //."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.h",
            "content": '#error "This code previously used replaced API"',
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_ignores_hash_in_javascript_inline():
    """A JavaScript line with # in a string literal should NOT trigger inline
    comment extraction — # is not a comment marker in JS. Only // should be checked.
    Real pattern: `const sel = "#originally-dark"` would falsely match `originally`
    if # were treated as a comment marker."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.js",
            "content": 'const selector = "#originally-dark"  // Use dark as default',
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_ignores_double_slash_in_js_url():
    """A JavaScript/TypeScript line with a URL containing // should NOT trigger inline
    comment extraction on the URL. The :// protocol marker should be
    recognized and skipped. Real pattern: `fetch("https://api.example.com/replaces")`
    should not false-positive on `replaces` in the URL path."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/fetch.ts",
            "content": 'fetch("https://api.example.com/replaces")',
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_comment_continuation_with_nested_glob():
    """A continuation line inside a /* */ block comment that contains /* in its
    content should append the full line, not truncate from the nested /* onward.
    * List: no longer supported /* pattern — violation should still be detected."""
    content = "/*\n * List: no longer supported /* pattern\n */"
    result = _run_hook(
        "Write",
        {
            "file_path": "src/cache.ts",
            "content": content,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no longer" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_inline_after_url_on_same_line():
    """A JS/TS line with a URL followed by a real inline comment containing a
    violation should still be detected. const url = "https://api.com"; // no longer used
    — the // before no longer is a real inline comment, not a URL."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/fetch.ts",
            "content": 'const url = "https://api.com"; // no longer used',
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no longer" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_ignores_code_before_block_comment():
    """A line with code before /* */ should only scan the comment portion, not the code.
    `cache.replaces(old); /* Use fresh cache */` should NOT trigger on `replaces`
    in the code portion."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/cache.ts",
            "content": "cache.replaces(old); /* Use fresh cache */",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_ignores_url_with_double_slash_in_python():
    """A Python line with a URL containing // should NOT trigger inline comment
    extraction — // is floor division in Python, not a comment marker.
    Real pattern: `url = "https://api.example.com/replaces/v1"` would falsely
    extract `//api.example.com/replaces/v1"` as a comment and match `replaces`."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": 'url = "https://api.example.com/replaces/v1"',
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_ignores_instead_of_in_code_string_with_inline_comment():
    """A code line containing 'instead of' inside a string literal with a trailing
    comment should NOT be blocked — only the comment portion after # is scanned.
    This prevents false-positives from `msg = 'instead of' # comment` patterns."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": "msg = 'instead of'  # Use the default timeout",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_ignores_glob_pattern_with_star_in_python():
    """A Python line with /* (glob pattern) should NOT set is_in_block_comment.
    Python doesn't support /* */ block comments. `glob("src/*")` must not cause
    subsequent lines to be treated as block comment content."""
    content = 'files = glob("src/*")\nprint("previously done")  # clean comment'
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": content,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_ignores_comment_with_glob_pattern():
    """A single-line comment containing /* should NOT set is_in_block_comment for
    subsequent lines. Without this guard, `# Uses /* glob syntax` would set block-
    comment state and all subsequent code lines would be falsely treated as comments."""
    content = "# Uses /* glob syntax\nnext_line = calc()  # clean comment"
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": content,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_single_line_block_comment_closes():
    """A same-line /* */ block comment like code(); /* note */ should close
    on the same line. is_in_block_comment must not stay True after the line."""
    content = "code(); /* previously used */\nclean_code()"
    result = _run_hook(
        "Write",
        {
            "file_path": "src/cache.ts",
            "content": content,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "previously" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_block_comment_with_url_closes_correctly():
    """A block comment line containing // in a URL should still detect */ and close
    the block comment state. `* https://example.com/ */` must not trigger inline
    comment extraction on // and skip the */ close check."""
    content = "/*\n * https://example.com/api/v1 */\nnormal_code()"
    result = _run_hook(
        "Write",
        {
            "file_path": "src/cache.ts",
            "content": content,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_same_line_block_comment_with_trailing_inline():
    """A line with a same-line /* */ block comment followed by a // inline comment
    containing a violation should detect the violation. The `continue` after same-line
    /* */ extraction must not skip the trailing inline comment check.
    `code(); /* clean */ // no longer used` — the `no longer` in // must be detected."""
    content = 'code(); /* clean */ // no longer used'
    result = _run_hook(
        "Write",
        {
            "file_path": "src/fetch.ts",
            "content": content,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no longer" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_multi_line_block_comment_close_with_trailing_inline():
    """A multi-line /* */ block comment where the closing line has a // inline comment
    containing a violation should detect the violation. The `continue` after block
    comment close line must not skip the trailing inline comment check."""
    content = "/*\n * end */ // no longer used"
    result = _run_hook(
        "Write",
        {
            "file_path": "src/cache.ts",
            "content": content,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no longer" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_earliest_inline_marker_in_php():
    """A PHP line with a // inline comment followed by a # hash should find the //
    marker (earliest) not the # marker for comment extraction.
    `echo $x; // previously used #tag` — `previously` in // must be detected."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/index.php",
            "content": 'echo $x; // previously used #tag',
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "previously" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_additional_context_contains_examples():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": VIOLATION_INSTEAD_OF_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    ctx = output["hookSpecificOutput"].get("additionalContext", "")
    assert "BAD:" in ctx
    assert "GOOD:" in ctx


def test_handles_non_dict_stdin():
    """A non-dict root JSON object on stdin (e.g. a JSON array) should exit
    cleanly without raising — the hook must guard against malformed payloads."""
    payload = json.dumps(["not", "a", "dict"])
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_handles_non_dict_tool_input():
    """A tool_input that is not a dict should exit cleanly — the hook must
    guard against tool_input.get() on a non-dict value."""
    payload = json.dumps({"tool_name": "Write", "tool_input": "not_a_dict"})
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_handles_non_string_tool_name():
    """A tool_name that is not a string should exit cleanly — the hook must
    guard against tool_name not being a string."""
    payload = json.dumps({"tool_name": 123, "tool_input": {"file_path": "src/main.py"}})
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""
