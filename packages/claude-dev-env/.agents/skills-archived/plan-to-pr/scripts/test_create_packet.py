"""Behavior tests for the native packet skeleton CLI."""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

script_path = Path(__file__).with_name("create_packet.py")
script_spec = importlib.util.spec_from_file_location("create_packet", script_path)
assert script_spec is not None
assert script_spec.loader is not None
script_module = importlib.util.module_from_spec(script_spec)
sys.modules["create_packet"] = script_module
script_spec.loader.exec_module(script_module)
create_packet = script_module.create_packet


def initialize_repository(repository_path: Path) -> str:
    """Create a temporary Git repository and return its commit hash."""
    subprocess.run(
        ["git", "-C", str(repository_path), "init"], check=True, capture_output=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repository_path),
            "config",
            "user.email",
            "test@example.invalid",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository_path), "config", "user.name", "Test User"],
        check=True,
    )
    (repository_path / "README.md").write_text("repository\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository_path), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(repository_path), "commit", "-m", "initial"],
        check=True,
        capture_output=True,
    )
    return subprocess.check_output(
        ["git", "-C", str(repository_path), "rev-parse", "HEAD"], text=True
    ).strip()


def test_create_packet_writes_deterministic_skeleton(tmp_path: Path) -> None:
    """A packet contains the schema fields, base commit, and stable files."""
    base_commit = initialize_repository(tmp_path)

    packet_directory = create_packet(tmp_path, "sample-plan", "HEAD")

    packet_payload = json.loads(
        (packet_directory / "packet.json").read_text(encoding="utf-8")
    )
    assert packet_payload["status"] == "draft"
    assert base_commit in packet_payload["decisions"][0]
    assert (packet_directory / "requirements" / "README.md").is_file()
    assert (packet_directory / "tasks" / "README.md").is_file()
    assert sorted(path.name for path in packet_directory.glob("*.md")) == [
        "context.md",
        "handoff.md",
        "plan.md",
        "tasks.md",
    ]


@pytest.mark.parametrize(
    "unsafe_slug", ["../escape", "Upper", "with space", "-leading"]
)
def test_create_packet_rejects_unsafe_slug(tmp_path: Path, unsafe_slug: str) -> None:
    """Unsafe slugs fail before a plan directory is created."""
    initialize_repository(tmp_path)

    with pytest.raises(ValueError):
        create_packet(tmp_path, unsafe_slug, "HEAD")

    assert not (tmp_path / "docs" / "plans").exists()


def test_create_packet_rejects_existing_packet(tmp_path: Path) -> None:
    """Existing packet directories remain untouched."""
    initialize_repository(tmp_path)
    packet_directory = create_packet(tmp_path, "sample-plan", "HEAD")
    packet_json_before_retry = (packet_directory / "packet.json").read_text(
        encoding="utf-8"
    )

    with pytest.raises(FileExistsError):
        create_packet(tmp_path, "sample-plan", "HEAD")

    assert (packet_directory / "packet.json").read_text(
        encoding="utf-8"
    ) == packet_json_before_retry
