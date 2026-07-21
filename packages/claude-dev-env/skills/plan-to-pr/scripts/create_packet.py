"""Create a deterministic native plan-to-PR packet skeleton."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from config.constants import (
    PACKET_CREATION_ERROR_EXIT_CODE,
    PACKET_JSON_INDENT_LEVEL,
    SLUG_PATTERN,
)


def _parse_arguments() -> argparse.Namespace:
    """Parse packet creation arguments."""
    parser = argparse.ArgumentParser(
        description="Create a native planning packet skeleton."
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--base-ref", required=True)
    return parser.parse_args()


def _validate_slug(slug: str) -> None:
    """Raise an error when a slug cannot name one plan directory."""
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError(
            "slug must contain lowercase letters, numbers, and single hyphens"
        )


def _resolve_base_commit(repo_root: Path, base_ref: str) -> str:
    """Resolve a base ref to its full commit hash."""
    if base_ref.startswith("-"):
        raise ValueError("base-ref must not start with a hyphen")
    completed_command = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "rev-parse",
            "--verify",
            f"{base_ref}^{{commit}}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed_command.returncode != 0:
        error_message = completed_command.stderr.strip() or "unable to resolve base-ref"
        raise ValueError(error_message)
    return completed_command.stdout.strip()


def _build_packet_payload(
    slug: str, base_ref: str, base_commit: str
) -> dict[str, object]:
    """Build the schema-shaped packet manifest without repository assumptions."""
    return {
        "schema_version": 1,
        "slug": slug,
        "status": "draft",
        "request": f"Plan work for {slug}.",
        "allowed_files": [],
        "sources": [],
        "decisions": [
            f"Base ref {base_ref} resolves to commit {base_commit}.",
            "Scope is pending planner review.",
        ],
        "open_questions": [
            "What repository behavior and files does the request require?"
        ],
        "tasks": [
            {
                "id": "task-1",
                "deliverable": "Planner-defined deliverable",
                "allowed_files": ["docs/plans/" + slug],
                "acceptance_command": "Planner-defined acceptance command",
                "test_command": "Planner-defined test command",
                "verification_command": "Planner-defined verification command",
                "commit": 1,
            }
        ],
        "validation": {
            "schema_valid": False,
            "boundary_valid": False,
            "markdown_matches": False,
            "validated_by": "native-plan-to-pr",
        },
    }


def _write_packet_file(packet_file: Path, packet_text: str) -> None:
    """Write one packet file using stable UTF-8 content."""
    packet_file.write_text(packet_text, encoding="utf-8", newline="\n")


def create_packet(repo_root: Path, slug: str, base_ref: str) -> Path:
    """Create and return a new packet directory under the repository plans path.

    Args:
        repo_root: Repository containing the plans directory.
        slug: Packet directory slug.
        base_ref: Git reference used for the packet decision record.
    Returns:
        The created packet directory.
    Raises:
        ValueError: If the slug or base reference is invalid.
        FileExistsError: If the packet directory already exists.
    """
    _validate_slug(slug)
    resolved_repo_root = repo_root.resolve()
    base_commit = _resolve_base_commit(resolved_repo_root, base_ref)
    packet_directory = resolved_repo_root / "docs" / "plans" / slug
    if packet_directory.exists():
        raise FileExistsError(f"packet already exists: {packet_directory}")

    for each_directory in (
        packet_directory,
        packet_directory / "requirements",
        packet_directory / "tasks",
    ):
        each_directory.mkdir(parents=True, exist_ok=True)

    packet_payload = _build_packet_payload(slug, base_ref, base_commit)
    packet_json = (
        json.dumps(packet_payload, indent=PACKET_JSON_INDENT_LEVEL, sort_keys=True)
        + "\n"
    )
    packet_files = {
        "packet.json": packet_json,
        "context.md": "# Context\n\nThe planner records repository facts and source references here.\n",
        "plan.md": "# Plan\n\nThe planner records ordered implementation decisions here.\n",
        "tasks.md": "# Tasks\n\nThe planner records one deliverable per task here.\n",
        "handoff.md": "# Handoff\n\nThe planner records the approved host task seed here.\n",
        "requirements/README.md": "# Requirements\n\nThe planner records confirmed requirements here.\n",
        "tasks/README.md": "# Task Records\n\nThe planner records task details here.\n",
    }
    for each_relative_path, each_file_text in packet_files.items():
        _write_packet_file(packet_directory / each_relative_path, each_file_text)
    return packet_directory


def main() -> int:
    """Create a packet and print its repository-relative path.

    Returns:
        The process status code.
    """
    parsed_arguments = _parse_arguments()
    try:
        packet_directory = create_packet(
            parsed_arguments.repo_root,
            parsed_arguments.slug,
            parsed_arguments.base_ref,
        )
    except (FileExistsError, OSError, ValueError) as packet_error:
        print(str(packet_error), file=sys.stderr)
        return PACKET_CREATION_ERROR_EXIT_CODE
    print(packet_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
