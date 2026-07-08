"""Constants for the NAS ssh binary enforcer hook.

Holds the Bash tool name, the NAS host-token pattern, the ssh-family command
basenames, the Windows OpenSSH binary path suffixes, the launcher-wrapper set, the
shell control-operator tokens and their split pattern, the leading-assignment and
launcher-duration patterns, the batch-mode pattern, and the two deny messages.
"""

import re

BASH_TOOL_NAME = "Bash"

NAS_HOST_TOKEN_PATTERN = re.compile(r"(?:^|@)192\.168\.1\.100(?::|$)")
"""Match the NAS address only as a connection host.

Anchored to token start or an ``@`` and followed by ``:`` or token end, so the
address is matched as a bare host (``192.168.1.100``), a ``user@host``
(``jon@192.168.1.100``), or a ``host:path`` target (``192.168.1.100:/vol1/``,
``jon@192.168.1.100:/vol1/``). The address inside a remote-command argument
(``"ping 192.168.1.100"``) or a remote path component on another host
(``jon@other:/backup/192.168.1.100/``) does not count as a NAS connection.
"""

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

BARE_SSH_BINARY_MESSAGE = (
    "BLOCKED [nas-ssh-binary]: Git Bash's MSYS ssh reads ~/.ssh/id_ed25519 as "
    "world-readable through its ACL mapping, rejects the key as bad permissions, "
    "and falls back to an interactive password prompt that hangs unattended "
    "sessions against the NAS at 192.168.1.100.\n\n"
    "Use the Windows OpenSSH binary, which authenticates the key without prompting:\n"
    '  "/c/Windows/System32/OpenSSH/ssh.exe" -o BatchMode=yes -o ConnectTimeout=10 '
    '-p 9222 jon@192.168.1.100 "<cmd>"\n\n'
    "See ~/.claude/rules/nas-ssh-invocation.md for full guidance."
)

MISSING_BATCH_MODE_MESSAGE = (
    "BLOCKED [nas-ssh-binary]: this NAS ssh command uses the Windows OpenSSH binary "
    "but omits -o BatchMode=yes, so an authentication regression falls back to an "
    "interactive password prompt that hangs unattended sessions against the NAS at "
    "192.168.1.100.\n\n"
    "Add -o BatchMode=yes so a key failure exits loudly rather than prompting:\n"
    '  "/c/Windows/System32/OpenSSH/ssh.exe" -o BatchMode=yes -o ConnectTimeout=10 '
    '-p 9222 jon@192.168.1.100 "<cmd>"\n\n'
    "See ~/.claude/rules/nas-ssh-invocation.md for full guidance."
)
