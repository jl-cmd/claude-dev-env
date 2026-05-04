"""Tests for reflow_skill_md.

Covers:
- wrap_long_bash_line returns unchanged when indent leaves zero/negative width
- wrap_long_bash_fence_lines handles deeply-indented bash content safely
- structural string literals are imported from config, not inline
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent


def _load_module() -> ModuleType:
    if str(_SCRIPTS_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIRECTORY))
    module_path = _SCRIPTS_DIRECTORY / "reflow_skill_md.py"
    spec = importlib.util.spec_from_file_location("reflow_skill_md", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reflow_module = _load_module()


def test_should_preserve_pr_converge_state_json_path_in_yaml_description() -> None:
    lines = [
        "  Multi-PR runs persist traffic in",
        "  `<TMPDIR>/pr-converge-<session_id>/state.json` per Multi-PR",
        "  orchestration model.",
        "---",
    ]
    all_reflowed_lines, next_index = reflow_module.reflow_yaml_description_block(lines, 0)
    reflowed_description = " ".join(each_line.strip() for each_line in all_reflowed_lines)

    assert next_index == len(lines)
    assert "`<TMPDIR>/pr-converge-<session_id>/state.json`" in reflowed_description
    assert "`<TMPDIR>/pr-converge-<session_id>/state.json>`" not in reflowed_description


def test_wrap_long_bash_line_returns_unchanged_when_indent_exceeds_max_width() -> None:
    """When indentation >= SKILL_REFLOW_MAXIMUM_WIDTH, return line as-is."""
    deep_indent = " " * 85
    long_line = deep_indent + "echo hello world this is a long command"
    all_result_lines = reflow_module.wrap_long_bash_line(long_line)
    assert all_result_lines == [long_line]


def test_wrap_long_bash_line_returns_unchanged_when_indent_equals_max_width() -> None:
    """When indentation == SKILL_REFLOW_MAXIMUM_WIDTH, return line as-is."""
    deep_indent = " " * 80
    long_line = deep_indent + "echo hello"
    all_result_lines = reflow_module.wrap_long_bash_line(long_line)
    assert all_result_lines == [long_line]


def test_wrap_long_bash_fence_lines_handles_deeply_indented_bash() -> None:
    """Full pipeline does not hang on bash fence with extreme indentation."""
    deep_indent = " " * 90
    all_input_lines = [
        "```bash",
        deep_indent + "some_command --flag value --other long argument text here",
        "```",
    ]
    all_result_lines = reflow_module.wrap_long_bash_fence_lines(all_input_lines)
    assert len(all_result_lines) == 3
    assert all_result_lines[0] == "```bash"
    assert all_result_lines[2] == "```"
    assert all_result_lines[1] == all_input_lines[1]


def test_is_new_logical_line_recognizes_fence_via_constant() -> None:
    """Code fence detection uses the imported constant marker."""
    assert reflow_module.is_new_logical_line("```bash") is True
    assert reflow_module.is_new_logical_line("```") is True


def test_reflow_structural_line_recognizes_example_tags_via_constant() -> None:
    """Example tag detection uses imported constant markers."""
    assert reflow_module.reflow_structural_line("<example>", "<example>") == ["<example>"]
    close_result = reflow_module.reflow_structural_line("</example>", "</example>")
    assert close_result == ["</example>"]


def test_reflow_structural_line_recognizes_yaml_delimiter_via_constant() -> None:
    """YAML delimiter detection uses imported constant."""
    assert reflow_module.reflow_structural_line("---", "---") == ["---"]


def test_reflow_merged_line_preserves_long_markdown_reference_definition() -> None:
    """Lines matching reference definitions survive reflow without paragraph wrapping."""
    long_url_token = "x" * 90
    line = f"[bugbot-ref]: https://example.com/{long_url_token}"
    stripped_line = line.strip()
    maximum_width = reflow_module.MAX_WIDTH
    assert len(stripped_line) > maximum_width
    assert reflow_module.REF_DEF_RE.match(stripped_line) is not None
    assert reflow_module.reflow_merged_line(line) == [stripped_line]


def test_reflow_bootstrap_moves_script_directory_ahead_of_shadow_config(
    tmp_path: Path,
) -> None:
    """sys.path bootstrap must move the script directory ahead of shadow config packages."""
    shadow_config_directory = tmp_path / "shadow" / "config"
    shadow_config_directory.mkdir(parents=True)
    (shadow_config_directory / "__init__.py").write_text("", encoding="utf-8")
    (shadow_config_directory / "pr_converge_constants.py").write_text(
        "BROKEN = True\n", encoding="utf-8"
    )
    original_sys_path = list(sys.path)
    try:
        sys.path.insert(0, str(_SCRIPTS_DIRECTORY))
        sys.path.insert(0, str(tmp_path / "shadow"))
        loaded_module = _load_module()
        assert loaded_module.SKILL_REFLOW_MAXIMUM_WIDTH == 80
        assert sys.path[0] == str(_SCRIPTS_DIRECTORY)
        assert sys.path.count(str(_SCRIPTS_DIRECTORY)) == 1
    finally:
        sys.path[:] = original_sys_path


def test_wrap_long_bash_line_applies_continuation_indent_to_wrapped_tail() -> None:
    """Wrapped continuation tail lines use the config continuation indent."""
    long_line = "echo " + "word " * 20
    all_result_lines = reflow_module.wrap_long_bash_line(long_line)
    assert len(all_result_lines) > 1, "Line must be long enough to wrap"
    assert all_result_lines[-1].startswith(reflow_module.BASH_CONTINUATION_INDENT), (
        "Final continuation segment must start with the config indent constant"
    )


def test_wrap_long_bash_line_keeps_final_segment_within_width() -> None:
    long_line = "x" * 158
    all_result_lines = reflow_module.wrap_long_bash_line(long_line)
    assert max(len(each_line) for each_line in all_result_lines) == 80


def test_reflow_uses_config_constant_for_continuation_indent() -> None:
    """The bash continuation indent string must come from config, not inline."""
    module_path = _SCRIPTS_DIRECTORY / "reflow_skill_md.py"
    source = module_path.read_text(encoding="utf-8")
    assert "BASH_CONTINUATION_INDENT" in source, (
        "reflow_skill_md.py must import BASH_CONTINUATION_INDENT from config"
    )

def test_reflow_bootstrap_matches_code_rules_sys_path_pattern() -> None:
    """Bootstrap must clear duplicate script_directory entries, then guard insert."""
    module_path = _SCRIPTS_DIRECTORY / "reflow_skill_md.py"
    source = module_path.read_text(encoding="utf-8")
    assert "while script_directory in sys.path:" in source, (
        "Bootstrap must remove all existing script_directory entries with a while loop"
    )
    assert "if script_directory not in sys.path:" in source, (
        "Bootstrap insert must be guarded for code_rules_gate compliance"
    )
    assert "sys.path.insert(0, script_directory)" in source, (
        "Bootstrap must insert script_directory at index 0"
    )
