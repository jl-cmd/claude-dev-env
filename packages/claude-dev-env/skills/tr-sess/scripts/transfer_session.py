"""Copy one Claude Code session from a source profile into a destination profile.

A session is a transcript, its sibling session directory, its task and env state,
and a working-directory entry in the destination profile's ``.claude.json``.

Copy a session::

    --source alpha --destination beta --session-id aaaaaaaa-...-eeeeeeeeeeee

    {"copiedBytes": 448, "copiedLines": 3, "hashMatch": true}   ok
    {"error": "destination transcript has 537 bytes ..."}       flagged, exit 3

The copy stops at the last complete line, because a live session keeps appending,
and is checked against the same-length prefix of the source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent / "config") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "config"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from tr_sess_scripts_constants import (
    transfer_session_constants as constants,
)


def _parse_arguments(all_command_arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transfer_session",
        description="Copy a Claude Code session from one profile to another.",
    )
    parser.add_argument("--source", required=True, help="source profile name")
    parser.add_argument("--destination", required=True, help="destination profile name")
    parser.add_argument("--session-id", default=None, help="session uuid to copy")
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_sessions",
        help="list sessions in the source profile",
    )
    parser.add_argument(
        "--profiles-root",
        default=None,
        help="profiles root directory; defaults to the per-user root",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace a destination transcript that carries extra work",
    )
    return parser.parse_args(all_command_arguments)


def _resolve_profiles_root(raw_profiles_root: str | None) -> Path:
    if raw_profiles_root:
        return Path(raw_profiles_root)
    return Path.home() / constants.PROFILES_ROOT_DIRECTORY_NAME


def _find_transcript(profile_root: Path, session_id: str) -> Path | None:
    projects_root = profile_root / constants.PROJECTS_DIRECTORY_NAME
    if not projects_root.is_dir():
        return None
    file_name = f"{session_id}{constants.TRANSCRIPT_SUFFIX}"
    for each_candidate in projects_root.glob(f"*/{file_name}"):
        if each_candidate.is_file():
            return each_candidate
    return None


def _read_records(path: Path) -> list[dict[str, object]]:
    all_records: list[dict[str, object]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for each_line in handle:
            stripped = each_line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                all_records.append(parsed)
    return all_records


def _read_working_directory(path: Path) -> str | None:
    for each_record in _read_records(path):
        working_directory = each_record.get(constants.RECORD_CWD_KEY)
        if isinstance(working_directory, str) and working_directory:
            return working_directory
    return None


def _read_title(path: Path) -> str | None:
    custom_title = None
    generated_title = None
    for each_record in _read_records(path):
        record_type = each_record.get(constants.RECORD_TYPE_KEY)
        if record_type == constants.CUSTOM_TITLE_RECORD_TYPE:
            custom_title_text = each_record.get(constants.RECORD_CUSTOM_TITLE_KEY)
            if isinstance(custom_title_text, str) and custom_title_text:
                custom_title = custom_title_text
        elif record_type == constants.AI_TITLE_RECORD_TYPE:
            generated_title_text = each_record.get(constants.RECORD_AI_TITLE_KEY)
            if isinstance(generated_title_text, str) and generated_title_text:
                generated_title = generated_title_text
    return custom_title or generated_title


def _list_sessions(profile_root: Path) -> list[dict[str, object]]:
    projects_root = profile_root / constants.PROJECTS_DIRECTORY_NAME
    if not projects_root.is_dir():
        return []

    all_dated_sessions: list[tuple[int, dict[str, object]]] = []
    for each_transcript in projects_root.glob(f"*/*{constants.TRANSCRIPT_SUFFIX}"):
        if not each_transcript.is_file():
            continue
        statistics = each_transcript.stat()
        modified_seconds = int(statistics.st_mtime)
        all_dated_sessions.append(
            (
                modified_seconds,
                {
                    constants.PAYLOAD_SESSION_ID_KEY: each_transcript.stem,
                    constants.PAYLOAD_PROJECT_KEY: each_transcript.parent.name,
                    constants.PAYLOAD_TITLE_KEY: _read_title(each_transcript),
                    constants.PAYLOAD_BYTES_KEY: statistics.st_size,
                    constants.PAYLOAD_MODIFIED_KEY: modified_seconds,
                },
            )
        )
    all_dated_sessions.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in all_dated_sessions]


def _complete_line_length(payload: bytes) -> int:
    last_newline_index = payload.rfind(bytes([constants.NEWLINE_BYTE]))
    if last_newline_index < 0:
        return 0
    return last_newline_index + 1


def _hash_bytes(payload: bytes) -> str:
    digest = hashlib.new(constants.HASH_ALGORITHM_NAME)
    digest.update(payload)
    return digest.hexdigest()


def _hash_source_prefix(path: Path, length: int) -> str:
    digest = hashlib.new(constants.HASH_ALGORITHM_NAME)
    remaining = length
    with path.open("rb") as handle:
        while remaining > 0:
            chunk = handle.read(min(constants.FILE_READ_CHUNK_SIZE, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def _copy_transcript(source: Path, destination: Path) -> dict[str, object]:
    source_bytes_at_copy = source.stat().st_size
    payload = source.read_bytes()
    trimmed = payload[: _complete_line_length(payload)]

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(trimmed)

    return {
        constants.PAYLOAD_SOURCE_BYTES_KEY: source_bytes_at_copy,
        constants.PAYLOAD_COPIED_BYTES_KEY: len(trimmed),
        constants.PAYLOAD_COPIED_LINES_KEY: trimmed.count(bytes([constants.NEWLINE_BYTE])),
        constants.PAYLOAD_HASH_MATCH_KEY: _hash_bytes(trimmed)
        == _hash_source_prefix(source, len(trimmed)),
    }


def _copy_directory(source: Path, destination: Path) -> bool:
    if not source.is_dir():
        return False
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return True


def _copy_sidecars(
    source_profile: Path,
    destination_profile: Path,
    source_transcript: Path,
    destination_transcript: Path,
    session_id: str,
) -> list[str]:
    all_copied: list[str] = []
    if _copy_directory(
        source_transcript.parent / session_id, destination_transcript.parent / session_id
    ):
        all_copied.append(session_id)
    for each_directory_name in constants.ALL_SIDECAR_DIRECTORY_NAMES:
        if _copy_directory(
            source_profile / each_directory_name / session_id,
            destination_profile / each_directory_name / session_id,
        ):
            all_copied.append(each_directory_name)
    return all_copied


def _register_project(destination_profile: Path, working_directory: str | None) -> str:
    config_path = destination_profile / constants.CONFIG_FILE_NAME
    if not config_path.is_file():
        return constants.CONFIG_ACTION_SKIPPED_NO_CONFIG
    if not working_directory:
        return constants.CONFIG_ACTION_SKIPPED_NO_CWD

    config = json.loads(config_path.read_text(encoding="utf-8"))
    all_projects = config.setdefault(constants.CONFIG_PROJECTS_KEY, {})
    if working_directory in all_projects:
        return constants.CONFIG_ACTION_PRESENT

    backup_path = config_path.with_name(
        f"{constants.CONFIG_FILE_NAME}{constants.CONFIG_BACKUP_SUFFIX}"
    )
    if not backup_path.exists():
        shutil.copy2(config_path, backup_path)

    all_projects[working_directory] = dict(constants.ALL_PROJECT_ENTRY_DEFAULTS)
    config_path.write_text(
        json.dumps(config, indent=constants.JSON_INDENT_WIDTH, ensure_ascii=False), encoding="utf-8", newline="\n"
    )
    return constants.CONFIG_ACTION_ADDED


def _destination_has_extra_work(source: Path, destination: Path) -> bool:
    if not destination.is_file():
        return False
    return destination.stat().st_size > source.stat().st_size


def _validate_request(
    arguments: argparse.Namespace, source_profile: Path, destination_profile: Path
) -> dict[str, object] | None:
    if arguments.source == arguments.destination:
        return {"error": "source and destination name the same profile"}
    if not destination_profile.is_dir():
        return {"error": f"destination profile not found: {arguments.destination}"}
    if not arguments.session_id:
        return {"error": "--session-id is required unless --list is given"}
    return None


def _perform_transfer(
    arguments: argparse.Namespace,
    source_profile: Path,
    destination_profile: Path,
    source_transcript: Path,
) -> tuple[int, dict[str, object]]:
    project_key = source_transcript.parent.name
    destination_transcript = (
        destination_profile
        / constants.PROJECTS_DIRECTORY_NAME
        / project_key
        / source_transcript.name
    )

    if not arguments.force and _destination_has_extra_work(
        source_transcript, destination_transcript
    ):
        message = constants.DIVERGED_MESSAGE_TEMPLATE.format(
            destination_bytes=destination_transcript.stat().st_size,
            source_bytes=source_transcript.stat().st_size,
        )
        return constants.EXIT_CODE_DESTINATION_DIVERGED, {"error": message}

    working_directory = _read_working_directory(source_transcript)
    copy_report = _copy_transcript(source_transcript, destination_transcript)
    all_sidecars = _copy_sidecars(
        source_profile,
        destination_profile,
        source_transcript,
        destination_transcript,
        arguments.session_id,
    )

    payload: dict[str, object] = {
        constants.PAYLOAD_SOURCE_PROFILE_KEY: arguments.source,
        constants.PAYLOAD_DESTINATION_PROFILE_KEY: arguments.destination,
        constants.PAYLOAD_SESSION_ID_KEY: arguments.session_id,
        constants.PAYLOAD_PROJECT_KEY: project_key,
        constants.PAYLOAD_WORKING_DIRECTORY_KEY: working_directory,
        constants.PAYLOAD_SIDECARS_KEY: all_sidecars,
        constants.PAYLOAD_CONFIG_ACTION_KEY: _register_project(
            destination_profile, working_directory
        ),
    }
    payload.update(copy_report)
    return constants.EXIT_CODE_SUCCESS, payload


def run(all_command_arguments: list[str]) -> tuple[int, dict[str, object]]:
    """Copy or list a session according to the given command-line arguments.

    Args:
        all_command_arguments: Command-line arguments without the program name,
            for example ``["--source", "alpha", "--destination", "beta"]``.

    Returns:
        A pair of the process exit code and the JSON-ready result payload. The
        payload carries the copy report on success, the session list under
        ``--list``, and an ``error`` key for a usage error or a divergence.
    """
    arguments = _parse_arguments(all_command_arguments)
    profiles_root = _resolve_profiles_root(arguments.profiles_root)
    source_profile = profiles_root / arguments.source
    destination_profile = profiles_root / arguments.destination

    if not source_profile.is_dir():
        return constants.EXIT_CODE_USAGE_ERROR, {
            "error": f"source profile not found: {arguments.source}"
        }

    if arguments.list_sessions:
        return constants.EXIT_CODE_SUCCESS, {
            constants.PAYLOAD_SOURCE_PROFILE_KEY: arguments.source,
            constants.PAYLOAD_SESSIONS_KEY: _list_sessions(source_profile),
        }

    validation_error = _validate_request(arguments, source_profile, destination_profile)
    if validation_error is not None:
        return constants.EXIT_CODE_USAGE_ERROR, validation_error

    source_transcript = _find_transcript(source_profile, arguments.session_id)
    if source_transcript is None:
        return constants.EXIT_CODE_USAGE_ERROR, {
            "error": f"session not found in source profile: {arguments.session_id}"
        }

    return _perform_transfer(
        arguments, source_profile, destination_profile, source_transcript
    )


def main() -> int:
    """Run the transfer from ``sys.argv`` and print the result as JSON.

    Args:
        None. Arguments are read from ``sys.argv``.

    Returns:
        The process exit code produced by :func:`run`.
    """
    exit_code, payload = run(sys.argv[1:])
    print(json.dumps(payload, indent=constants.JSON_INDENT_WIDTH, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
