from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

scripts_directory = Path(__file__).resolve().parents[2] / "scripts"
if str(scripts_directory) not in sys.path:
    sys.path.insert(0, str(scripts_directory))

from verification_notice import build_verification_notice
from verification_notice_context import VerificationNoticeContext
from verification_start import start_automatic_advisory


def build_context(
    repository_root: Path,
    *,
    event: str = "commit",
    repository_remote: str = "jonecho/python-automation",
) -> VerificationNoticeContext:
    git_directory = repository_root / ".git"
    return VerificationNoticeContext(
        event=event,
        repository_remote=repository_remote,
        repository_root=repository_root,
        current_head="a" * 40,
        manifest_path=None,
        manifest_is_available=False,
        git_directory=git_directory,
        report_is_present=False,
        all_report_fields=None,
    )


def write_runner_configuration(repository_root: Path, configuration: object) -> None:
    runner_path = repository_root / ".git" / "local-verification" / "runner.json"
    runner_path.parent.mkdir(parents=True)
    runner_path.write_text(json.dumps(configuration), encoding="utf-8")


def create_runner_configuration(repository_root: Path) -> tuple[str, str]:
    python_path = str(repository_root / "venv" / "Scripts" / "python.exe")
    settings_path = str(repository_root / "settings.json")
    write_runner_configuration(
        repository_root,
        {"python": python_path, "settings": settings_path},
    )
    return python_path, settings_path


def test_start_automatic_advisory_launches_without_waiting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    python_path, settings_path = create_runner_configuration(tmp_path)

    all_launches: list[tuple[object, dict[str, object]]] = []

    class UnwaitedProcess:
        def wait(self) -> None:
            raise AssertionError("native startup must not wait")

    def record_launch(
        command: object,
        **launch_options: object,
    ) -> UnwaitedProcess:
        all_launches.append((command, launch_options))
        return UnwaitedProcess()

    monkeypatch.setattr(subprocess, "Popen", record_launch)

    start_automatic_advisory(build_context(tmp_path))

    assert len(all_launches) == 1
    _assert_launch_matches_runner(
        all_launches[0],
        python_path,
        settings_path,
        tmp_path,
    )


def _assert_launch_matches_runner(
    launch: tuple[object, dict[str, object]],
    python_path: str,
    settings_path: str,
    repository_root: Path,
) -> None:
    command, launch_options = launch
    assert command == [
        python_path,
        str(Path(__file__).resolve().parents[2] / "scripts" / "automatic_advisory" / "cli.py"),
        "--settings",
        settings_path,
        "--start",
    ]
    assert launch_options["cwd"] == repository_root
    assert launch_options["stdin"] is subprocess.DEVNULL
    assert launch_options["stdout"] is subprocess.DEVNULL
    assert launch_options["stderr"] is subprocess.DEVNULL
    assert "--once" not in command


def test_start_automatic_advisory_ignores_malformed_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_path = tmp_path / ".git" / "local-verification" / "runner.json"
    runner_path.parent.mkdir(parents=True)
    runner_path.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *arguments, **options: pytest.fail("malformed configuration launched a process"),
    )

    start_automatic_advisory(build_context(tmp_path))


def test_start_automatic_advisory_ignores_other_repository_and_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_runner_configuration(
        tmp_path,
        {"python": str(tmp_path / "python"), "settings": str(tmp_path / "settings")},
    )
    launch_count = 0

    def count_launches(*arguments: object, **options: object) -> None:
        nonlocal launch_count
        launch_count += 1

    monkeypatch.setattr(subprocess, "Popen", count_launches)

    start_automatic_advisory(
        build_context(tmp_path, repository_remote="other-owner/other-repository")
    )
    start_automatic_advisory(build_context(tmp_path, event="merge"))

    assert launch_count == 0


def test_start_automatic_advisory_ignores_launch_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_runner_configuration(
        tmp_path,
        {"python": str(tmp_path / "python"), "settings": str(tmp_path / "settings")},
    )

    def fail_to_launch(*arguments: object, **options: object) -> None:
        raise OSError("process unavailable")

    monkeypatch.setattr(subprocess, "Popen", fail_to_launch)

    start_automatic_advisory(build_context(tmp_path))


def test_notice_prints_runner_python_in_canonical_command(tmp_path: Path) -> None:
    python_path, settings_path = create_runner_configuration(tmp_path)

    notice_text = build_verification_notice(build_context(tmp_path))

    expected_command = (
        f"& '{python_path}' '{tmp_path / '.github' / 'ci' / 'local_verify.py'}' --base origin/main"
    )
    assert expected_command in notice_text
