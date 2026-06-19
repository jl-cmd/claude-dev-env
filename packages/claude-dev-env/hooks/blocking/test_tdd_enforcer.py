"""Tests for tdd-enforcer hook (blocking behavior)."""

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent / "tdd_enforcer.py"


def _load_production_module():
    module_spec = importlib.util.spec_from_file_location("tdd_enforcer_under_test", SCRIPT_PATH)
    assert module_spec is not None and module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


_PRODUCTION_MODULE = _load_production_module()
FRESHNESS_SECONDS = _PRODUCTION_MODULE._freshness_seconds()
STALE_MTIME_OFFSET_SECONDS = FRESHNESS_SECONDS + 60


def _run_hook_with_payload(
    payload: dict,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    subprocess_env = {**os.environ, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=subprocess_env,
    )


def _make_write_payload(file_path: Path, content: str = "") -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": str(file_path), "content": content},
    }


def _decision_from(completed: subprocess.CompletedProcess[str]) -> str | None:
    if not completed.stdout:
        return None
    parsed = json.loads(completed.stdout)
    hook_output = parsed.get("hookSpecificOutput", {})
    return hook_output.get("permissionDecision")


def _sandbox(tmp_path: Path) -> Path:
    isolated_root = tmp_path / "sandbox"
    isolated_root.mkdir()
    (isolated_root / ".git").mkdir()
    return isolated_root


def test_should_allow_when_sibling_test_file_exists_and_recent(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    production_file.write_text("def fulfill(): pass\n")
    sibling_test = sandbox / "test_orders.py"
    sibling_test.write_text("def test_fulfill(): pass\n")

    completed = _run_hook_with_payload(_make_write_payload(production_file))

    assert _decision_from(completed) == "allow"


def test_should_deny_when_no_test_file_exists(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    production_file.write_text("def fulfill(): pass\n")

    completed = _run_hook_with_payload(_make_write_payload(production_file))

    assert _decision_from(completed) == "deny"
    parsed = json.loads(completed.stdout)
    reason = parsed["hookSpecificOutput"]["permissionDecisionReason"]
    assert "test_orders.py" in reason


def test_should_deny_when_test_file_exists_but_is_stale(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    production_file.write_text("def fulfill(): pass\n")
    sibling_test = sandbox / "test_orders.py"
    sibling_test.write_text("def test_fulfill(): pass\n")
    stale_timestamp = time.time() - STALE_MTIME_OFFSET_SECONDS
    os.utime(sibling_test, (stale_timestamp, stale_timestamp))

    completed = _run_hook_with_payload(_make_write_payload(production_file))

    assert _decision_from(completed) == "deny"


def test_should_deny_when_pragma_no_tdd_gate_sentinel_is_present_without_test(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    content_with_sentinel = "# pragma: no-tdd-gate\ndef fulfill(): pass\n"

    completed = _run_hook_with_payload(
        _make_write_payload(production_file, content_with_sentinel)
    )

    assert _decision_from(completed) == "deny"


def test_should_skip_markdown_files_entirely(tmp_path: Path) -> None:
    markdown_file = tmp_path / "notes.md"

    completed = _run_hook_with_payload(_make_write_payload(markdown_file, "# Notes\n"))

    assert completed.returncode == 0
    assert completed.stdout.strip() == ""


def test_should_skip_test_files_entirely(tmp_path: Path) -> None:
    test_file = tmp_path / "test_orders.py"

    completed = _run_hook_with_payload(
        _make_write_payload(test_file, "def test_fulfill(): pass\n")
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == ""


def test_should_allow_when_tests_directory_sibling_has_fresh_test(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    package_dir = sandbox / "source"
    package_dir.mkdir()
    tests_dir = sandbox / "tests"
    tests_dir.mkdir()
    production_file = package_dir / "orders.py"
    production_file.write_text("def fulfill(): pass\n")
    matching_test = tests_dir / "test_orders.py"
    matching_test.write_text("def test_fulfill(): pass\n")

    completed = _run_hook_with_payload(_make_write_payload(production_file))

    assert _decision_from(completed) == "allow"


def test_should_allow_tsx_when_dot_test_sibling_exists(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "Button.tsx"
    production_file.write_text("export const Button = () => null;\n")
    sibling_test = sandbox / "Button.test.tsx"
    sibling_test.write_text("test('renders', () => {});\n")

    completed = _run_hook_with_payload(_make_write_payload(production_file))

    assert _decision_from(completed) == "allow"


def test_should_deny_when_test_file_has_no_test_evidence(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    production_file.write_text("def fulfill(): pass\n")
    sibling_test = sandbox / "test_orders.py"
    sibling_test.write_text("x = 1\n")

    completed = _run_hook_with_payload(_make_write_payload(production_file))

    assert _decision_from(completed) == "deny"


def test_should_deny_edit_when_pragma_sentinel_present_in_new_string_without_test(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    production_file.write_text("def fulfill(): pass\n")
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(production_file),
            "old_string": "pass",
            "new_string": "# pragma: no-tdd-gate\npass",
        },
    }

    completed = _run_hook_with_payload(payload)

    assert _decision_from(completed) == "deny"


def _make_edit_payload(file_path: Path, old_string: str, new_string: str) -> dict:
    return {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(file_path),
            "old_string": old_string,
            "new_string": new_string,
        },
    }


def test_should_allow_python_file_with_only_module_level_constants(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    constants_file = sandbox / "constants.py"
    constants_only_content = (
        '"""Module-level constants for the widget subsystem."""\n'
        "import re\n"
        "MAXIMUM_RETRIES: int = 3\n"
        "DEFAULT_TIMEOUT_SECONDS: float = 30.0\n"
        'BANNED_WORDS: tuple[str, ...] = ("foo", "bar")\n'
    )
    constants_file.write_text(constants_only_content)

    completed = _run_hook_with_payload(
        _make_write_payload(constants_file, constants_only_content)
    )

    assert _decision_from(completed) == "allow"


def test_should_allow_edit_to_change_constant_value_in_constants_only_file(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    constants_file = sandbox / "constants.py"
    constants_file.write_text(
        '"""Module-level constants."""\n'
        "MAXIMUM_RETRIES: int = 3\n"
        "DEFAULT_TIMEOUT_SECONDS: float = 30.0\n"
    )

    completed = _run_hook_with_payload(
        _make_edit_payload(
            constants_file,
            old_string="MAXIMUM_RETRIES: int = 3",
            new_string="MAXIMUM_RETRIES: int = 5",
        )
    )

    assert _decision_from(completed) == "allow"


def _make_multiedit_payload(file_path: Path, edits: list[dict]) -> dict:
    return {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(file_path),
            "edits": edits,
        },
    }


def test_should_allow_multiedit_to_change_constant_value_in_constants_only_file(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    constants_file = sandbox / "constants.py"
    constants_file.write_text(
        '"""Module-level constants."""\n'
        "MAXIMUM_RETRIES: int = 3\n"
        "DEFAULT_TIMEOUT_SECONDS: float = 30.0\n"
    )

    completed = _run_hook_with_payload(
        _make_multiedit_payload(
            constants_file,
            edits=[
                {
                    "old_string": "MAXIMUM_RETRIES: int = 3",
                    "new_string": "MAXIMUM_RETRIES: int = 5",
                },
            ],
        )
    )

    assert _decision_from(completed) == "allow"


def test_should_deny_multiedit_that_adds_function_to_constants_only_file(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    constants_file = sandbox / "constants.py"
    constants_file.write_text(
        '"""Module-level constants."""\n'
        "MAXIMUM_RETRIES: int = 3\n"
    )

    completed = _run_hook_with_payload(
        _make_multiedit_payload(
            constants_file,
            edits=[
                {
                    "old_string": "MAXIMUM_RETRIES: int = 3",
                    "new_string": "MAXIMUM_RETRIES: int = 3\n\ndef reset() -> None:\n    return None",
                },
            ],
        )
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_edit_that_adds_function_to_constants_only_file(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    constants_file = sandbox / "constants.py"
    constants_file.write_text(
        '"""Module-level constants."""\n'
        "MAXIMUM_RETRIES: int = 3\n"
    )

    completed = _run_hook_with_payload(
        _make_edit_payload(
            constants_file,
            old_string="MAXIMUM_RETRIES: int = 3",
            new_string="MAXIMUM_RETRIES: int = 3\n\ndef reset() -> None:\n    return None",
        )
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_python_file_with_assignment_calling_undefined_function(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    unsafe_file = sandbox / "unsafe.py"
    unsafe_content = (
        '"""Config with unsafe call."""\n'
        "VALUE: str = compute()\n"
    )
    unsafe_file.write_text(unsafe_content)

    completed = _run_hook_with_payload(
        _make_write_payload(unsafe_file, unsafe_content)
    )

    assert _decision_from(completed) == "deny"


def test_should_allow_python_file_with_assignment_calling_imported_function(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    safe_file = sandbox / "safe.py"
    safe_content = (
        '"""Config with imported call."""\n'
        "from pathlib import Path\n"
        "BASE_PATH = Path(r'C:\\\\data')\n"
    )
    safe_file.write_text(safe_content)

    completed = _run_hook_with_payload(
        _make_write_payload(safe_file, safe_content)
    )

    assert _decision_from(completed) == "allow"


def test_should_deny_python_file_when_any_function_definition_is_present(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    mixed_file = sandbox / "mixed.py"
    mixed_content = (
        "MAXIMUM_RETRIES: int = 3\n"
        "def do_something() -> None:\n"
        "    return None\n"
    )
    mixed_file.write_text(mixed_content)

    completed = _run_hook_with_payload(
        _make_write_payload(mixed_file, mixed_content)
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_python_file_when_any_class_definition_is_present(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    class_file = sandbox / "klass.py"
    class_content = (
        "class Widget:\n"
        "    size: int = 3\n"
    )
    class_file.write_text(class_content)

    completed = _run_hook_with_payload(
        _make_write_payload(class_file, class_content)
    )

    assert _decision_from(completed) == "deny"


def test_deny_response_places_system_message_and_suppress_output_at_top_level(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    production_file.write_text("def fulfill(): pass\n")

    completed = _run_hook_with_payload(_make_write_payload(production_file))

    parsed = json.loads(completed.stdout)
    hook_output = parsed["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"
    assert parsed.get("suppressOutput") is True
    assert isinstance(parsed.get("systemMessage"), str)
    assert parsed["systemMessage"]
    assert "suppressOutput" not in hook_output
    assert "systemMessage" not in hook_output
    verbose_reason = hook_output["permissionDecisionReason"]
    assert "propose" in verbose_reason.lower() or "enhancement" in verbose_reason.lower()


def test_should_deny_python_file_that_calls_function_at_module_level(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    side_effect_file = sandbox / "side_effects.py"
    side_effect_content = (
        "import sys\n"
        "sys.exit(1)\n"
    )
    side_effect_file.write_text(side_effect_content)

    completed = _run_hook_with_payload(
        _make_write_payload(side_effect_file, side_effect_content)
    )

    assert _decision_from(completed) == "deny"


def test_should_allow_python_file_with_module_docstring_plus_constants(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    constants_file = sandbox / "constants.py"
    constants_content = (
        '"""Module-level constants for the widget subsystem."""\n'
        "import re\n"
        "MAXIMUM_RETRIES: int = 3\n"
    )
    constants_file.write_text(constants_content)

    completed = _run_hook_with_payload(
        _make_write_payload(constants_file, constants_content)
    )

    assert _decision_from(completed) == "allow"


def test_should_deny_python_file_that_mutates_module_state_via_aug_assign(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    mutation_file = sandbox / "mutation.py"
    mutation_content = (
        "COUNTER: int = 0\n"
        "COUNTER += 1\n"
    )
    mutation_file.write_text(mutation_content)

    completed = _run_hook_with_payload(
        _make_write_payload(mutation_file, mutation_content)
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_production_file_inside_directory_containing_skip_substring(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    mockingbird_directory = sandbox / "mockingbird"
    mockingbird_directory.mkdir()
    production_file = mockingbird_directory / "orders.py"
    production_file.write_text("def fulfill(): pass\n")

    completed = _run_hook_with_payload(_make_write_payload(production_file))

    assert _decision_from(completed) == "deny"


def test_should_deny_when_test_file_contains_only_production_stem_without_test_function(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    production_file.write_text("def fulfill(): pass\n")
    sibling_test = sandbox / "test_orders.py"
    sibling_test.write_text("orders = 'mentioned but no test function'\n")

    completed = _run_hook_with_payload(_make_write_payload(production_file))

    assert _decision_from(completed) == "deny"


def test_should_allow_when_large_test_file_has_valid_test_function_past_first_chunk(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    production_file.write_text("def fulfill(): pass\n")
    sibling_test = sandbox / "test_orders.py"
    padding_byte_count = 250_000
    padding_comment = "# " + ("x" * padding_byte_count) + "\n"
    sibling_test.write_text(padding_comment + "def test_fulfill(): pass\n")

    completed = _run_hook_with_payload(_make_write_payload(production_file))

    assert _decision_from(completed) == "allow"


def test_directory_skip_components_exactly_matches_pre_fc61a8b_hardcoded_set() -> None:
    expected_directory_skip_components = frozenset({
        "conftest", "fixture", "fixtures", "mock", "mocks", "stub", "stubs",
    })

    actual_directory_skip_components = _PRODUCTION_MODULE._directory_skip_components()

    assert actual_directory_skip_components == expected_directory_skip_components


def test_directory_skip_components_excludes_pluralized_conftest() -> None:
    actual_directory_skip_components = _PRODUCTION_MODULE._directory_skip_components()

    assert "conftests" not in actual_directory_skip_components


def test_should_skip_silently_when_posix_path_has_dotclaude_segment(tmp_path: Path) -> None:
    dotclaude_production_file = tmp_path / ".claude" / "agents" / "reviewer.py"

    completed = _run_hook_with_payload(
        _make_write_payload(dotclaude_production_file, "def review(): pass\n")
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == ""


def test_should_skip_silently_when_windows_backslash_path_has_dotclaude_segment() -> None:
    windows_style_path = "C:\\Users\\dev\\.claude\\agents\\reviewer.py"

    completed = _run_hook_with_payload({
        "tool_name": "Write",
        "tool_input": {"file_path": windows_style_path, "content": "def review(): pass\n"},
    })

    assert completed.returncode == 0
    assert completed.stdout.strip() == ""


def test_should_skip_silently_when_mixed_separator_path_has_dotclaude_segment() -> None:
    mixed_separator_path = "C:/Users/dev\\.claude/agents\\reviewer.py"

    completed = _run_hook_with_payload({
        "tool_name": "Write",
        "tool_input": {"file_path": mixed_separator_path, "content": "def review(): pass\n"},
    })

    assert completed.returncode == 0
    assert completed.stdout.strip() == ""


def test_should_not_skip_when_dotclaude_is_only_a_filename_substring(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    substring_production_file = sandbox / "my.claude.helpers.py"
    substring_production_file.write_text("def help(): pass\n")

    completed = _run_hook_with_payload(_make_write_payload(substring_production_file))

    assert _decision_from(completed) == "deny"


def test_is_inside_dotclaude_segment_helper_matches_only_exact_segments() -> None:
    assert _PRODUCTION_MODULE._is_inside_dotclaude_segment("/home/user/.claude/agent.py") is True
    assert _PRODUCTION_MODULE._is_inside_dotclaude_segment("C:\\Users\\dev\\.claude\\agent.py") is True
    assert _PRODUCTION_MODULE._is_inside_dotclaude_segment("/src/my.claude.helpers.py") is False
    assert _PRODUCTION_MODULE._is_inside_dotclaude_segment("/src/app/service.py") is False


def test_should_offer_split_family_test_files_as_candidates_for_code_rules_module(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "code_rules_magic_values.py"
    string_magic_family_test = sandbox / "test_code_rules_enforcer_split_string_magic.py"
    string_magic_family_test.write_text("def test_string_magic(): pass\n")
    banned_family_test = sandbox / "test_code_rules_enforcer_split_banned.py"
    banned_family_test.write_text("def test_banned(): pass\n")

    all_candidates = _PRODUCTION_MODULE.candidate_test_paths_for(production_module)

    assert string_magic_family_test in all_candidates
    assert banned_family_test in all_candidates


def test_should_keep_plain_stem_candidates_first_for_code_rules_module(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "code_rules_magic_values.py"
    family_test = sandbox / "test_code_rules_enforcer_split_string_magic.py"
    family_test.write_text("def test_string_magic(): pass\n")

    all_candidates = _PRODUCTION_MODULE.candidate_test_paths_for(production_module)

    assert all_candidates[0] == sandbox / "test_code_rules_magic_values.py"
    assert all_candidates[1] == sandbox / "code_rules_magic_values_test.py"


def test_should_not_offer_split_family_candidates_for_non_code_rules_module(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    family_test = sandbox / "test_code_rules_enforcer_split_string_magic.py"
    family_test.write_text("def test_string_magic(): pass\n")

    all_candidates = _PRODUCTION_MODULE.candidate_test_paths_for(production_module)

    assert family_test not in all_candidates


def test_should_add_no_split_family_candidates_when_directory_has_none(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "code_rules_magic_values.py"

    all_candidates = _PRODUCTION_MODULE.candidate_test_paths_for(production_module)

    expected_stem_candidates = [
        sandbox / "test_code_rules_magic_values.py",
        sandbox / "code_rules_magic_values_test.py",
    ]
    assert all_candidates == expected_stem_candidates


def test_should_not_offer_family_candidates_for_code_ruleset_stem(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "code_ruleset.py"
    family_test = sandbox / "test_code_rules_enforcer_split_example.py"
    family_test.write_text("def test_detects_example(): pass\n")

    all_candidates = _PRODUCTION_MODULE.candidate_test_paths_for(production_module)

    expected_stem_candidates = [
        sandbox / "test_code_ruleset.py",
        sandbox / "code_ruleset_test.py",
    ]
    assert all_candidates == expected_stem_candidates
    assert family_test not in all_candidates


def test_should_allow_code_rules_edit_when_fresh_split_family_sibling_exists(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "code_rules_example.py"
    production_module.write_text("def detect() -> None:\n    return None\n")
    family_test = sandbox / "test_code_rules_enforcer_split_example_concern.py"
    family_test.write_text("def test_detects_example(): pass\n")

    payload = _make_edit_payload(
        production_module,
        old_string="return None",
        new_string="return None  # adjusted",
    )
    completed = _run_hook_with_payload(payload)

    assert _decision_from(completed) == "allow"


def test_should_deny_code_rules_edit_when_split_family_sibling_is_stale(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "code_rules_example.py"
    production_module.write_text("def detect() -> None:\n    return None\n")
    family_test = sandbox / "test_code_rules_enforcer_split_example_concern.py"
    family_test.write_text("def test_detects_example(): pass\n")
    stale_timestamp = time.time() - STALE_MTIME_OFFSET_SECONDS
    os.utime(family_test, (stale_timestamp, stale_timestamp))

    payload = _make_edit_payload(
        production_module,
        old_string="return None",
        new_string="return None  # adjusted",
    )
    completed = _run_hook_with_payload(payload)

    assert _decision_from(completed) == "deny"


def test_should_offer_nested_package_mirroring_candidate_for_subpackage_module(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    package_root = sandbox / "pkg"
    subpackage_directory = package_root / "services" / "mouse_movement"
    subpackage_directory.mkdir(parents=True)
    (package_root / "tests").mkdir()
    production_module = subpackage_directory / "tremor.py"

    all_candidates = _PRODUCTION_MODULE.candidate_test_paths_for(production_module)

    assert package_root / "tests" / "services" / "test_tremor.py" in all_candidates
    assert (
        package_root / "tests" / "services" / "mouse_movement" / "test_tremor.py"
        in all_candidates
    )


def test_should_offer_flat_candidate_alongside_nested_candidates(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    package_root = sandbox / "pkg"
    subpackage_directory = package_root / "services" / "mouse_movement"
    subpackage_directory.mkdir(parents=True)
    (package_root / "tests").mkdir()
    production_module = subpackage_directory / "tremor.py"

    all_candidates = _PRODUCTION_MODULE.candidate_test_paths_for(production_module)

    assert package_root / "tests" / "test_tremor.py" in all_candidates
    assert (
        package_root / "tests" / "services" / "mouse_movement" / "test_tremor.py"
        in all_candidates
    )


def test_should_allow_write_when_nested_package_mirroring_test_is_fresh(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    package_root = sandbox / "pkg"
    subpackage_directory = package_root / "services" / "mouse_movement"
    subpackage_directory.mkdir(parents=True)
    nested_tests_directory = package_root / "tests" / "services" / "mouse_movement"
    nested_tests_directory.mkdir(parents=True)
    production_module = subpackage_directory / "tremor.py"
    production_module.write_text("def jitter(): pass\n")
    nested_test = nested_tests_directory / "test_tremor.py"
    nested_test.write_text("def test_jitter(): pass\n")

    completed = _run_hook_with_payload(_make_write_payload(production_module))

    assert _decision_from(completed) == "allow"


def test_should_collect_tests_directories_from_every_ancestor_up_to_repo_boundary(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    package_root = sandbox / "pkg"
    subpackage_directory = package_root / "services"
    subpackage_directory.mkdir(parents=True)
    (package_root / "tests").mkdir()
    (subpackage_directory / "tests").mkdir()

    all_pairs = _PRODUCTION_MODULE._ancestor_tests_directories(subpackage_directory)

    collected_tests_directories = [each_tests_directory for _, each_tests_directory in all_pairs]
    assert subpackage_directory / "tests" in collected_tests_directories
    assert package_root / "tests" in collected_tests_directories


def test_ancestor_tests_walk_stops_at_repo_boundary(tmp_path: Path) -> None:
    outer_tests_directory = tmp_path / "tests"
    outer_tests_directory.mkdir()
    sandbox = _sandbox(tmp_path)
    package_directory = sandbox / "pkg"
    package_directory.mkdir()

    all_pairs = _PRODUCTION_MODULE._ancestor_tests_directories(package_directory)

    collected_tests_directories = [each_tests_directory for _, each_tests_directory in all_pairs]
    assert outer_tests_directory not in collected_tests_directories


def test_ancestor_tests_walk_honors_parent_walk_limit(tmp_path: Path) -> None:
    walk_limit = _PRODUCTION_MODULE._parent_walk_limit()
    deep_directory = tmp_path
    for each_level_index in range(walk_limit + 2):
        deep_directory = deep_directory / f"level_{each_level_index}"
    deep_directory.mkdir(parents=True)
    top_tests_directory = tmp_path / "tests"
    top_tests_directory.mkdir()

    all_pairs = _PRODUCTION_MODULE._ancestor_tests_directories(deep_directory)

    collected_tests_directories = [each_tests_directory for _, each_tests_directory in all_pairs]
    assert top_tests_directory not in collected_tests_directories


def test_should_deny_edit_that_swaps_an_import_target(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\n\ndef fulfill(): pass\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="import os",
            new_string="import sys",
        )
    )

    assert _decision_from(completed) == "deny"


def _run_hook_with_payload_and_env(
    payload: dict,
    extra_env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, **extra_env},
    )


_BEHAVIOR_BEARING_CONTENT = "def fulfill_order(order: str) -> str:\n    return order\n"


def test_should_exit_zero_for_ephemeral_scratch_python() -> None:
    """B16: behavior-bearing scratch .py under root-anchored /tmp exits 0 with no deny."""
    ephemeral_path = "/tmp/scratch_work.py"
    payload = _make_write_payload(Path(ephemeral_path), _BEHAVIOR_BEARING_CONTENT)
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) != "deny", (
        f"TDD enforcer must not deny ephemeral Python path, got: {completed.stdout!r}"
    )


def test_should_exit_zero_for_ephemeral_scratch_typescript() -> None:
    """B17: ephemeral .ts scratch file under root-anchored /tmp exits 0 with no deny."""
    ephemeral_path = "/tmp/scratch_work.ts"
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": ephemeral_path,
            "content": "export function fulfillOrder(order: string): string { return order; }\n",
        },
    }
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) != "deny", (
        f"TDD enforcer must not deny ephemeral TypeScript path, got: {completed.stdout!r}"
    )


def test_should_still_deny_non_ephemeral_python_without_test() -> None:
    """B18: a non-ephemeral .py file with no matching test still receives a deny."""
    non_ephemeral_path = "/repo/src/orders.py"
    payload = _make_write_payload(Path(non_ephemeral_path), _BEHAVIOR_BEARING_CONTENT)
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) == "deny", (
        f"TDD enforcer must deny non-ephemeral production file, got: {completed.stdout!r}"
    )


def test_should_deny_ephemeral_scratch_when_override_truthy() -> None:
    """B19: with override set, an ephemeral scratch .py with no test still receives a deny."""
    ephemeral_path = "/tmp/scratch_work.py"
    payload = _make_write_payload(Path(ephemeral_path), _BEHAVIOR_BEARING_CONTENT)
    completed = _run_hook_with_payload_and_env(
        payload,
        extra_env={"CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT": "1"},
    )
    assert _decision_from(completed) == "deny", (
        f"TDD enforcer must deny ephemeral path when override is set, got: {completed.stdout!r}"
    )


def test_should_exit_before_fresh_test_lookup_for_ephemeral(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B20: the ephemeral exit precedes the fresh-test candidate search.

    Spies on candidate_test_paths_for and asserts it is never reached for a
    scratch .py under $CLAUDE_JOB_DIR/tmp, proving the early exit short-circuits
    before any test-file lookup runs.
    """
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path))
    candidate_search_call_count = {"count": 0}

    def _spy_candidate_test_paths_for(production_path: Path) -> list[Path]:
        candidate_search_call_count["count"] += 1
        return []

    monkeypatch.setattr(
        _PRODUCTION_MODULE, "candidate_test_paths_for", _spy_candidate_test_paths_for
    )
    scratch_path = str(tmp_path / "tmp" / "scratch_work.py")
    payload = _make_write_payload(Path(scratch_path), _BEHAVIOR_BEARING_CONTENT)
    monkeypatch.setattr(_PRODUCTION_MODULE.sys, "stdin", io.StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit) as raised_exit:
        _PRODUCTION_MODULE.main()
    assert int(raised_exit.value.code or 0) == 0
    assert candidate_search_call_count["count"] == 0, (
        "candidate_test_paths_for must not run for an ephemeral scratch path"
    )


def test_should_allow_edit_that_removes_an_import_statement(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\n\ndef fulfill(): pass\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="import os\n",
            new_string="",
        )
    )

    assert _decision_from(completed) == "allow"


def test_should_allow_multiedit_when_every_pair_removes_an_import(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\nimport json\nimport time\n\ndef fulfill(): pass\n")

    completed = _run_hook_with_payload(
        _make_multiedit_payload(
            production_module,
            edits=[
                {"old_string": "import os\n", "new_string": ""},
                {"old_string": "import json\n", "new_string": ""},
            ],
        )
    )

    assert _decision_from(completed) == "allow"


def test_should_deny_multiedit_when_one_pair_is_not_import_only(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\n\ndef fulfill(): pass\n")

    completed = _run_hook_with_payload(
        _make_multiedit_payload(
            production_module,
            edits=[
                {"old_string": "import os", "new_string": "import sys"},
                {
                    "old_string": "def fulfill(): pass",
                    "new_string": "def fulfill(): return 1",
                },
            ],
        )
    )

    assert _decision_from(completed) == "deny"


def test_should_not_exempt_write_with_behavior_under_import_only_rule(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    write_content_with_behavior = "import os\n\ndef fulfill(): return os.getpid()\n"

    completed = _run_hook_with_payload(
        _make_write_payload(production_module, write_content_with_behavior)
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_behavior_edit_without_a_fresh_candidate_test(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("def fulfill(): pass\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="def fulfill(): pass",
            new_string="def fulfill(): return 1",
        )
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_edit_of_import_text_inside_a_string_literal(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text('banner = "import os is great"\n\ndef fulfill(): return banner\n')

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="import os",
            new_string="import sys",
        )
    )

    assert _decision_from(completed) == "deny"


def test_should_allow_import_reorder_when_old_string_carries_context_lines(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\nimport sys\n\ndef fulfill(): pass\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="import os\nimport sys\n\ndef fulfill(): pass",
            new_string="import sys\nimport os\n\ndef fulfill(): pass",
        )
    )

    assert _decision_from(completed) == "allow"


def test_should_allow_import_only_edit_after_a_constants_assignment(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\nimport sys\n\nMAX_ORDERS = 5\n\ndef fulfill(): pass\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="import os\n",
            new_string="",
        )
    )

    assert _decision_from(completed) == "allow"


def test_should_deny_replace_all_edit_that_rewrites_call_sites(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import json\n\ndef parse(line): return json.loads(line)\n")

    completed = _run_hook_with_payload(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(production_module),
                "old_string": "json",
                "new_string": "pickle",
                "replace_all": True,
            },
        }
    )

    assert _decision_from(completed) == "deny"


def test_should_allow_edit_that_reorders_import_statements(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\nimport sys\n\ndef fulfill(): pass\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="import os\nimport sys",
            new_string="import sys\nimport os",
        )
    )

    assert _decision_from(completed) == "allow"


def test_should_deny_edit_that_retargets_an_import_source(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("from fast import compute\n\ndef run(): return compute()\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="from fast import compute",
            new_string="from slow import compute",
        )
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_edit_that_adds_a_future_import(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\n\ndef fulfill(): return os.getpid()\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="import os",
            new_string="from __future__ import annotations\nimport os",
        )
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_multiedit_with_an_empty_edits_list(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\n\ndef fulfill(): return os.getpid()\n")

    completed = _run_hook_with_payload(
        _make_multiedit_payload(production_module, edits=[])
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_edit_that_removes_a_future_import(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text(
        "from __future__ import annotations\nimport os\n\ndef fulfill(): return os.getpid()\n"
    )

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="from __future__ import annotations\n",
            new_string="",
        )
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_edit_that_adds_an_import(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\n\ndef fulfill(): pass\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="import os",
            new_string="import os\nimport sys",
        )
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_edit_that_duplicates_an_import(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("import os\n\ndef fulfill(): pass\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="import os",
            new_string="import os\nimport os",
        )
    )

    assert _decision_from(completed) == "deny"


def test_should_deny_changing_a_future_import_on_a_constants_only_file(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_module = sandbox / "orders.py"
    production_module.write_text("from __future__ import annotations\nMAX_ORDERS = 5\n")

    completed = _run_hook_with_payload(
        _make_edit_payload(
            production_module,
            old_string="from __future__ import annotations",
            new_string="from __future__ import division",
        )
    )

    assert _decision_from(completed) == "deny"
