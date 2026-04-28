"""Unit tests for windows_rmtree_blocker PreToolUse hook."""

import importlib.util
import json
import io
import pathlib
import sys
from contextlib import redirect_stdout

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


def test_extract_payload_handles_write_content() -> None:
    extracted = extract_payload_text("Write", {"content": "abc"})
    assert extracted == "abc"


def test_extract_payload_handles_edit_new_string() -> None:
    extracted = extract_payload_text("Edit", {"new_string": "abc"})
    assert extracted == "abc"


def test_extract_payload_handles_bash_command() -> None:
    extracted = extract_payload_text("Bash", {"command": "ls"})
    assert extracted == "ls"


def test_extract_payload_returns_empty_for_unknown_tool() -> None:
    extracted = extract_payload_text("OtherTool", {"content": "abc"})
    assert extracted == ""


def _run_hook(hook_input: dict) -> tuple[str, int]:
    captured = io.StringIO()
    sys.stdin = io.StringIO(json.dumps(hook_input))
    try:
        with redirect_stdout(captured):
            try:
                hook_module.main()
            except SystemExit as exit_signal:
                exit_code = exit_signal.code or 0
    finally:
        sys.stdin = sys.__stdin__
    return captured.getvalue(), exit_code


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
