"""Mutation-style tests for the Plan-to-PR packet validator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


VALIDATOR_PATH = Path(__file__).with_name("validate_packet.py")


def write_packet(packet_directory: Path) -> None:
    """Create a complete packet and its grounded source file."""
    packet_directory.mkdir(parents=True)
    repository_root = packet_directory.parents[2]
    source_file = repository_root / "src" / "auth.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(
        "def authenticate_user():\n    return True\n", encoding="utf-8"
    )
    task_details = "## Tasks\n- task-1: Login validation; src/auth.py; python -m pytest tests/test_auth.py; python -m pytest tests/test_auth.py; python -m compileall src/auth.py\n"
    for filename, sections in {
        "context.md": (
            "Request",
            "Repository Facts",
            "Constraints",
            "Source References",
        ),
        "plan.md": ("Implementation", "Decisions", "Dependencies", "Risks"),
        "tasks.md": (),
        "handoff.md": ("Approval", "Task Order"),
    }.items():
        headings = "\n".join(
            f"## {section}\nGrounded packet detail." for section in sections
        )
        if filename == "tasks.md":
            headings = task_details.rstrip()
        if filename == "handoff.md":
            headings += "\nPacket: add-login\nApproval: approved\nTask Order: task-1\nTask task-1: Login validation\nAllowed files: src/auth.py\nAcceptance command: python -m pytest tests/test_auth.py\nTest command: python -m pytest tests/test_auth.py\nVerification command: python -m compileall src/auth.py"
        (packet_directory / filename).write_text(headings + "\n", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "slug": packet_directory.name,
        "status": "approved",
        "request": "Add login validation.",
        "allowed_files": ["src/auth.py"],
        "sources": [
            {
                "path": "src/auth.py",
                "locator": "section authenticate_user",
                "fact": "The helper returns the login decision.",
            }
        ],
        "decisions": ["Reuse the existing helper."],
        "open_questions": [],
        "tasks": [
            {
                "id": "task-1",
                "deliverable": "Login validation",
                "allowed_files": ["src/auth.py"],
                "acceptance_command": "python -m pytest tests/test_auth.py",
                "test_command": "python -m pytest tests/test_auth.py",
                "verification_command": "python -m compileall src/auth.py",
                "commit": 1,
            }
        ],
        "validation": {
            "schema_valid": True,
            "boundary_valid": True,
            "markdown_matches": True,
            "validated_by": "native-plan-to-pr",
        },
    }
    (packet_directory / "packet.json").write_text(json.dumps(payload), encoding="utf-8")


def run_validator(packet_directory: Path) -> subprocess.CompletedProcess[str]:
    """Run the validator as a real CLI process."""
    return subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(packet_directory)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_packet_passes(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode == 0
    assert validator_run.stdout.strip() == "packet validation passed"


def test_missing_packet_file_reports_field(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    (packet_directory / "plan.md").unlink()
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "missing required file: plan.md" in validator_run.stderr


def test_placeholder_packet_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    (packet_directory / "context.md").write_text(
        "## Request\nTODO: fill this in", encoding="utf-8"
    )
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "context.md: contains unresolved" in validator_run.stderr


def test_task_scope_outside_allowed_files_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    packet_file = packet_directory / "packet.json"
    packet_payload = json.loads(packet_file.read_text(encoding="utf-8"))
    packet_payload["tasks"][0]["allowed_files"] = ["src/other.py"]
    packet_file.write_text(json.dumps(packet_payload), encoding="utf-8")
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "outside packet scope" in validator_run.stderr


def test_unknown_schema_field_fails(tmp_path: Path) -> None:
    """Schema-shaped packets reject fields outside the packet contract."""
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    packet_file = packet_directory / "packet.json"
    packet_payload = json.loads(packet_file.read_text(encoding="utf-8"))
    packet_payload["unexpected"] = True
    packet_file.write_text(json.dumps(packet_payload), encoding="utf-8")
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "unknown field: unexpected" in validator_run.stderr


def test_cyclic_dependencies_fail(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    packet_file = packet_directory / "packet.json"
    packet_payload = json.loads(packet_file.read_text(encoding="utf-8"))
    packet_payload["tasks"].append(
        {
            "id": "task-2",
            "deliverable": "Second change",
            "allowed_files": ["src/auth.py"],
            "acceptance_command": "python -m pytest tests/test_auth.py",
            "test_command": "python -m pytest tests/test_auth.py",
            "verification_command": "python -m compileall src/auth.py",
            "commit": 1,
            "dependencies": ["task-1"],
        }
    )
    packet_payload["tasks"][0]["dependencies"] = ["task-2"]
    packet_file.write_text(json.dumps(packet_payload), encoding="utf-8")
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "dependency cycle detected" in validator_run.stderr


def test_duplicate_dependencies_fail(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    packet_file = packet_directory / "packet.json"
    packet_payload = json.loads(packet_file.read_text(encoding="utf-8"))
    packet_payload["tasks"][0]["dependencies"] = ["task-1", "task-1"]
    packet_file.write_text(json.dumps(packet_payload), encoding="utf-8")
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "dependencies: entries must be unique" in validator_run.stderr


def test_incomplete_handoff_fails(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    (packet_directory / "handoff.md").write_text(
        "## Approval\nApproval: approved\n## Task Order\nTask Order: task-1\n",
        encoding="utf-8",
    )
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "handoff.md: task task-1 missing deliverable" in validator_run.stderr


def test_handoff_rejects_wrong_slug_approval_order_and_suffixed_commands(
    tmp_path: Path,
) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    handoff_file = packet_directory / "handoff.md"
    handoff_text = handoff_file.read_text(encoding="utf-8")
    handoff_file.write_text(
        handoff_text.replace("Packet: add-login", "Packet: add-login-extra")
        .replace("Approval: approved", "Approval: pending")
        .replace("Task Order: task-1", "Task Order: task-2, task-1")
        .replace(
            "Acceptance command: python -m pytest tests/test_auth.py",
            "Acceptance command: python -m pytest tests/test_auth.py --quiet",
        ),
        encoding="utf-8",
    )
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "missing packet slug" in validator_run.stderr
    assert "missing approval state" in validator_run.stderr
    assert "task order does not match" in validator_run.stderr
    assert "missing acceptance command" in validator_run.stderr


def test_task_markdown_rejects_suffixed_commands(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    tasks_file = packet_directory / "tasks.md"
    task_text = tasks_file.read_text(encoding="utf-8")
    tasks_file.write_text(
        task_text.replace(
            "python -m pytest tests/test_auth.py;",
            "python -m pytest tests/test_auth.py --quiet;",
        ),
        encoding="utf-8",
    )
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "tasks.md: task task-1 missing acceptance_command" in validator_run.stderr


def test_handoff_rejects_undeclared_task(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    handoff_file = packet_directory / "handoff.md"
    handoff_file.write_text(
        handoff_file.read_text(encoding="utf-8") + "\nTask task-2: Undeclared task\n",
        encoding="utf-8",
    )
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "handoff.md: declared tasks do not match packet.json" in validator_run.stderr


def test_source_locator_and_path_boundaries_fail(tmp_path: Path) -> None:
    packet_directory = tmp_path / "docs" / "plans" / "add-login"
    write_packet(packet_directory)
    packet_file = packet_directory / "packet.json"
    packet_payload = json.loads(packet_file.read_text(encoding="utf-8"))
    packet_payload["sources"][0]["locator"] = "authenticate_user"
    packet_payload["sources"][0]["path"] = "src/auth..py"
    packet_file.write_text(json.dumps(packet_payload), encoding="utf-8")
    validator_run = run_validator(packet_directory)
    assert validator_run.returncode != 0
    assert "locator: must be line, lines, or section locator" in validator_run.stderr
    assert "path: must be a repository-relative path" in validator_run.stderr
