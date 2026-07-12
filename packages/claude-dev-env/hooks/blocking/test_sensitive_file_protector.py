"""Decision tests for the sensitive-file filename guard.

Each case drives the real hook script through its production ``__main__``
stdin path, feeding it the PreToolUse JSON payload Claude Code sends and
reading the permission decision back off stdout.

The guard denies a filename that names a live secret or a lock file, and
steps aside for a placeholders-only committed template (``.env.example``
and its ``.sample`` / ``.template`` spellings). The template exemption is
narrow: ``.env.local`` is a ``.env.*`` filename that is not a template, and
it stays denied.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BLOCKING_DIRECTORY = Path(__file__).resolve().parent
HOOK_SCRIPT_PATH = BLOCKING_DIRECTORY / "sensitive_file_protector.py"

WRITE_TOOL_NAME = "Write"
EDIT_TOOL_NAME = "Edit"
READ_TOOL_NAME = "Read"

DENY_DECISION = "deny"

PLACEHOLDER_TEMPLATE_BODY = "API_TOKEN=your-token-here\nDATABASE_HOST=localhost\n"
ORDINARY_SOURCE_BODY = "def add(left: int, right: int) -> int:\n    return left + right\n"

ALL_TEMPLATE_FILENAMES = (
    ".env.example",
    ".env.sample",
    ".env.template",
    ".ENV.Example",
    "settings.json.template",
)

ALL_DENIED_FILENAMES = (
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
    "server.pem",
    "signing.key",
    "bundle.p12",
    "bundle.pfx",
    "package-lock.json",
    "yarn.lock",
    "Pipfile.lock",
    "poetry.lock",
    "pnpm-lock.yaml",
    "composer.lock",
)

ALL_UPPERCASE_DENIED_FILENAMES = (".ENV", "ID_RSA", "CREDENTIALS.JSON", "SERVER.PEM")

ALL_ORDINARY_FILENAMES = ("main.py", "README.md", "settings.json")


def _run_hook(tool_name: str, file_path: Path, content: str) -> subprocess.CompletedProcess:
    payload = json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": {"file_path": str(file_path), "content": content},
        }
    )
    return _run_hook_with_stdin(payload)


def _run_hook_with_stdin(stdin_text: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT_PATH)],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )


def _permission_decision(completed: subprocess.CompletedProcess) -> str | None:
    if not completed.stdout.strip():
        return None
    parsed_decision = json.loads(completed.stdout)
    return parsed_decision["hookSpecificOutput"]["permissionDecision"]


def _deny_reason(completed: subprocess.CompletedProcess) -> str:
    parsed_decision = json.loads(completed.stdout)
    return parsed_decision["hookSpecificOutput"]["permissionDecisionReason"]


@pytest.mark.parametrize("template_filename", ALL_TEMPLATE_FILENAMES)
def test_template_filename_is_allowed(tmp_path: Path, template_filename: str) -> None:
    completed = _run_hook(WRITE_TOOL_NAME, tmp_path / template_filename, PLACEHOLDER_TEMPLATE_BODY)
    assert completed.returncode == 0, completed.stderr
    assert _permission_decision(completed) is None, (
        f"{template_filename} is a committed template and must not be denied by filename; "
        f"got stdout {completed.stdout!r}"
    )


@pytest.mark.parametrize("sensitive_filename", ALL_DENIED_FILENAMES)
def test_sensitive_filename_is_denied(tmp_path: Path, sensitive_filename: str) -> None:
    completed = _run_hook(WRITE_TOOL_NAME, tmp_path / sensitive_filename, PLACEHOLDER_TEMPLATE_BODY)
    assert completed.returncode == 0, completed.stderr
    assert _permission_decision(completed) == DENY_DECISION, (
        f"{sensitive_filename} must stay denied; got stdout {completed.stdout!r}"
    )


@pytest.mark.parametrize("uppercase_filename", ALL_UPPERCASE_DENIED_FILENAMES)
def test_uppercase_sensitive_filename_is_denied(tmp_path: Path, uppercase_filename: str) -> None:
    completed = _run_hook(WRITE_TOOL_NAME, tmp_path / uppercase_filename, PLACEHOLDER_TEMPLATE_BODY)
    assert completed.returncode == 0, completed.stderr
    assert _permission_decision(completed) == DENY_DECISION, (
        f"{uppercase_filename} names a secret in an uppercase spelling and must stay denied like "
        f"its lowercase form; got stdout {completed.stdout!r}"
    )


@pytest.mark.parametrize("ordinary_filename", ALL_ORDINARY_FILENAMES)
def test_ordinary_source_file_is_allowed(tmp_path: Path, ordinary_filename: str) -> None:
    completed = _run_hook(WRITE_TOOL_NAME, tmp_path / ordinary_filename, ORDINARY_SOURCE_BODY)
    assert completed.returncode == 0, completed.stderr
    assert _permission_decision(completed) is None


def test_dot_env_local_deny_reason_names_the_file_and_the_pattern(tmp_path: Path) -> None:
    completed = _run_hook(WRITE_TOOL_NAME, tmp_path / ".env.local", PLACEHOLDER_TEMPLATE_BODY)
    assert _permission_decision(completed) == DENY_DECISION
    deny_reason = _deny_reason(completed)
    assert ".env.local" in deny_reason
    assert ".env.*" in deny_reason


def test_edit_to_a_template_is_allowed(tmp_path: Path) -> None:
    completed = _run_hook(EDIT_TOOL_NAME, tmp_path / ".env.example", PLACEHOLDER_TEMPLATE_BODY)
    assert completed.returncode == 0, completed.stderr
    assert _permission_decision(completed) is None


def test_edit_to_a_secrets_file_is_denied(tmp_path: Path) -> None:
    completed = _run_hook(EDIT_TOOL_NAME, tmp_path / ".env", PLACEHOLDER_TEMPLATE_BODY)
    assert completed.returncode == 0, completed.stderr
    assert _permission_decision(completed) == DENY_DECISION


def test_read_tool_is_not_evaluated(tmp_path: Path) -> None:
    completed = _run_hook(READ_TOOL_NAME, tmp_path / ".env", PLACEHOLDER_TEMPLATE_BODY)
    assert completed.returncode == 0, completed.stderr
    assert _permission_decision(completed) is None


def test_payload_without_a_file_path_is_allowed() -> None:
    completed = _run_hook_with_stdin(json.dumps({"tool_name": WRITE_TOOL_NAME, "tool_input": {}}))
    assert completed.returncode == 0, completed.stderr
    assert _permission_decision(completed) is None


def test_malformed_payload_fails_open() -> None:
    completed = _run_hook_with_stdin("{not valid json")
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == ""


@pytest.mark.parametrize("trailing_suffix_filename", (".env.example.bak", ".env.template.old", ".env.sample.orig"))
def test_template_suffix_must_be_last_to_earn_the_exemption(
    tmp_path: Path, trailing_suffix_filename: str
) -> None:
    completed = _run_hook(
        WRITE_TOOL_NAME, tmp_path / trailing_suffix_filename, PLACEHOLDER_TEMPLATE_BODY
    )
    assert completed.returncode == 0, completed.stderr
    assert _permission_decision(completed) == DENY_DECISION, (
        f"{trailing_suffix_filename} is a copy of a live secrets file, not a template; "
        f"only a trailing template suffix earns the exemption, got {completed.stdout!r}"
    )
