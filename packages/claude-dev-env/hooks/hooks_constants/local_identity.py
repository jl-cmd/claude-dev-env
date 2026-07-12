"""Resolve the NAS host, ssh user, and ssh port for the NAS ssh enforcer hook.

The enforcer ships into ``~/.claude/`` and cannot read a repository file, so it
reads the real NAS values from the environment or a git-ignored file in the
Claude home directory, and it composes the two deny messages that quote those
values. The committed defaults are placeholders.

::

    CLAUDE_NAS_HOST set to a host   ->  nas_host() returns that host
    CLAUDE_NAS_SSH_PORT set to 2200 ->  nas_ssh_port() returns 2200
    (env unset, no file)            ->  nas_host() == "nas.example.local"
                                        nas_ssh_port() == 22

Each value comes from its ``CLAUDE_NAS_*`` environment variable, then
``~/.claude/local-identity.json``, then the placeholder default.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

NAS_HOST_ENV_VAR = "CLAUDE_NAS_HOST"
PII_EXEMPT_REPOS_ENV_VAR = "CLAUDE_PII_EXEMPT_REPOS"
PII_EXEMPT_REPOS_JSON_KEY = "pii_exempt_repositories"
PII_EXEMPT_REPOS_SEPARATOR = ","
NAS_SSH_USER_ENV_VAR = "CLAUDE_NAS_SSH_USER"
NAS_SSH_PORT_ENV_VAR = "CLAUDE_NAS_SSH_PORT"
NAS_JSON_KEY = "nas"
NAS_HOST_JSON_KEY = "host"
NAS_SSH_USER_JSON_KEY = "ssh_user"
NAS_SSH_PORT_JSON_KEY = "ssh_port"
CLAUDE_HOME_DIRECTORY_NAME = ".claude"
LOCAL_IDENTITY_FILE_NAME = "local-identity.json"
PLACEHOLDER_NAS_HOST = "nas.example.local"
PLACEHOLDER_NAS_SSH_USER = "operator"
PLACEHOLDER_NAS_SSH_PORT = 22
OPENSSH_INVOCATION_EXAMPLE_BINARY = '"/c/Windows/System32/OpenSSH/ssh.exe"'
NAS_SSH_RULE_REFERENCE = "~/.claude/rules/nas-ssh-invocation.md"


def _local_identity_file_path() -> Path:
    return Path.home() / CLAUDE_HOME_DIRECTORY_NAME / LOCAL_IDENTITY_FILE_NAME


def _identity_dictionary_from_local_file() -> dict[str, object]:
    identity_path = _local_identity_file_path()
    if not identity_path.is_file():
        return {}
    try:
        parsed_identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    return parsed_identity if isinstance(parsed_identity, dict) else {}


def _nas_section_from_local_file() -> dict[str, object]:
    nas_section = _identity_dictionary_from_local_file().get(NAS_JSON_KEY, {})
    return nas_section if isinstance(nas_section, dict) else {}


def _normalized_slug_set(all_raw_slugs: list[object]) -> frozenset[str]:
    return frozenset(
        each_slug.strip().lower()
        for each_slug in all_raw_slugs
        if isinstance(each_slug, str) and each_slug.strip()
    )


def pii_exempt_repository_slugs() -> frozenset[str]:
    """Return owner/repo slugs whose commits skip the staged PII scan.

    ::

        CLAUDE_PII_EXEMPT_REPOS="Owner/repo-a, Other/b"  ->  {"owner/repo-a", "other/b"}
        (env unset, file lists ["Owner/repo-a"])         ->  {"owner/repo-a"}
        (env unset, no file)                             ->  frozenset()

    The environment variable (comma-separated) wins, then the
    ``pii_exempt_repositories`` list in the git-ignored
    ``~/.claude/local-identity.json``. Slugs are lowercased so matching is
    case-insensitive.

    Returns:
        Lowercased ``owner/repo`` slugs exempt from staged-commit PII scanning.
    """
    slugs_from_environment = os.environ.get(PII_EXEMPT_REPOS_ENV_VAR)
    if slugs_from_environment:
        return _normalized_slug_set(
            list(slugs_from_environment.split(PII_EXEMPT_REPOS_SEPARATOR))
        )
    stored_slugs = _identity_dictionary_from_local_file().get(
        PII_EXEMPT_REPOS_JSON_KEY
    )
    if not isinstance(stored_slugs, list):
        return frozenset()
    return _normalized_slug_set(stored_slugs)


def nas_host() -> str:
    """Return the NAS host the ssh enforcer guards.

    ::

        CLAUDE_NAS_HOST set to a host  ->  that host
        (env unset, no file)           ->  "nas.example.local"

    The environment variable wins, then the git-ignored file, then the
    placeholder default.

    Returns:
        The NAS hostname or address.
    """
    host_from_environment = os.environ.get(NAS_HOST_ENV_VAR)
    if host_from_environment:
        return host_from_environment
    stored_host = _nas_section_from_local_file().get(NAS_HOST_JSON_KEY)
    if isinstance(stored_host, str) and stored_host:
        return stored_host
    return PLACEHOLDER_NAS_HOST


def nas_ssh_user() -> str:
    """Return the ssh user the enforcer expects for the NAS.

    ::

        CLAUDE_NAS_SSH_USER set to a user  ->  that user
        (env unset, no file)               ->  "operator"

    The environment variable wins, then the git-ignored file, then the
    placeholder default.

    Returns:
        The ssh login name for the NAS.
    """
    user_from_environment = os.environ.get(NAS_SSH_USER_ENV_VAR)
    if user_from_environment:
        return user_from_environment
    stored_user = _nas_section_from_local_file().get(NAS_SSH_USER_JSON_KEY)
    if isinstance(stored_user, str) and stored_user:
        return stored_user
    return PLACEHOLDER_NAS_SSH_USER


def nas_ssh_port() -> int:
    """Return the ssh port the enforcer expects for the NAS.

    ::

        CLAUDE_NAS_SSH_PORT set to 2200  ->  2200
        (env unset, no file)             ->  22

    The environment variable wins, then the git-ignored file, then the
    placeholder default.

    Returns:
        The ssh port number for the NAS.
    """
    port_from_environment = os.environ.get(NAS_SSH_PORT_ENV_VAR)
    if port_from_environment and port_from_environment.isdigit():
        return int(port_from_environment)
    stored_port = _nas_section_from_local_file().get(NAS_SSH_PORT_JSON_KEY)
    if isinstance(stored_port, int):
        return stored_port
    return PLACEHOLDER_NAS_SSH_PORT


def _openssh_invocation_example() -> str:
    return (
        f"{OPENSSH_INVOCATION_EXAMPLE_BINARY} -o BatchMode=yes -o ConnectTimeout=10 "
        f'-p {nas_ssh_port()} {nas_ssh_user()}@{nas_host()} "<cmd>"'
    )


def bare_ssh_binary_deny_message() -> str:
    """Return the deny message for a bare ssh-family word aimed at the NAS.

    ::

        ssh -p 22 operator@nas.example.local "ls"  ->  this message text
        (the text quotes the resolved host, user, and port)

    Names the Git Bash MSYS-ssh hang and points at the Windows OpenSSH binary
    with batch mode on.

    Returns:
        The full deny-message text for the bare ssh-family case.
    """
    return (
        f"BLOCKED [nas-ssh-binary]: Git Bash's MSYS ssh reads ~/.ssh/id_ed25519 as "
        f"world-readable through its ACL mapping, rejects the key as bad permissions, "
        f"and falls back to an interactive password prompt that hangs unattended "
        f"sessions against the NAS at {nas_host()}.\n\n"
        f"Use the Windows OpenSSH binary, which authenticates the key without prompting:\n"
        f"  {_openssh_invocation_example()}\n\n"
        f"See {NAS_SSH_RULE_REFERENCE} for full guidance."
    )


def missing_batch_mode_deny_message() -> str:
    """Return the deny message for the OpenSSH binary without batch mode.

    ::

        "..ssh.exe" -p 22 operator@nas.example.local "ls"  ->  this message text
        (the text quotes the resolved host, user, and port)

    Names the interactive-prompt hang and asks for ``-o BatchMode=yes`` so a key
    failure exits loudly.

    Returns:
        The full deny-message text for the missing-batch-mode case.
    """
    return (
        f"BLOCKED [nas-ssh-binary]: this NAS ssh command uses the Windows OpenSSH binary "
        f"but omits -o BatchMode=yes, so an authentication regression falls back to an "
        f"interactive password prompt that hangs unattended sessions against the NAS at "
        f"{nas_host()}.\n\n"
        f"Add -o BatchMode=yes so a key failure exits loudly rather than prompting:\n"
        f"  {_openssh_invocation_example()}\n\n"
        f"See {NAS_SSH_RULE_REFERENCE} for full guidance."
    )
