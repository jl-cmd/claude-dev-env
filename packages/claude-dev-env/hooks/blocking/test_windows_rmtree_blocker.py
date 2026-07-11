"""Unit tests for windows_rmtree_blocker PreToolUse hook."""

import importlib.util
import json
import io
import pathlib
import sys
from contextlib import redirect_stderr, redirect_stdout

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "windows_rmtree_blocker",
    _HOOK_DIR / "windows_rmtree_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

payload_contains_unsafe_rmtree = hook_module.payload_contains_unsafe_rmtree
extract_payload_text = hook_module.extract_payload_text


def test_detects_basic_ignore_errors_call() -> None:
    assert payload_contains_unsafe_rmtree(
        "shutil.rmtree(target_path, ignore_errors=True)"
    )


def test_detects_call_with_path_first_then_ignore_errors() -> None:
    assert payload_contains_unsafe_rmtree(
        'shutil.rmtree(r"C:\\temp\\foo", ignore_errors=True)'
    )


def test_detects_oneliner_python_dash_c_form() -> None:
    bash_command = (
        'python -c "import shutil; '
        "shutil.rmtree(r'<team_temp_dir>', ignore_errors=True)\""
    )
    assert payload_contains_unsafe_rmtree(bash_command)


def test_detects_call_with_extra_whitespace() -> None:
    assert payload_contains_unsafe_rmtree(
        "shutil .rmtree (path,    ignore_errors  =  True)"
    )


def test_detects_call_split_across_lines() -> None:
    multiline_code = "shutil.rmtree(\n    target_path,\n    ignore_errors=True,\n)"
    assert payload_contains_unsafe_rmtree(multiline_code)


def test_allows_rmtree_with_onexc_handler() -> None:
    safe_code = "shutil.rmtree(target_path, onexc=_strip_read_only_and_retry)"
    assert not payload_contains_unsafe_rmtree(safe_code)


def test_allows_rmtree_with_onerror_handler() -> None:
    safe_code = "shutil.rmtree(target_path, onerror=_strip_read_only_and_retry)"
    assert not payload_contains_unsafe_rmtree(safe_code)


def test_allows_bare_rmtree_call() -> None:
    bare_call = "shutil.rmtree(target_path)"
    assert not payload_contains_unsafe_rmtree(bare_call)


def test_allows_ignore_errors_false() -> None:
    assert not payload_contains_unsafe_rmtree(
        "shutil.rmtree(target_path, ignore_errors=False)"
    )


def test_blocks_rmtree_with_nested_parens_in_args() -> None:
    assert payload_contains_unsafe_rmtree(
        "shutil.rmtree(Path(target).resolve(), ignore_errors=True)"
    )


DANGEROUS_RMTREE_SNIPPET = "shutil.rm" + "tree(path, ignore_errors" + "=True)"
DANGEROUS_RMTREE_SNIPPET_WITH_TARGET = (
    "shutil.rm" + "tree(target_path, ignore_errors" + "=True)"
)


def test_extract_payload_handles_write_content() -> None:
    extracted = extract_payload_text(
        "Write", {"file_path": "foo.py", "content": "abc"}
    )
    assert extracted == "abc"


def test_extract_payload_handles_edit_new_string() -> None:
    extracted = extract_payload_text(
        "Edit", {"file_path": "foo.py", "new_string": "abc"}
    )
    assert extracted == "abc"


def test_extract_payload_handles_bash_command() -> None:
    extracted = extract_payload_text("Bash", {"command": "ls"})
    assert extracted == "ls"


def test_extract_payload_returns_empty_for_unknown_tool() -> None:
    extracted = extract_payload_text("OtherTool", {"content": "abc"})
    assert extracted == ""


def test_extract_payload_returns_empty_for_write_to_non_python_file() -> None:
    extracted = extract_payload_text(
        "Write",
        {
            "file_path": "agents/clean-coder.md",
            "content": DANGEROUS_RMTREE_SNIPPET,
        },
    )
    assert extracted == ""


def test_extract_payload_returns_empty_for_edit_to_non_python_file() -> None:
    extracted = extract_payload_text(
        "Edit",
        {
            "file_path": "docs/something.md",
            "new_string": DANGEROUS_RMTREE_SNIPPET,
        },
    )
    assert extracted == ""


def test_extract_payload_returns_content_for_write_to_python_file() -> None:
    extracted = extract_payload_text(
        "Write",
        {
            "file_path": "hooks/blocking/my_hook.py",
            "content": DANGEROUS_RMTREE_SNIPPET_WITH_TARGET,
        },
    )
    assert extracted == DANGEROUS_RMTREE_SNIPPET_WITH_TARGET


def test_python_file_extension_constant_drives_python_filter() -> None:
    python_extension = hook_module.PYTHON_FILE_EXTENSION
    extracted_for_python = extract_payload_text(
        "Write",
        {
            "file_path": f"hooks/blocking/sample{python_extension}",
            "content": DANGEROUS_RMTREE_SNIPPET_WITH_TARGET,
        },
    )
    assert extracted_for_python == DANGEROUS_RMTREE_SNIPPET_WITH_TARGET


def test_extract_payload_returns_content_for_write_without_file_path() -> None:
    extracted = extract_payload_text(
        "Write",
        {"content": "some python code"},
    )
    assert extracted == "some python code"


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
    stdout_text, _stderr_text, exit_code = _run_hook_with_stdin_text(
        json.dumps(hook_input)
    )
    return stdout_text, exit_code


def test_main_blocks_unsafe_bash_command() -> None:
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    'python -c "import shutil; '
                    "shutil.rmtree(r'/tmp/x', ignore_errors=True)\""
                )
            },
        }
    )
    assert exit_code == 0
    response_payload = json.loads(stdout_text)
    decision_block = response_payload["hookSpecificOutput"]
    assert decision_block["permissionDecision"] == "deny"
    assert "windows-rmtree" in decision_block["permissionDecisionReason"]


def test_main_passes_through_safe_write() -> None:
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {"content": "shutil.rmtree(path, onexc=handler)"},
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_passes_through_unrelated_tool() -> None:
    stdout_text, exit_code = _run_hook(
        {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}}
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_passes_through_unsafe_write_to_non_python_file() -> None:
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "agents/clean-coder.md",
                "content": DANGEROUS_RMTREE_SNIPPET,
            },
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_blocks_write_with_missing_file_path_and_unsafe_content() -> None:
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {"content": DANGEROUS_RMTREE_SNIPPET_WITH_TARGET},
        }
    )
    assert exit_code == 0
    response_payload = json.loads(stdout_text)
    decision_block = response_payload["hookSpecificOutput"]
    assert decision_block["permissionDecision"] == "deny"


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
