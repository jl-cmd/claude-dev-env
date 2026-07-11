"""Constants for the NAS ssh binary enforcer hook.

Holds the Bash tool name, the ssh-family command basenames, the Windows OpenSSH
binary path suffixes, the launcher-wrapper set, the shell control-operator tokens
and their split pattern, the leading-assignment and launcher-duration patterns,
and the batch-mode pattern.
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
ALL_LAUNCHER_WRAPPER_COMMANDS = frozenset({"timeout", "nohup", "nice", "stdbuf", "setsid", "env"})
ALL_SHELL_CONTROL_OPERATOR_TOKENS = frozenset({"&&", "||", ";", "|", "&", "|&"})
CONTROL_OPERATOR_SPLIT_PATTERN = re.compile(r"(&&|\|\||;|\|&|\||(?<!>)&(?!>))")
LEADING_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LAUNCHER_DURATION_PATTERN = re.compile(r"^\d+[a-z]*$", re.IGNORECASE)
BATCH_MODE_PATTERN = re.compile(r"batchmode\s*=\s*yes", re.IGNORECASE)
