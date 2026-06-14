"""Unit tests for hook_prose_detector_consistency PreToolUse hook."""

import importlib.util
import io
import json
import pathlib
import sys
from unittest import mock

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_ROOT = _HOOK_DIR.parent
for _each_root in (str(_HOOK_DIR), str(_HOOKS_ROOT)):
    if _each_root not in sys.path:
        sys.path.insert(0, _each_root)

hook_spec = importlib.util.spec_from_file_location(
    "hook_prose_detector_consistency",
    _HOOK_DIR / "hook_prose_detector_consistency.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

content_has_violation = hook_module.content_has_violation
claims_output_key_trigger = hook_module.claims_output_key_trigger
detects_only_path_shape = hook_module.detects_only_path_shape
is_constants_module = hook_module.is_constants_module
is_hook_python_module = hook_module.is_hook_python_module
is_own_detector_family = hook_module.is_own_detector_family
written_content = hook_module.written_content

_BLOCKER_MODULE_PATH = "/repo/hooks/blocking/some_blocker.py"
_CONSTANTS_MODULE_PATH = "/repo/hooks/hooks_constants/some_blocker_constants.py"

_OWN_HOOK_PATH = "/repo/packages/x/hooks/blocking/hook_prose_detector_consistency.py"
_OWN_CONSTANTS_PATH = (
    "/repo/packages/x/hooks/hooks_constants/hook_prose_detector_consistency_constants.py"
)
_OWN_TEST_PATH = "/repo/packages/x/hooks/blocking/test_hook_prose_detector_consistency.py"


_OVERSTATED_MESSAGE_MODULE = (
    'path_context = re.compile(r"(?:[\\\\/]\\s*([A-Za-z][\\w]*?_[ijk])")\n'
    "CORRECTIVE_MESSAGE = (\n"
    '    "A bare per-iteration index token (for example `cand_i`) appears as a path "\n'
    '    "or output-key segment inside a looping block."\n'
    ")\n"
)

_FIXED_MESSAGE_MODULE = (
    'path_context = re.compile(r"(?:[\\\\/]\\s*([A-Za-z][\\w]*?_[ijk])")\n'
    "CORRECTIVE_MESSAGE = (\n"
    '    "A bare per-iteration index token (for example `cand_i`) appears as a "\n'
    '    "per-iteration path segment inside a looping block."\n'
    ")\n"
)


def test_overstated_path_shape_module_is_flagged() -> None:
    assert content_has_violation(_OVERSTATED_MESSAGE_MODULE, _BLOCKER_MODULE_PATH) is True


def test_fixed_path_shape_module_passes() -> None:
    assert content_has_violation(_FIXED_MESSAGE_MODULE, _BLOCKER_MODULE_PATH) is False


def test_output_key_claim_without_path_detector_in_blocker_passes() -> None:
    no_path_detector = (
        'pattern = re.compile(r"[A-Za-z]+")\n'
        'CORRECTIVE_MESSAGE = "blocks an output-key segment"\n'
    )
    assert content_has_violation(no_path_detector, _BLOCKER_MODULE_PATH) is False


def test_output_key_claim_alone_in_constants_module_is_flagged() -> None:
    constants_only = 'CORRECTIVE_MESSAGE = "appears as a path or output-key segment"\n'
    assert content_has_violation(constants_only, _CONSTANTS_MODULE_PATH) is True


def test_constants_module_without_output_key_claim_passes() -> None:
    clean_constants = 'CORRECTIVE_MESSAGE = "appears as a per-iteration path segment"\n'
    assert content_has_violation(clean_constants, _CONSTANTS_MODULE_PATH) is False


def test_path_detector_without_output_key_claim_passes() -> None:
    path_only = 'path_context = re.compile(r"(?:[\\\\/]\\s*([A-Za-z][\\w]*?_[ijk])")\n'
    assert content_has_violation(path_only, _BLOCKER_MODULE_PATH) is False


def test_space_separated_output_key_phrase_is_flagged() -> None:
    space_variant = (
        'path_context = re.compile(r"(?:[\\\\/]\\s*(token))")\n'
        'message = "appears as a path or output key segment"\n'
    )
    assert content_has_violation(space_variant, _BLOCKER_MODULE_PATH) is True


def test_own_hook_module_is_exempt_from_self_lockout() -> None:
    own_hook_content = pathlib.Path(hook_module.__file__).read_text(encoding="utf-8")
    assert content_has_violation(own_hook_content, _OWN_HOOK_PATH) is False


def test_own_constants_module_is_exempt_from_self_lockout() -> None:
    own_constants_path = (
        _HOOKS_ROOT
        / "hooks_constants"
        / "hook_prose_detector_consistency_constants.py"
    )
    own_constants_content = own_constants_path.read_text(encoding="utf-8")
    assert content_has_violation(own_constants_content, _OWN_CONSTANTS_PATH) is False


def test_own_test_module_is_exempt_from_self_lockout() -> None:
    own_test_content = pathlib.Path(__file__).read_text(encoding="utf-8")
    assert content_has_violation(own_test_content, _OWN_TEST_PATH) is False


def test_slot_blocker_constants_companion_passes_at_its_real_path() -> None:
    slot_constants_path = (
        _HOOKS_ROOT
        / "hooks_constants"
        / "workflow_substitution_slot_blocker_constants.py"
    )
    slot_constants_content = slot_constants_path.read_text(encoding="utf-8")
    assert content_has_violation(slot_constants_content, str(slot_constants_path)) is False


def test_is_own_detector_family_recognizes_hook_module() -> None:
    assert is_own_detector_family(_OWN_HOOK_PATH) is True


def test_is_own_detector_family_recognizes_constants_companion() -> None:
    assert is_own_detector_family(_OWN_CONSTANTS_PATH) is True


def test_is_own_detector_family_recognizes_test_module() -> None:
    assert is_own_detector_family(_OWN_TEST_PATH) is True


def test_is_own_detector_family_rejects_unrelated_blocker() -> None:
    assert is_own_detector_family(_BLOCKER_MODULE_PATH) is False


def test_unrelated_constants_module_still_flagged_after_exemption() -> None:
    constants_only = 'CORRECTIVE_MESSAGE = "appears as a path or output-key segment"\n'
    assert content_has_violation(constants_only, _CONSTANTS_MODULE_PATH) is True


def test_is_constants_module_accepts_constants_suffix() -> None:
    assert is_constants_module(_CONSTANTS_MODULE_PATH) is True


def test_is_constants_module_rejects_blocker_module() -> None:
    assert is_constants_module(_BLOCKER_MODULE_PATH) is False


def test_claims_output_key_trigger_matches_hyphen_form() -> None:
    assert claims_output_key_trigger("a path or output-key segment here") is True


def test_claims_output_key_trigger_ignores_unrelated_output_word() -> None:
    assert claims_output_key_trigger("the output is written to disk") is False


def test_detects_only_path_shape_finds_separator_class() -> None:
    assert detects_only_path_shape('re.compile(r"[\\\\/]token")') is True


def test_detects_only_path_shape_finds_backslash_only_class() -> None:
    assert detects_only_path_shape(r'pat = re.compile(r"[\\]token")') is True


def test_detects_only_path_shape_false_without_separator_class() -> None:
    assert detects_only_path_shape('re.compile(r"[A-Za-z]+")') is False


def test_is_hook_python_module_accepts_hooks_path() -> None:
    assert is_hook_python_module("/repo/packages/x/hooks/blocking/some_blocker.py") is True


def test_is_hook_python_module_rejects_non_hook_path() -> None:
    assert is_hook_python_module("/repo/src/blocking/some_blocker.py") is False


def test_is_hook_python_module_rejects_non_python_file() -> None:
    assert is_hook_python_module("/repo/hooks/blocking/notes.md") is False


def test_written_content_reads_edit_new_string() -> None:
    edit_input = {"new_string": "edited body"}
    assert written_content("Edit", edit_input) == "edited body"


def _run_main_with_io(input_text: str) -> str:
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            try:
                hook_module.main()
            except SystemExit:
                pass
            return mock_stdout.getvalue()


def test_main_blocks_overstated_hook_module_write() -> None:
    hook_input = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/hooks/hooks_constants/some_blocker_constants.py",
            "content": _OVERSTATED_MESSAGE_MODULE,
        },
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    payload = json.loads(output_text)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_blocks_overstated_hook_module_edit() -> None:
    hook_input = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/repo/hooks/hooks_constants/some_blocker_constants.py",
            "new_string": _OVERSTATED_MESSAGE_MODULE,
        },
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    payload = json.loads(output_text)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_passes_fixed_hook_module_write() -> None:
    hook_input = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/hooks/hooks_constants/some_blocker_constants.py",
            "content": _FIXED_MESSAGE_MODULE,
        },
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_non_hook_path() -> None:
    hook_input = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/some_blocker.py",
            "content": _OVERSTATED_MESSAGE_MODULE,
        },
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_wrong_tool_name() -> None:
    hook_input = {
        "tool_name": "Bash",
        "tool_input": {
            "file_path": "/repo/hooks/blocking/x.py",
            "command": "echo output-key segment",
        },
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_malformed_json() -> None:
    assert _run_main_with_io("not valid json {{{") == ""
