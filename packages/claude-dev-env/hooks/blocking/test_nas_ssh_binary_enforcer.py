"""Unit tests for nas-ssh-binary-enforcer PreToolUse hook."""

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "nas_ssh_binary_enforcer",
    _HOOK_DIR / "nas_ssh_binary_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
_find_nas_ssh_violation = hook_module._find_nas_ssh_violation

from hooks_constants.nas_ssh_binary_enforcer_constants import (
    BARE_SSH_BINARY_MESSAGE as _BARE_SSH_BINARY_MESSAGE,
    MISSING_BATCH_MODE_MESSAGE as _MISSING_BATCH_MODE_MESSAGE,
)


def test_bare_ssh_to_nas_is_denied_with_binary_message() -> None:
    assert (
        _find_nas_ssh_violation('ssh -p 9222 jon@192.168.1.100 "ls /volume1"')
        == _BARE_SSH_BINARY_MESSAGE
    )


def test_bare_scp_to_nas_is_denied() -> None:
    assert (
        _find_nas_ssh_violation("scp -P 9222 file.txt jon@192.168.1.100:/volume1/")
        == _BARE_SSH_BINARY_MESSAGE
    )


def test_bare_sftp_to_nas_is_denied() -> None:
    assert _find_nas_ssh_violation("sftp -P 9222 jon@192.168.1.100") == _BARE_SSH_BINARY_MESSAGE


def test_bare_ssh_to_nas_behind_launcher_wrapper_is_denied() -> None:
    assert (
        _find_nas_ssh_violation('timeout 10 ssh -p 9222 jon@192.168.1.100 "uptime"')
        == _BARE_SSH_BINARY_MESSAGE
    )


def test_bare_ssh_to_nas_after_shell_operator_is_denied() -> None:
    assert (
        _find_nas_ssh_violation('cd /tmp && ssh -p 9222 jon@192.168.1.100 "uptime"')
        == _BARE_SSH_BINARY_MESSAGE
    )


def test_bare_ssh_to_nas_after_glued_operator_is_denied() -> None:
    assert (
        _find_nas_ssh_violation('true;ssh -p 9222 jon@192.168.1.100 "uptime"')
        == _BARE_SSH_BINARY_MESSAGE
    )


def test_bare_ssh_to_nas_after_pipe_ampersand_operator_is_denied() -> None:
    assert (
        _find_nas_ssh_violation('echo start |& ssh -p 9222 jon@192.168.1.100 "echo hi"')
        == _BARE_SSH_BINARY_MESSAGE
    )


def test_full_openssh_binary_to_nas_without_batchmode_is_denied() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/ssh.exe" -o ConnectTimeout=10 '
            '-p 9222 jon@192.168.1.100 "uptime"'
        )
        == _MISSING_BATCH_MODE_MESSAGE
    )


def test_full_openssh_scp_to_nas_without_batchmode_is_denied() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/scp.exe" -P 9222 file.txt jon@192.168.1.100:/volume1/'
        )
        == _MISSING_BATCH_MODE_MESSAGE
    )


def test_full_openssh_binary_to_nas_with_batchmode_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/ssh.exe" -o BatchMode=yes '
            '-o ConnectTimeout=10 -p 9222 jon@192.168.1.100 "uptime"'
        )
        is None
    )


def test_full_openssh_binary_glued_batchmode_flag_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/ssh.exe" -oBatchMode=yes '
            '-p 9222 jon@192.168.1.100 "uptime"'
        )
        is None
    )


def test_bare_ssh_to_other_host_is_allowed() -> None:
    assert _find_nas_ssh_violation('ssh -p 22 jon@example.com "uptime"') is None


def test_full_openssh_binary_to_other_host_without_batchmode_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/ssh.exe" -p 22 jon@example.com "uptime"'
        )
        is None
    )


def test_nas_ip_as_echoed_data_is_allowed() -> None:
    assert _find_nas_ssh_violation('echo "connect via ssh to 192.168.1.100"') is None


def test_nas_ip_mentioned_without_ssh_command_word_is_allowed() -> None:
    assert _find_nas_ssh_violation("ping -c 1 192.168.1.100") is None


def test_ssh_family_word_only_in_remote_command_argument_is_allowed() -> None:
    assert (
        _find_nas_ssh_violation(
            '"/c/Windows/System32/OpenSSH/ssh.exe" -o BatchMode=yes '
            '-p 9222 jon@192.168.1.100 "grep ssh /etc/config"'
        )
        is None
    )


def test_nas_ip_in_different_segment_than_ssh_is_allowed() -> None:
    assert _find_nas_ssh_violation('echo 192.168.1.100 && ssh -p 22 jon@example.com "id"') is None


def test_similar_ip_prefix_is_not_matched() -> None:
    assert _find_nas_ssh_violation('ssh -p 22 jon@192.168.1.1000 "id"') is None


def test_empty_command_is_allowed() -> None:
    assert _find_nas_ssh_violation("") is None


def test_unbalanced_quotes_command_is_allowed() -> None:
    assert _find_nas_ssh_violation("ssh 'unterminated 192.168.1.100") is None
