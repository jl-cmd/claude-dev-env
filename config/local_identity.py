"""Resolve the fan-out owner scopes and their token environment-variable names.

The fan-out dispatcher runs against a set of GitHub owner accounts whose real
names are private, so the committed tree carries a placeholder and the real
scopes arrive at run time from the environment or a git-ignored local file.

::

    FANOUT_OWNER_SCOPES="acme,acme-labs"   ->  ["acme", "acme-labs"]
    (env unset, no local file)             ->  ["example-owner"]

The scopes come from the ``FANOUT_OWNER_SCOPES`` environment variable
(comma-separated), then ``config/local-identity.json`` at the repository root,
then the placeholder default.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

FANOUT_OWNER_SCOPES_ENV_VAR = "FANOUT_OWNER_SCOPES"
OWNER_SCOPES_JSON_KEY = "github_owner_scopes"
LOCAL_IDENTITY_FILE_RELATIVE_PATH = "config/local-identity.json"
OWNER_SCOPE_SEPARATOR = ","
TOKEN_ENV_VAR_SUFFIX = "_TOKEN"
OWNER_SCOPE_HYPHEN = "-"
ALL_PLACEHOLDER_OWNER_SCOPES: tuple[str, ...] = ("example-owner",)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _owner_scopes_from_environment() -> list[str]:
    raw_scopes = os.environ.get(FANOUT_OWNER_SCOPES_ENV_VAR, "")
    all_split_scopes = raw_scopes.split(OWNER_SCOPE_SEPARATOR)
    return [each_scope.strip() for each_scope in all_split_scopes if each_scope.strip()]


def _owner_scopes_from_local_file() -> list[str]:
    local_identity_path = _repository_root() / LOCAL_IDENTITY_FILE_RELATIVE_PATH
    if not local_identity_path.is_file():
        return []
    try:
        parsed_identity = json.loads(local_identity_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    if not isinstance(parsed_identity, dict):
        return []
    stored_scopes = parsed_identity.get(OWNER_SCOPES_JSON_KEY, [])
    if not isinstance(stored_scopes, list):
        return []
    return [str(each_scope) for each_scope in stored_scopes if str(each_scope).strip()]


def fanout_owner_scopes() -> list[str]:
    """Return the GitHub owner scopes the fan-out dispatcher targets.

    ::

        FANOUT_OWNER_SCOPES="acme,acme-labs"  ->  ["acme", "acme-labs"]
        (env unset, local file present)       ->  the file's scopes
        (env unset, no local file)            ->  ["example-owner"]

    The environment variable wins, then the git-ignored local file, then the
    placeholder default the committed tree ships.

    Returns:
        The owner-scope names, in resolution-priority order.
    """
    scopes_from_environment = _owner_scopes_from_environment()
    if scopes_from_environment:
        return scopes_from_environment
    scopes_from_local_file = _owner_scopes_from_local_file()
    if scopes_from_local_file:
        return scopes_from_local_file
    return list(ALL_PLACEHOLDER_OWNER_SCOPES)


def token_env_var_name(owner_scope: str) -> str:
    """Return the token environment-variable name for one owner scope.

    ::

        token_env_var_name("acme")       ->  the acme installation-token variable
        token_env_var_name("acme-labs")  ->  the acme-labs variable, hyphen dropped

    The name upper-cases the scope, drops hyphens, and appends the token
    suffix, so each owner reads its own installation token from the matching
    variable.

    Args:
        owner_scope: The GitHub owner login the fan-out targets.

    Returns:
        The environment-variable name that carries that owner's token.
    """
    return owner_scope.upper().replace(OWNER_SCOPE_HYPHEN, "") + TOKEN_ENV_VAR_SUFFIX
