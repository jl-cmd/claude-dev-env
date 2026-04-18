"""Tests for tdd-enforcer hook (blocking behavior)."""

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path


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


def _run_hook_with_payload(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
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


def test_should_allow_when_bypass_sentinel_present_in_content(tmp_path: Path) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    content_with_sentinel = "# pragma: no-tdd-gate\ndef fulfill(): pass\n"

    completed = _run_hook_with_payload(
        _make_write_payload(production_file, content_with_sentinel)
    )

    assert _decision_from(completed) == "allow"


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


def test_should_allow_edit_when_bypass_sentinel_present_in_new_string(
    tmp_path: Path,
) -> None:
    sandbox = _sandbox(tmp_path)
    production_file = sandbox / "orders.py"
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(production_file),
            "old_string": "pass",
            "new_string": "# pragma: no-tdd-gate\npass",
        },
    }

    completed = _run_hook_with_payload(payload)

    assert _decision_from(completed) == "allow"


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
