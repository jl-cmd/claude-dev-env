"""Constants for the NAS ssh binary enforcer hook.

Holds the Bash tool name, the ssh-family command basenames, the Windows OpenSSH
binary path suffixes, and the batch-mode pattern. Segment splitting and
leading-program resolution come from ``shell_command_segments``.
"""

import re

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
