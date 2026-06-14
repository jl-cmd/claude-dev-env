"""Unit tests for workflow_substitution_slot_blocker PreToolUse hook."""

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
    "workflow_substitution_slot_blocker",
    _HOOK_DIR / "workflow_substitution_slot_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

content_has_violation = hook_module.content_has_violation
find_bare_index_segments = hook_module.find_bare_index_segments
find_bare_path_segments = hook_module.find_bare_path_segments
has_iteration_loop = hook_module.has_iteration_loop
written_content = hook_module.written_content


_VIOLATING_TEMPLATE = (
    "For EACH candidate i, build a bible dir cand_i per the contract.\n"
    "   & ${PY} -c \"...Path(r'${args.work_dir}\\\\cand_i\\\\plate.svg')...\"\n"
    "   & ${PY} compose.py --out ${args.work_dir}\\\\cand_i\\\\sample.png "
    "--glow <candidate glow_hex>\n"
    'Return: {key: "cand_i", name, sample_png}\n'
)

_FIXED_TEMPLATE = (
    "For EACH candidate i, build a bible dir cand_<i> per the contract.\n"
    "   & ${PY} -c \"...Path(r'${args.work_dir}\\\\cand_<i>\\\\plate.svg')...\"\n"
    "   & ${PY} compose.py --out ${args.work_dir}\\\\cand_<i>\\\\sample.png "
    "--glow <candidate glow_hex>\n"
    'Return: {key: "cand_<i>", name, sample_png}\n'
)


def test_detects_bare_index_in_path_segment() -> None:
    assert find_bare_index_segments(
        "render Path(r'${args.work_dir}\\\\cand_i\\\\plate.svg')"
    ) == {"cand_i"}


def test_detects_quoted_key_when_token_also_appears_as_path_segment() -> None:
    looped_path_and_key = "write ${work}\\\\cand_i\\\\plate.svg\n{key: \"cand_i\", name}"
    assert "cand_i" in find_bare_index_segments(looped_path_and_key)


def test_quoted_key_alone_without_path_segment_is_not_detected() -> None:
    assert find_bare_index_segments('{key: "metric_i", name}') == set()


def test_index_segments_equal_path_segments_for_looped_path_and_key() -> None:
    looped_path_and_key = "write ${work}\\\\cand_i\\\\plate.svg\n{key: \"cand_i\", name}"
    assert find_bare_index_segments(looped_path_and_key) == find_bare_path_segments(
        looped_path_and_key
    )


def test_index_segments_equal_path_segments_for_quoted_only_key() -> None:
    quoted_only_key = '{key: "metric_i", name}'
    assert find_bare_index_segments(quoted_only_key) == find_bare_path_segments(
        quoted_only_key
    )


def test_marked_substitution_slot_is_not_a_bare_segment() -> None:
    assert (
        find_bare_index_segments(
            "render Path(r'${args.work_dir}\\\\cand_<i>\\\\plate.svg')"
        )
        == set()
    )


def test_violating_template_is_flagged() -> None:
    assert content_has_violation(_VIOLATING_TEMPLATE) is True


def test_fixed_template_passes() -> None:
    assert content_has_violation(_FIXED_TEMPLATE) is False


def test_template_without_angle_convention_is_not_flagged() -> None:
    no_convention = (
        "For EACH candidate i, write to ${work}\\\\cand_i\\\\plate.svg and return.\n"
    )
    assert content_has_violation(no_convention) is False


def test_template_without_loop_is_not_flagged() -> None:
    no_loop = "Write the plate to ${work}\\\\cand_i\\\\plate.svg using <glow_hex>.\n"
    assert content_has_violation(no_loop) is False


def test_each_inside_an_ordinary_word_is_not_a_loop() -> None:
    for each_word in ("reach", "teach", "breach", "bleach", "preach", "impeach"):
        assert has_iteration_loop(each_word + " the end") is False


def test_standalone_lowercase_each_in_prose_is_not_a_loop() -> None:
    assert has_iteration_loop("use each color once") is False


def test_standalone_each_keyword_is_a_loop() -> None:
    assert has_iteration_loop("For EACH candidate i") is True


def test_lowercase_for_each_phrase_is_still_a_loop() -> None:
    assert has_iteration_loop("for each candidate") is True


def test_benign_prose_each_with_fixed_literal_is_not_flagged() -> None:
    benign_template = (
        "Render each layer to <layer.svg>.\n"
        "The protocol field is named 'tier_i' as a permanent identifier.\n"
    )
    assert content_has_violation(benign_template) is False


def test_quoted_permanent_identifier_key_is_not_flagged() -> None:
    permanent_identifier_template = (
        'For EACH candidate, render <plate.svg>.\nReturn {key: "metric_i", value}'
    )
    assert content_has_violation(permanent_identifier_template) is False


def test_quoted_key_flagged_only_when_token_also_appears_as_path_segment() -> None:
    looping_path_and_key = (
        "For EACH candidate, write <plate.svg> to ${work}\\\\cand_i\\\\plate.svg.\n"
        'Return {key: "cand_i", name}\n'
    )
    assert content_has_violation(looping_path_and_key) is True


def test_written_content_reads_multiedit_new_strings() -> None:
    multi_edit_input = {
        "edits": [
            {"old_string": "x", "new_string": "first ${work}\\\\cand_i\\\\plate.svg"},
            {"old_string": "y", "new_string": "second <glow_hex>"},
        ]
    }
    combined = written_content("MultiEdit", multi_edit_input)
    assert "cand_i" in combined
    assert "<glow_hex>" in combined


def _run_main_with_io(input_text: str) -> str:
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            try:
                hook_module.main()
            except SystemExit:
                pass
            return mock_stdout.getvalue()


def test_main_blocks_violating_workflow_write() -> None:
    hook_input = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/scripts/shared_palette_gate.workflow.js",
            "content": _VIOLATING_TEMPLATE,
        },
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    payload = json.loads(output_text)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_blocks_violating_workflow_edit() -> None:
    hook_input = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/repo/scripts/shared_palette_gate.workflow.js",
            "new_string": _VIOLATING_TEMPLATE,
        },
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    payload = json.loads(output_text)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_blocks_violating_workflow_multiedit() -> None:
    hook_input = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "/repo/scripts/shared_palette_gate.workflow.js",
            "edits": [{"old_string": "placeholder", "new_string": _VIOLATING_TEMPLATE}],
        },
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    payload = json.loads(output_text)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_passes_fixed_workflow_write() -> None:
    hook_input = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/scripts/shared_palette_gate.workflow.js",
            "content": _FIXED_TEMPLATE,
        },
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_non_workflow_path() -> None:
    hook_input = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/scripts/helper.js",
            "content": _VIOLATING_TEMPLATE,
        },
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_wrong_tool_name() -> None:
    hook_input = {
        "tool_name": "Bash",
        "tool_input": {
            "file_path": "/repo/scripts/x.workflow.js",
            "command": "echo cand_i",
        },
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_malformed_json() -> None:
    assert _run_main_with_io("not valid json {{{") == ""
