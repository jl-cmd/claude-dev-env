"""Git and GitHub validation checks for pre-push review."""

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import List


SUBPROCESS_TIMEOUT_SECONDS = 30


@dataclass
class Violation:
    """Represents a validation violation."""
    file: str
    line: int
    message: str


def get_current_branch() -> str:
    """Get the current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def check_draft_pr_state() -> List[Violation]:
    """
    Check that PR is in draft state.

    Returns empty list if:
    - No PR exists for current branch
    - gh CLI not available
    - PR is in draft state

    Returns violation if:
    - PR is not in draft state
    """
    branch = get_current_branch()
    if not branch:
        return []

    try:
        pr_info = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--json", "number,isDraft"],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return []
    except subprocess.CalledProcessError:
        return []
    except subprocess.TimeoutExpired:
        return []

    if not pr_info.stdout.strip():
        return []

    try:
        pr_data = json.loads(pr_info.stdout)
    except json.JSONDecodeError:
        return []

    if not pr_data:
        return []

    is_draft = pr_data[0].get("isDraft", False)

    if is_draft:
        return []

    return [
        Violation(
            file="",
            line=0,
            message="PR must be in draft state before pushing. Run: gh pr ready --undo",
        )
    ]


def main() -> None:
    """Run all git checks and exit with appropriate code."""
    violations: List[Violation] = []

    violations.extend(check_draft_pr_state())

    if violations:
        for violation in violations:
            print(violation.message)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
