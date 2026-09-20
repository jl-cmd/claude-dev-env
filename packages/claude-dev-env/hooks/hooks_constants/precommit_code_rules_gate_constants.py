"""Constants for git-repository-root resolution.

The git-repository-root resolution command and its timeout, used by
``resolve_repository_root`` to find the repository a directory belongs to.
"""

GIT_COMMAND_TIMEOUT_SECONDS: int = 5
ALL_GIT_REPOSITORY_ROOT_COMMAND: tuple[str, ...] = (
    "git",
    "rev-parse",
    "--show-toplevel",
)
