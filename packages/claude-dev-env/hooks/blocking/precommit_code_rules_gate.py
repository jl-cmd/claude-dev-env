"""PreToolUse hook that passes Git commit validation to Git hooks.

Intercepts Bash `git commit` invocations (including `git -C <path> commit`),
emits neutral evidence, and returns control to Git. Configured Git hooks
receive the commit at the commit boundary.
"""

import re
import sys
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from block_main_commit import (  # noqa: E402
    is_commit_command,
    parse_bash_command_from_stdin,
)

from hooks_constants.precommit_code_rules_gate_constants import (  # noqa: E402
    GIT_DASH_C_COMMIT_PATTERN,
)


def is_git_commit_invocation(bash_command: str) -> bool:
    """Report whether *bash_command* runs a git commit.

    Matches both the plain ``git commit`` substring form and the
    ``git -C <path> commit`` form, where the directory flag sits between
    the two words.

    Args:
        bash_command: The Bash tool command string from the hook payload.

    Returns:
        True when the command invokes git commit; False otherwise.
    """
    if is_commit_command(bash_command):
        return True
    return re.search(GIT_DASH_C_COMMIT_PATTERN, bash_command) is not None


def main() -> None:
    """Pass Git commit validation through to configured Git hooks."""
    bash_command = parse_bash_command_from_stdin()
    if not is_git_commit_invocation(bash_command):
        sys.exit(0)
    sys.stderr.write("Git commit proceeds to configured Git hooks.\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
