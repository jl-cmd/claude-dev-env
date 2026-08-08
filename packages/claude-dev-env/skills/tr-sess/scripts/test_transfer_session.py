"""Behaviour tests for the tr-sess session transfer script.

Each test builds a real profile tree on disk and runs the real transfer, so the
copy, the truncation, the hash check, the divergence guard, and the .claude.json
registration are all exercised against real files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
for each_import_root in (SCRIPTS_DIRECTORY / "config", SCRIPTS_DIRECTORY):
    if str(each_import_root) not in sys.path:
        sys.path.insert(0, str(each_import_root))

import transfer_session
from tr_sess_scripts_constants import (
    transfer_session_constants as constants,
)

SESSION_ID = "11111111-2222-3333-4444-555555555555"
PROJECT_KEY = "C--dev-scratch"
WORKING_DIRECTORY = "C:\\dev\\scratch"
SOURCE_PROFILE = "alpha"
DESTINATION_PROFILE = "beta"


def build_record(record_type: str, **extra: object) -> dict[str, object]:
    record = {
        constants.RECORD_TYPE_KEY: record_type,
        constants.RECORD_SESSION_ID_KEY: SESSION_ID,
        constants.RECORD_CWD_KEY: WORKING_DIRECTORY,
    }
    record.update(extra)
    return record


def write_transcript(path: Path, records: list[dict[str, object]], trailing_partial: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(record) + "\n" for record in records)
    if trailing_partial:
        body += '{"type":"user","incompl'
    path.write_text(body, encoding="utf-8", newline="")


def make_profiles(root: Path, destination_config: dict[str, object] | None = None) -> None:
    for profile in (SOURCE_PROFILE, DESTINATION_PROFILE):
        (root / profile / constants.PROJECTS_DIRECTORY_NAME).mkdir(parents=True, exist_ok=True)
    config = destination_config if destination_config is not None else {constants.CONFIG_PROJECTS_KEY: {}}
    (root / DESTINATION_PROFILE / constants.CONFIG_FILE_NAME).write_text(
        json.dumps(config), encoding="utf-8"
    )


def source_transcript_path(root: Path) -> Path:
    return (
        root
        / SOURCE_PROFILE
        / constants.PROJECTS_DIRECTORY_NAME
        / PROJECT_KEY
        / f"{SESSION_ID}{constants.TRANSCRIPT_SUFFIX}"
    )


def destination_transcript_path(root: Path) -> Path:
    return (
        root
        / DESTINATION_PROFILE
        / constants.PROJECTS_DIRECTORY_NAME
        / PROJECT_KEY
        / f"{SESSION_ID}{constants.TRANSCRIPT_SUFFIX}"
    )


def run_transfer(root: Path, *extra_arguments: str) -> tuple[int, dict[str, object]]:
    arguments = [
        "--source",
        SOURCE_PROFILE,
        "--destination",
        DESTINATION_PROFILE,
        "--session-id",
        SESSION_ID,
        "--profiles-root",
        str(root),
        *extra_arguments,
    ]
    return transfer_session.run(arguments)


def should_copy_transcript_and_register_project(tmp_path: Path) -> None:
    make_profiles(tmp_path)
    records = [build_record("user"), build_record("assistant")]
    write_transcript(source_transcript_path(tmp_path), records)

    exit_code, payload = run_transfer(tmp_path)

    assert exit_code == constants.EXIT_CODE_SUCCESS
    destination = destination_transcript_path(tmp_path)
    assert destination.exists()
    assert destination.read_bytes() == source_transcript_path(tmp_path).read_bytes()
    assert payload[constants.PAYLOAD_COPIED_LINES_KEY] == len(records)
    assert payload[constants.PAYLOAD_HASH_MATCH_KEY] is True
    assert payload[constants.PAYLOAD_PROJECT_KEY] == PROJECT_KEY

    config = json.loads(
        (tmp_path / DESTINATION_PROFILE / constants.CONFIG_FILE_NAME).read_text(encoding="utf-8")
    )
    assert WORKING_DIRECTORY in config[constants.CONFIG_PROJECTS_KEY]
    assert config[constants.CONFIG_PROJECTS_KEY][WORKING_DIRECTORY]["hasTrustDialogAccepted"] is True


def should_truncate_partial_trailing_line(tmp_path: Path) -> None:
    make_profiles(tmp_path)
    records = [build_record("user"), build_record("assistant")]
    write_transcript(source_transcript_path(tmp_path), records, trailing_partial=True)

    exit_code, payload = run_transfer(tmp_path)

    assert exit_code == constants.EXIT_CODE_SUCCESS
    copied = destination_transcript_path(tmp_path).read_text(encoding="utf-8")
    assert copied.endswith("\n")
    assert payload[constants.PAYLOAD_COPIED_LINES_KEY] == len(records)
    assert payload[constants.PAYLOAD_HASH_MATCH_KEY] is True
    for line in copied.splitlines():
        json.loads(line)


def should_copy_sidecar_directories(tmp_path: Path) -> None:
    make_profiles(tmp_path)
    write_transcript(source_transcript_path(tmp_path), [build_record("user")])
    session_directory = source_transcript_path(tmp_path).parent / SESSION_ID
    session_directory.mkdir(parents=True)
    (session_directory / "note.txt").write_text("sidecar", encoding="utf-8")
    for name in constants.ALL_SIDECAR_DIRECTORY_NAMES:
        sidecar = tmp_path / SOURCE_PROFILE / name / SESSION_ID
        sidecar.mkdir(parents=True)
        (sidecar / "entry.json").write_text("{}", encoding="utf-8")

    exit_code, payload = run_transfer(tmp_path)

    assert exit_code == constants.EXIT_CODE_SUCCESS
    assert (destination_transcript_path(tmp_path).parent / SESSION_ID / "note.txt").exists()
    for name in constants.ALL_SIDECAR_DIRECTORY_NAMES:
        assert (tmp_path / DESTINATION_PROFILE / name / SESSION_ID / "entry.json").exists()
    assert sorted(payload[constants.PAYLOAD_SIDECARS_KEY]) == sorted(
        [SESSION_ID, *constants.ALL_SIDECAR_DIRECTORY_NAMES]
    )


def should_refuse_when_destination_carries_extra_work(tmp_path: Path) -> None:
    make_profiles(tmp_path)
    write_transcript(source_transcript_path(tmp_path), [build_record("user")])
    write_transcript(
        destination_transcript_path(tmp_path),
        [build_record("user"), build_record("assistant"), build_record("user")],
    )
    destination_before = destination_transcript_path(tmp_path).read_bytes()

    exit_code, payload = run_transfer(tmp_path)

    assert exit_code == constants.EXIT_CODE_DESTINATION_DIVERGED
    assert destination_transcript_path(tmp_path).read_bytes() == destination_before
    assert "force" in str(payload["error"])


def should_overwrite_diverged_destination_when_forced(tmp_path: Path) -> None:
    make_profiles(tmp_path)
    write_transcript(source_transcript_path(tmp_path), [build_record("user")])
    write_transcript(
        destination_transcript_path(tmp_path),
        [build_record("user"), build_record("assistant"), build_record("user")],
    )

    exit_code, payload = run_transfer(tmp_path, "--force")

    assert exit_code == constants.EXIT_CODE_SUCCESS
    assert payload[constants.PAYLOAD_COPIED_LINES_KEY] == 1
    assert destination_transcript_path(tmp_path).read_bytes() == source_transcript_path(
        tmp_path
    ).read_bytes()


def should_refresh_destination_when_source_grew(tmp_path: Path) -> None:
    make_profiles(tmp_path)
    write_transcript(source_transcript_path(tmp_path), [build_record("user")])
    run_transfer(tmp_path)
    write_transcript(
        source_transcript_path(tmp_path),
        [build_record("user"), build_record("assistant")],
    )

    exit_code, payload = run_transfer(tmp_path)

    assert exit_code == constants.EXIT_CODE_SUCCESS
    assert payload[constants.PAYLOAD_COPIED_LINES_KEY] == 2
    assert payload[constants.PAYLOAD_CONFIG_ACTION_KEY] == constants.CONFIG_ACTION_PRESENT


def should_report_usage_error_for_unknown_session(tmp_path: Path) -> None:
    make_profiles(tmp_path)

    exit_code, payload = run_transfer(tmp_path)

    assert exit_code == constants.EXIT_CODE_USAGE_ERROR
    assert SESSION_ID in str(payload["error"])


def should_list_sessions_in_source_profile(tmp_path: Path) -> None:
    make_profiles(tmp_path)
    write_transcript(
        source_transcript_path(tmp_path),
        [
            build_record("user"),
            build_record(
                constants.CUSTOM_TITLE_RECORD_TYPE,
                **{constants.RECORD_CUSTOM_TITLE_KEY: "Icons workflow"},
            ),
        ],
    )

    exit_code, payload = transfer_session.run(
        [
            "--source",
            SOURCE_PROFILE,
            "--destination",
            DESTINATION_PROFILE,
            "--profiles-root",
            str(tmp_path),
            "--list",
        ]
    )

    assert exit_code == constants.EXIT_CODE_SUCCESS
    sessions = payload[constants.PAYLOAD_SESSIONS_KEY]
    assert len(sessions) == 1
    assert sessions[0][constants.PAYLOAD_SESSION_ID_KEY] == SESSION_ID
    assert sessions[0][constants.PAYLOAD_TITLE_KEY] == "Icons workflow"
    assert sessions[0][constants.PAYLOAD_PROJECT_KEY] == PROJECT_KEY


def should_skip_registration_when_destination_has_no_config(tmp_path: Path) -> None:
    make_profiles(tmp_path)
    (tmp_path / DESTINATION_PROFILE / constants.CONFIG_FILE_NAME).unlink()
    write_transcript(source_transcript_path(tmp_path), [build_record("user")])

    exit_code, payload = run_transfer(tmp_path)

    assert exit_code == constants.EXIT_CODE_SUCCESS
    assert payload[constants.PAYLOAD_CONFIG_ACTION_KEY] == constants.CONFIG_ACTION_SKIPPED_NO_CONFIG
    assert destination_transcript_path(tmp_path).exists()


def should_back_up_config_before_first_registration(tmp_path: Path) -> None:
    make_profiles(tmp_path)
    write_transcript(source_transcript_path(tmp_path), [build_record("user")])

    run_transfer(tmp_path)

    backup = (
        tmp_path
        / DESTINATION_PROFILE
        / f"{constants.CONFIG_FILE_NAME}{constants.CONFIG_BACKUP_SUFFIX}"
    )
    assert backup.exists()
    assert json.loads(backup.read_text(encoding="utf-8"))[constants.CONFIG_PROJECTS_KEY] == {}


def should_reject_source_profile_that_does_not_exist(tmp_path: Path) -> None:
    make_profiles(tmp_path)

    exit_code, payload = transfer_session.run(
        [
            "--source",
            "missing-profile",
            "--destination",
            DESTINATION_PROFILE,
            "--session-id",
            SESSION_ID,
            "--profiles-root",
            str(tmp_path),
        ]
    )

    assert exit_code == constants.EXIT_CODE_USAGE_ERROR
    assert "missing-profile" in str(payload["error"])


def should_reject_transfer_into_the_same_profile(tmp_path: Path) -> None:
    make_profiles(tmp_path)
    write_transcript(source_transcript_path(tmp_path), [build_record("user")])

    exit_code, payload = transfer_session.run(
        [
            "--source",
            SOURCE_PROFILE,
            "--destination",
            SOURCE_PROFILE,
            "--session-id",
            SESSION_ID,
            "--profiles-root",
            str(tmp_path),
        ]
    )

    assert exit_code == constants.EXIT_CODE_USAGE_ERROR
    assert "same profile" in str(payload["error"])


def should_print_payload_and_return_exit_code_from_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    make_profiles(tmp_path)
    write_transcript(source_transcript_path(tmp_path), [build_record("user")])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "transfer_session.py",
            "--source",
            SOURCE_PROFILE,
            "--destination",
            DESTINATION_PROFILE,
            "--session-id",
            SESSION_ID,
            "--profiles-root",
            str(tmp_path),
        ],
    )

    exit_code = transfer_session.main()

    assert exit_code == constants.EXIT_CODE_SUCCESS
    printed = json.loads(capsys.readouterr().out)
    assert printed[constants.PAYLOAD_HASH_MATCH_KEY] is True
    assert destination_transcript_path(tmp_path).exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
