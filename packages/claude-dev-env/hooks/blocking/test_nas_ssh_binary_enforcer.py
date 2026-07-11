"""Unit tests for nas-ssh-binary-enforcer PreToolUse hook.

The real NAS host, ssh user, and port are private, so these tests set them via
the ``CLAUDE_NAS_*`` environment variables and drive the real hook, asserting
the runtime-built host pattern and deny messages.
"""

import importlib.util
import os
import pathlib
import sys
from collections.abc import Iterator
from unittest.mock import patch

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))
if str(_HOOK_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR.parent))

hook_spec = importlib.util.spec_from_file_location(
    "nas_ssh_binary_enforcer",
    _HOOK_DIR / "nas_ssh_binary_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
_find_nas_ssh_violation = hook_module._find_nas_ssh_violation

from hooks_constants.local_identity import (  # noqa: E402
    bare_ssh_binary_deny_message,
    missing_batch_mode_deny_message,
)

NAS_HOST = "test-nas.example.net"
NAS_SSH_USER = "tester"
NAS_SSH_PORT = "2222"


@pytest.fixture(autouse=True)
def _set_nas_identity_env() -> Iterator[None]:
    with patch.dict(
        os.environ,
        {
            "CLAUDE_NAS_HOST": NAS_HOST,
            "CLAUDE_NAS_SSH_USER": NAS_SSH_USER,
            "CLAUDE_NAS_SSH_PORT": NAS_SSH_PORT,
        },
        clear=False,
    ):
        yield


def test_bare_ssh_to_nas_is_denied_with_binary_message() -> None:
    assert (
        _find_nas_ssh_violation(
            f'ssh -p {NAS_SSH_PORT} {NAS_SSH_USER}@{NAS_HOST} "ls /volume1"'
        )
        == bare_ssh_binary_deny_message()
    )


def test_bare_scp_to_nas_is_denied() -> None:
    assert (
        _find_nas_ssh_violation(
            f"scp -P {NAS_SSH_PORT} file.txt {NAS_SSH_USER}@{NAS_HOST}:/volume1/"
        )
        == bare_ssh_binary_deny_message()
    )


def test_bare_sftp_to_nas_is_denied() -> None:
    assert (
        _find_nas_ssh_violation(f"sftp -P {NAS_SSH_PORT} {NAS_SSH_USER}@{NAS_HOST}")
        == bare_ssh_binary_deny_message()
    )


def test_bare_ssh_to_nas_behind_launcher_wrapper_is_denied() -> None:
    assert (
        _find_nas_ssh_violation(
            f'timeout 10 ssh -p {NAS_SSH_PORT} {NAS_SSH_USER}@{NAS_HOST} "uptime"'
        )
        == bare_ssh_binary_deny_message()
    )


def test_bare_ssh_to_nas_after_shell_operator_is_denied() -> None:
    assert (
        _find_nas_ssh_violation(
            f'cd /tmp && ssh -p {NAS_SSH_PORT} {NAS_SSH_USER}@{NAS_HOST} "uptime"'
        )
        == bare_ssh_binary_deny_message()
    )


def test_bare_ssh_to_nas_after_glued_operator_is_denied() -> None:
    assert (
        _find_nas_ssh_violation(
            f'true;ssh -p {NAS_SSH_PORT} {NAS_SSH_USER}@{NAS_HOST} "uptime"'
        )
        == bare_ssh_binary_deny_message()
    )


def test_bare_ssh_to_nas_after_pipe_ampersand_operator_is_denied() -> None:
    assert (
        _find_nas_ssh_violation(
            f'echo start |& ssh -p {NAS_SSH_PORT} {NAS_SSH_USER}@{NAS_HOST} "echo hi"'
        )
        == bare_ssh_binary_deny_message()
    )


def test_full_openssh_binary_to_nas_without_batchmode_is_denied() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/ssh.exe" -o ConnectTimeout=10 '
            f'-p {NAS_SSH_PORT} {NAS_SSH_USER}@{NAS_HOST} "uptime"'
        )
        == missing_batch_mode_deny_message()
    )


def test_full_openssh_scp_to_nas_without_batchmode_is_denied() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/scp.exe" '
            f"-P {NAS_SSH_PORT} file.txt {NAS_SSH_USER}@{NAS_HOST}:/volume1/"
        )
        == missing_batch_mode_deny_message()
    )


def test_full_openssh_binary_to_nas_with_batchmode_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/ssh.exe" -o BatchMode=yes '
            f'-o ConnectTimeout=10 -p {NAS_SSH_PORT} {NAS_SSH_USER}@{NAS_HOST} "uptime"'
        )
        is None
    )


def test_full_openssh_binary_glued_batchmode_flag_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/ssh.exe" -oBatchMode=yes '
            f'-p {NAS_SSH_PORT} {NAS_SSH_USER}@{NAS_HOST} "uptime"'
        )
        is None
    )


def test_bare_ssh_to_other_host_is_allowed() -> None:
    assert _find_nas_ssh_violation(f'ssh -p 22 {NAS_SSH_USER}@example.com "uptime"') is None


def test_full_openssh_binary_to_other_host_without_batchmode_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            f'"/c/Windows/System32/OpenSSH/ssh.exe" -p 22 {NAS_SSH_USER}@example.com "uptime"'
        )
        is None
    )


def test_nas_host_as_echoed_data_is_allowed() -> None:
    assert _find_nas_ssh_violation(f'echo "connect via ssh to {NAS_HOST}"') is None


def test_nas_host_mentioned_without_ssh_command_word_is_allowed() -> None:
    assert _find_nas_ssh_violation(f"ping -c 1 {NAS_HOST}") is None


def test_ssh_family_word_only_in_remote_command_argument_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/ssh.exe" -o BatchMode=yes '
            f'-p {NAS_SSH_PORT} {NAS_SSH_USER}@{NAS_HOST} "grep ssh /etc/config"'
        )
        is None
    )


def test_nas_host_in_different_segment_than_ssh_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            f'echo {NAS_HOST} && ssh -p 22 {NAS_SSH_USER}@example.com "id"'
        )
        is None
    )


def test_ssh_to_other_host_with_nas_host_in_remote_command_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            f'ssh -p 22 {NAS_SSH_USER}@example.com "ping -c1 {NAS_HOST}"'
        )
        is None
    )


def test_scp_to_other_host_with_nas_host_in_remote_path_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            f"scp -P 22 f.txt {NAS_SSH_USER}@example.com:/backup/{NAS_HOST}/"
        )
        is None
    )


def test_similar_host_suffix_is_not_matched() -> None:
    assert _find_nas_ssh_violation(f'ssh -p 22 {NAS_SSH_USER}@{NAS_HOST}x "id"') is None


def test_empty_command_is_allowed() -> None:
    assert _find_nas_ssh_violation("") is None


def test_unbalanced_quotes_command_is_allowed() -> None:
    assert _find_nas_ssh_violation(f"ssh 'unterminated {NAS_HOST}") is None
