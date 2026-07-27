"""Constants for the NAS ssh binary enforcer hook.

Holds the Bash tool name, the ssh-family command basenames, the Windows OpenSSH
binary path suffixes, and the batch-mode pattern. Shared shell-segment helpers
live in ``shell_command_segments`` and are re-exported here for existing imports.
"""

from __future__ import annotations

import re

from hooks_constants.shell_command_segments import (  # noqa: F401
    ALL_LAUNCHER_WRAPPER_COMMANDS,
    ALL_SHELL_CONTROL_OPERATOR_TOKENS,
    CONTROL_OPERATOR_SPLIT_PATTERN,
    LAUNCHER_DURATION_PATTERN,
    LEADING_ASSIGNMENT_PATTERN,
)

BASH_TOOL_NAME = "Bash"

ALL_SSH_FAMILY_COMMAND_BASENAMES = frozenset(
    {"ssh", "scp", "sftp", "ssh.exe", "scp.exe", "sftp.exe"}
)
ALL_OPENSSH_BINARY_PATH_SUFFIXES = (
    "/openssh/ssh.exe",
    "/openssh/scp.exe",
    "/openssh/sftp.exe",
)
BATCH_MODE_PATTERN = re.compile(r"batchmode\s*=\s*yes", re.IGNORECASE)
