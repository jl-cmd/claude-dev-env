"""Unit tests for duplicate_rmtree_helper_blocker PreToolUse hook."""

import importlib.util
import io
import json
import pathlib
import sys
from contextlib import redirect_stderr, redirect_stdout

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))
_HOOKS_ROOT = _HOOK_DIR.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

hook_spec = importlib.util.spec_from_file_location(
    "duplicate_rmtree_helper_blocker",
    _HOOK_DIR / "duplicate_rmtree_helper_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

payload_defines_sanctioned_helper = hook_module.payload_defines_sanctioned_helper
path_is_exempt = hook_module.path_is_exempt
extract_payload_text = hook_module.extract_payload_text

COPIED_TRIO = (
    "def _strip_read_only_and_retry(removal_function, target_path, *_exc_info):\n"
    "    try:\n"
    "        os.chmod(target_path, stat.S_IWRITE)\n"
    "        removal_function(target_path)\n"
    "    except OSError:\n"
    "        pass\n\n\n"
    "_rmtree_supports_onexc = 'onexc' in inspect.signature(shutil.rmtree).parameters\n\n\n"
    "def _force_remove_tree(target_path):\n"
    "    if _rmtree_supports_onexc:\n"
    "        shutil.rmtree(target_path, onexc=_strip_read_only_and_retry)\n"
)


def test_detects_strip_read_only_definition() -> None:
    assert payload_defines_sanctioned_helper(
        "def _strip_read_only_and_retry(removal_function, target_path, *_exc_info):\n    pass"
    )


def test_detects_force_remove_tree_definition() -> None:
    assert payload_defines_sanctioned_helper(
        "def _force_remove_tree(target_path: Path) -> None:\n    pass"
    )


def test_detects_force_rmtree_definition() -> None:
    assert payload_defines_sanctioned_helper(
        "def force_rmtree(target_path: str) -> None:\n    pass"
    )


def test_detects_indented_method_definition() -> None:
    assert payload_defines_sanctioned_helper(
        "class FileTools:\n    def _strip_read_only_and_retry(self, fn, path):\n        pass"
    )


def test_detects_copied_trio_block() -> None:
    assert payload_defines_sanctioned_helper(COPIED_TRIO)


def test_allows_import_of_shared_helper() -> None:
    assert not payload_defines_sanctioned_helper(
        "from shared_utils.web_automation.utils.windows_filesystem import force_rmtree"
    )


def test_allows_call_site_without_definition() -> None:
    assert not payload_defines_sanctioned_helper("force_rmtree(staging_directory)")


def test_allows_helper_name_inside_string_literal() -> None:
    corrective_message = (
        '    "    def _strip_read_only_and_retry(removal_function, target_path):\\n"'
    )
    assert not payload_defines_sanctioned_helper(corrective_message)


def test_allows_helper_definition_inside_triple_quoted_string() -> None:
    documentation_snippet = (
        'EXAMPLE = """\\\n'
        'def _strip_read_only_and_retry(removal_function, target_path, *_exc_info):\n'
        '    pass\n'
        '"""\n'
    )
    assert not payload_defines_sanctioned_helper(documentation_snippet)


def test_allows_force_rmtree_definition_inside_triple_quoted_string() -> None:
    documentation_snippet = (
        "snippet = '''\n"
        "def force_rmtree(target_path: str) -> None:\n"
        "    pass\n"
        "'''\n"
    )
    assert not payload_defines_sanctioned_helper(documentation_snippet)


def test_detects_real_definition_following_triple_quoted_docstring() -> None:
    module_text = (
        '"""Module docstring."""\n'
        'def force_rmtree(target_path: str) -> None:\n'
        '    pass\n'
    )
    assert payload_defines_sanctioned_helper(module_text)


def test_detects_real_definition_between_two_triple_quoted_strings() -> None:
    module_text = (
        '"""Leading docstring."""\n'
        'def _force_remove_tree(target_path: str) -> None:\n'
        '    pass\n'
        '"""Trailing docstring."""\n'
    )
    assert payload_defines_sanctioned_helper(module_text)


def test_allows_unrelated_definition() -> None:
    assert not payload_defines_sanctioned_helper("def categorize_and_move(theme_folder):\n    pass")


def test_path_exempts_blocker_source() -> None:
    assert path_is_exempt("packages/x/hooks/blocking/windows_rmtree_blocker.py")
    assert path_is_exempt("packages/x/hooks/blocking/duplicate_rmtree_helper_blocker.py")


def test_path_exempts_shared_helper_module() -> None:
    assert path_is_exempt("shared_utils/web_automation/utils/windows_filesystem.py")


def test_path_exempts_existing_session_env_cleanup_definition_site() -> None:
    assert path_is_exempt("packages/claude-dev-env/hooks/session/session_env_cleanup.py")


def test_path_exempts_existing_md_to_html_test_support_definition_site() -> None:
    assert path_is_exempt(
        "packages/claude-dev-env/hooks/blocking/_md_to_html_blocker_test_support.py"
    )


def test_path_exempts_existing_teardown_worktrees_definition_site() -> None:
    assert path_is_exempt(
        "packages/claude-dev-env/skills/_shared/pr-loop/scripts/teardown_worktrees.py"
    )


def test_main_allows_full_file_write_of_existing_definition_site() -> None:
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "packages/claude-dev-env/hooks/session/session_env_cleanup.py",
                "content": COPIED_TRIO,
            },
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_path_exempts_test_file_prefix() -> None:
    assert path_is_exempt("hooks/blocking/test_duplicate_rmtree_helper_blocker.py")


def test_path_exempts_test_file_suffix() -> None:
    assert path_is_exempt("shared_utils/something_test.py")


def test_path_does_not_exempt_production_module() -> None:
    assert not path_is_exempt(
        "shared_utils/samsung_utils/cert_failure_processor/failure_categorizer.py"
    )


def test_path_does_not_exempt_filename_containing_exempt_fragment() -> None:
    assert not path_is_exempt("packages/x/not_windows_filesystem.py")
    assert not path_is_exempt("packages/x/my_windows_filesystem.py")


def test_path_does_not_exempt_backslash_path_with_containing_fragment() -> None:
    assert not path_is_exempt("packages\\x\\not_windows_filesystem.py")


def test_extract_payload_text_reads_write_content() -> None:
    extracted = extract_payload_text("Write", {"file_path": "foo.py", "content": "abc"})
    assert extracted == ("foo.py", "abc")


def test_extract_payload_text_reads_edit_new_string() -> None:
    extracted = extract_payload_text("Edit", {"file_path": "foo.py", "new_string": "abc"})
    assert extracted == ("foo.py", "abc")


def test_extract_payload_text_returns_empty_for_non_python_file() -> None:
    extracted = extract_payload_text("Write", {"file_path": "notes.md", "content": COPIED_TRIO})
    assert extracted == ("notes.md", "")


def test_extract_payload_text_returns_empty_for_unknown_tool() -> None:
    extracted = extract_payload_text("Read", {"file_path": "foo.py"})
    assert extracted == ("", "")


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
                raw_exit_code = exit_signal.code
                exit_code = raw_exit_code if isinstance(raw_exit_code, int) else 0
    finally:
        sys.stdin = sys.__stdin__
    return captured_stdout.getvalue(), captured_stderr.getvalue(), exit_code


def _run_hook(hook_input: dict) -> tuple[str, int]:
    stdout_text, _stderr_text, exit_code = _run_hook_with_stdin_text(json.dumps(hook_input))
    return stdout_text, exit_code


def test_main_blocks_local_trio_copy_in_production_module() -> None:
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": (
                    "shared_utils/samsung_utils/cert_failure_processor/failure_categorizer.py"
                ),
                "content": COPIED_TRIO,
            },
        }
    )
    assert exit_code == 0
    response_payload = json.loads(stdout_text)
    decision_block = response_payload["hookSpecificOutput"]
    assert decision_block["permissionDecision"] == "deny"
    assert "duplicate-rmtree-helper" in decision_block["permissionDecisionReason"]


def test_main_allows_import_of_shared_helper() -> None:
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "shared_utils/samsung_utils/cleanup.py",
                "content": (
                    "from shared_utils.web_automation.utils.windows_filesystem import "
                    "force_rmtree\n\nforce_rmtree(path)\n"
                ),
            },
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_definition_in_shared_helper_module() -> None:
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "shared_utils/web_automation/utils/windows_filesystem.py",
                "content": COPIED_TRIO,
            },
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_definition_in_test_file() -> None:
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "shared_utils/test_windows_filesystem.py",
                "content": COPIED_TRIO,
            },
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_passes_through_non_python_file() -> None:
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/cleanup.md", "content": COPIED_TRIO},
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_passes_through_unrelated_tool() -> None:
    stdout_text, exit_code = _run_hook({"tool_name": "Read", "tool_input": {"file_path": "foo.py"}})
    assert exit_code == 0
    assert stdout_text == ""


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
