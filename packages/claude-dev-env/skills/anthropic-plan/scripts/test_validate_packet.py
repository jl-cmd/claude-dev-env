"""Tests for the plan packet validator."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPTS_DIRECTORY / "validate_packet.py"


def load_validator_module() -> ModuleType:
    if str(SCRIPTS_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIRECTORY))
    spec = importlib.util.spec_from_file_location("validate_packet", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    validator_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator_module)
    return validator_module


def write_valid_packet(packet_directory: Path) -> None:
    all_relative_paths = load_validator_module().required_relative_paths()
    for each_relative_path in all_relative_paths:
        target_path = packet_directory / each_relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(valid_markdown_for(each_relative_path), encoding="utf-8")

    packet_payload = {
        "schemaVersion": 1,
        "slug": "add-login",
        "repoRoot": str(packet_directory.parent.parent.parent),
        "packetPath": str(packet_directory),
        "sourceFiles": ["src/auth.py"],
        "assumptions": ["No migration is needed."],
        "validator": {"deterministic": "pending", "semantic": "pending"},
    }
    (packet_directory / "packet.json").write_text(
        json.dumps(packet_payload, indent=2),
        encoding="utf-8",
    )


def valid_markdown_for(relative_path: str) -> str:
    if relative_path == "context/source-map.md":
        return (
            "# Source Map\n\n"
            "| Source | Why it matters | Facts extracted | Plan implication |\n"
            "|---|---|---|---|\n"
            "| src/auth.py | Login flow entrypoint | Existing authenticate_user function handles password checks. | Reuse authenticate_user in the implementation. |\n"
        )
    if relative_path == "implementation/tdd-plan.md":
        return (
            "# TDD Plan\n\n"
            "1. Failing test: add test_auth_login_success before production edits.\n"
            "2. Production code: wire the existing authenticate_user call.\n"
            "3. Refactor after green: remove duplicated setup.\n"
        )
    if relative_path == "implementation/steps.md":
        return (
            "# Steps\n\n"
            "1. Test first: add login success coverage.\n"
            "2. Production change: add the route handler; covered by test_auth_login_success.\n"
        )
    if relative_path == "handoff/build-prompt.md":
        return (
            "# Build Prompt\n\n"
            "Use only this packet. Read README.md, then context/source-map.md, then implementation/steps.md. "
            "Do not rely on prior chat history."
        )
    return f"# {relative_path}\n\nGrounded implementation detail for this packet file.\n"


def run_validator(packet_directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(packet_directory)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_packet_passes(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 0, validator_run.stderr
    assert "packet validation passed" in validator_run.stdout


def test_missing_required_file_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "spec" / "behavior.md").unlink()

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 2
    assert "missing required file: spec/behavior.md" in validator_run.stderr


def test_placeholder_text_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "spec" / "scope.md").write_text("TODO: fill this in", encoding="utf-8")

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 2
    assert "placeholder text" in validator_run.stderr


@pytest.mark.parametrize(
    "template_placeholder_markdown",
    [
        "# <Plan Title>\n\nThis plan implements the feature.",
        "This plan implements <feature name> for the <component> module.",
        "| <path> | <reason> | <verified fact> | <implementation implication> |",
    ],
)
def test_angle_bracket_placeholder_text_fails(
    tmp_path: Path,
    template_placeholder_markdown: str,
) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "spec" / "scope.md").write_text(
        template_placeholder_markdown,
        encoding="utf-8",
    )

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 2
    assert "spec/scope.md contains placeholder text" in validator_run.stderr


@pytest.mark.parametrize(
    "non_placeholder_markdown",
    [
        "<details>\n<summary>Notes</summary>\nGrounded detail.\n</details>",
        "Type the annotation as `list[str]` and call `<command>` from a code span.",
        "Reach the endpoint with `curl <url>` inside the inline code span.",
        "The comparison `attempt_count < threshold` must hold before the retry.",
    ],
)
def test_inline_html_and_code_does_not_flag_placeholder(
    tmp_path: Path,
    non_placeholder_markdown: str,
) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "spec" / "scope.md").write_text(
        non_placeholder_markdown,
        encoding="utf-8",
    )

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 0, validator_run.stderr


def test_open_questions_heading_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "validation" / "unresolved-risks.md").write_text(
        "## Open Questions\n- Which database?",
        encoding="utf-8",
    )

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 2
    assert "Open Questions" in validator_run.stderr


def test_weak_source_map_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "context" / "source-map.md").write_text(
        "# Source Map\n\nNo sources yet.\n",
        encoding="utf-8",
    )

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 2
    assert "source-map.md must include source-grounded rows" in validator_run.stderr


def test_missing_tdd_plan_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "implementation" / "tdd-plan.md").write_text(
        "# TDD Plan\n\nImplementation can start directly.",
        encoding="utf-8",
    )

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 2
    assert "tdd-plan.md must name failing tests" in validator_run.stderr


@pytest.mark.parametrize(
    "forbidden_phrase",
    ["as discussed above", "from our chat", "previous conversation", "earlier in this thread"],
)
def test_handoff_prompt_depending_on_chat_history_fails(
    tmp_path: Path,
    forbidden_phrase: str,
) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "handoff" / "build-prompt.md").write_text(
        f"# Build Prompt\n\nUse the details {forbidden_phrase}.",
        encoding="utf-8",
    )

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 2
    assert "build-prompt.md must stand alone" in validator_run.stderr


def test_tdd_plan_with_red_only_as_substring_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "implementation" / "tdd-plan.md").write_text(
        "# TDD Plan\n\nImplementation is required. Wire production code directly.",
        encoding="utf-8",
    )

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 2
    assert "tdd-plan.md must name failing tests" in validator_run.stderr


def test_tdd_plan_naming_red_step_passes(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "implementation" / "tdd-plan.md").write_text(
        "# TDD Plan\n\n1. Red step: add the failing coverage.\n2. Green production code follows.",
        encoding="utf-8",
    )

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 0, validator_run.stderr


def test_packet_path_with_forward_slashes_matches_native_directory(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    packet_file = packet_directory / "packet.json"
    packet_payload = json.loads(packet_file.read_text(encoding="utf-8"))
    packet_payload["packetPath"] = packet_directory.as_posix()
    packet_file.write_text(json.dumps(packet_payload, indent=2), encoding="utf-8")

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 0, validator_run.stderr


def test_packet_path_with_trailing_separator_matches_directory(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    packet_file = packet_directory / "packet.json"
    packet_payload = json.loads(packet_file.read_text(encoding="utf-8"))
    packet_payload["packetPath"] = str(packet_directory) + "/"
    packet_file.write_text(json.dumps(packet_payload, indent=2), encoding="utf-8")

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 0, validator_run.stderr


def test_packet_path_mismatch_still_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    packet_file = packet_directory / "packet.json"
    packet_payload = json.loads(packet_file.read_text(encoding="utf-8"))
    packet_payload["packetPath"] = str(packet_directory.parent / "different-slug")
    packet_file.write_text(json.dumps(packet_payload, indent=2), encoding="utf-8")

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 2
    assert "packet.json packetPath must match the validated packet directory" in validator_run.stderr


def test_source_map_with_bare_non_python_source_passes(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "context" / "source-map.md").write_text(
        "# Source Map\n\n"
        "| Source | Why it matters | Facts extracted | Plan implication |\n"
        "|---|---|---|---|\n"
        "| plan-packet.mjs | Workflow entry | Exports the run function. | Reuse the run shape. |\n",
        encoding="utf-8",
    )

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 0, validator_run.stderr


def test_source_map_with_only_version_number_row_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_valid_packet(packet_directory)
    (packet_directory / "context" / "source-map.md").write_text(
        "# Source Map\n\n"
        "| Source | Why it matters | Facts extracted | Plan implication |\n"
        "|---|---|---|---|\n"
        "| The login subsystem | We reviewed version 2.0 of the design | No file path named here | Build accordingly |\n",
        encoding="utf-8",
    )

    validator_run = run_validator(packet_directory)

    assert validator_run.returncode == 2
    assert "source-map.md must include source-grounded rows" in validator_run.stderr
