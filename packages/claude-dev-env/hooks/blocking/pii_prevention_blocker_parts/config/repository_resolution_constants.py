"""Named constants for the commit repository-resolution deny message.

The template carries an ``{attempted_path}`` slot so the refusal names the exact
directory whose git repository root did not resolve. The cwd label fills that
slot when the command named no path and the gate fell back to the session
working directory.
"""

from __future__ import annotations

REPOSITORY_ROOT_UNRESOLVED_REASON_TEMPLATE: str = (
    "BLOCKED [pii_prevention_blocker]: could not resolve the git repository root "
    "for a commit command targeting {attempted_path} (not a git work tree, git "
    "missing, or bad -C or cd path). Refuse commit until the repository root is "
    "resolvable."
)

REPOSITORY_ROOT_UNRESOLVED_CWD_LABEL: str = "the session working directory"

ALL_DIRECTORY_CHANGE_COMMAND_NAMES: frozenset[str] = frozenset(
    {"cd", "pushd", "set-location", "sl"}
)

ALL_DIRECTORY_CHANGE_PATH_OPTION_NAMES: frozenset[str] = frozenset(
    {"-path", "-literalpath"}
)

DIRECTORY_CHANGE_OPTION_TERMINATOR: str = "--"
