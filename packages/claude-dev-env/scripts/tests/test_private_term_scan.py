"""Behavior tests for the GitHub event private-term scan."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from dev_env_scripts_constants.private_term_constants import PrivateTermDigest

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

import private_term_scan

_FIXTURE_TERM = "acmewidget"
_CLEAN_IDENTITY = ("Claude", "noreply@example.com")


@pytest.fixture(autouse=True)
def private_fixture_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        private_term_scan,
        "ALL_PRIVATE_TERM_DIGESTS",
        frozenset(
            {
                PrivateTermDigest(
                    length=len(_FIXTURE_TERM),
                    sha256=hashlib.sha256(_FIXTURE_TERM.encode("utf-8")).hexdigest(),
                )
            }
        ),
    )


def _write_event(tmp_path: Path, event: dict[str, object]) -> Path:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    return event_path


def _git(repository_root: Path, *all_arguments: str, name: str, email: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *all_arguments],
        check=True,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(repository_root),
        },
    )
    return completed.stdout.strip()


def _repository_with_commits(
    tmp_path: Path, all_commits: list[tuple[str, str, str]]
) -> tuple[Path, str, str]:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _git(
        repository_root, "init", "-q", name=_CLEAN_IDENTITY[0], email=_CLEAN_IDENTITY[1]
    )
    _git(
        repository_root,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "base",
        name=_CLEAN_IDENTITY[0],
        email=_CLEAN_IDENTITY[1],
    )
    base = _git(repository_root, "rev-parse", "HEAD", name="x", email="x@example.com")
    for each_message, each_name, each_email in all_commits:
        _git(
            repository_root,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            each_message,
            name=each_name,
            email=each_email,
        )
    head = _git(repository_root, "rev-parse", "HEAD", name="x", email="x@example.com")
    return repository_root, base, head


def test_should_flag_a_pull_request_body_line(tmp_path: Path) -> None:
    event_path = _write_event(
        tmp_path,
        {
            "pull_request": {
                "title": "fix: one",
                "body": "Why\nSee Acme-Widgets-Inc/x#1\n",
            }
        },
    )
    all_findings = private_term_scan.scan_event(event_path)
    assert all_findings == [
        "pull request body: Line 2 names a private organization. "
        "Describe it in general terms and drop any link to it."
    ]


def test_should_flag_a_pull_request_title(tmp_path: Path) -> None:
    event_path = _write_event(
        tmp_path, {"pull_request": {"title": "fix: acme widget upload", "body": None}}
    )
    assert private_term_scan.scan_event(event_path)[0].startswith("pull request title:")


@pytest.mark.parametrize(
    ("event", "label"),
    [
        ({"comment": {"body": "by acme widgets"}}, "comment body"),
        ({"review": {"body": "by acme widgets"}}, "review body"),
        ({"issue": {"title": "clean", "body": "by acme widgets"}}, "issue body"),
        ({"release": {"name": "v1", "body": "by acme widgets"}}, "release body"),
    ],
)
def test_should_flag_each_event_text(
    tmp_path: Path, event: dict[str, object], label: str
) -> None:
    all_findings = private_term_scan.scan_event(_write_event(tmp_path, event))
    assert len(all_findings) == 1
    assert all_findings[0].startswith(f"{label}: Line 1")


def test_should_pass_a_clean_event(tmp_path: Path) -> None:
    event_path = _write_event(
        tmp_path,
        {"comment": {"body": "Looks good."}, "issue": {"title": "t", "body": None}},
    )
    assert private_term_scan.scan_event(event_path) == []


def test_should_flag_a_commit_message_and_a_commit_identity(tmp_path: Path) -> None:
    repository_root, base, head = _repository_with_commits(
        tmp_path,
        [
            ("fix: clean change", "Pat", "pat@acmewidgets.example.com"),
            ("docs: note\n\nWritten for Acme Widgets.", *_CLEAN_IDENTITY),
            ("chore: clean", *_CLEAN_IDENTITY),
        ],
    )
    all_findings = private_term_scan.scan_commits(repository_root, f"{base}..{head}")
    assert len(all_findings) == 2
    assert all_findings[0].startswith("commit ")
    assert " identity:" in all_findings[0]
    assert " message: Line 3 " in all_findings[1]
    assert all("acme" not in each_finding.lower() for each_finding in all_findings)


def test_should_skip_a_github_noreply_address_in_a_commit_identity(
    tmp_path: Path,
) -> None:
    repository_root, base, head = _repository_with_commits(
        tmp_path,
        [
            ("fix: clean change", "Pat", "81234567+acmewidget@users.noreply.github.com"),
            ("chore: clean", *_CLEAN_IDENTITY),
        ],
    )
    assert private_term_scan.scan_commits(repository_root, f"{base}..{head}") == []


def test_should_flag_a_private_name_beside_a_github_noreply_address(
    tmp_path: Path,
) -> None:
    repository_root, base, head = _repository_with_commits(
        tmp_path,
        [
            ("fix: clean change", "Acme Widget", "81234567+pat@users.noreply.github.com"),
            ("chore: clean", *_CLEAN_IDENTITY),
        ],
    )
    all_findings = private_term_scan.scan_commits(repository_root, f"{base}..{head}")
    assert len(all_findings) == 1
    assert " identity:" in all_findings[0]


def test_should_print_findings_and_fail_from_the_command_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    event_path = _write_event(tmp_path, {"comment": {"body": "by acme widgets"}})
    exit_code = private_term_scan.main(["--event-path", str(event_path)])
    assert exit_code == 1
    assert "comment body: Line 1" in capsys.readouterr().out


def test_should_pass_from_the_command_line_on_a_clean_event(tmp_path: Path) -> None:
    event_path = _write_event(tmp_path, {"comment": {"body": "fine"}})
    assert private_term_scan.main(["--event-path", str(event_path)]) == 0
