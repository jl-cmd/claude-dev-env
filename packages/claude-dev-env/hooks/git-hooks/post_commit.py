#!/usr/bin/env python3
"""
Git post-commit hook: Auto-update parent repos when committing in a submodule.

When you commit in a submodule, this hook:
1. Detects if current repo is a submodule of a parent
2. Stages the submodule update in the parent
3. Creates a commit in the parent pointing to the new submodule commit

This prevents the "lost work" issue where submodule commits aren't tracked by parent.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_git(*args: str, cwd: Path | None = None) -> str:
    """Run a git command and return output."""
    result = subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def find_parent_repo(repo_dir: Path) -> Path | None:
    """Find parent repo that has this as a submodule."""
    repo_name = repo_dir.name
    parent_dir = repo_dir.parent

    while parent_dir != parent_dir.parent:
        git_path = parent_dir / ".git"
        gitmodules_path = parent_dir / ".gitmodules"

        if git_path.exists() and gitmodules_path.exists():
            try:
                content = gitmodules_path.read_text()
                if f"path = {repo_name}" in content:
                    return parent_dir
            except Exception:
                pass

        parent_dir = parent_dir.parent

    return None


def main() -> int:
    """Main hook logic."""
    try:
        repo_dir = Path(run_git("rev-parse", "--show-toplevel"))
    except Exception:
        return 0

    repo_name = repo_dir.name
    parent_repo = find_parent_repo(repo_dir)

    if not parent_repo:
        return 0

    commit_msg = run_git("log", "-1", "--pretty=%s", cwd=repo_dir)
    commit_hash = run_git("rev-parse", "--short", "HEAD", cwd=repo_dir)

    print()
    print("=== Submodule Parent Update ===")
    print(f"Submodule: {repo_name} @ {commit_hash}")
    print(f"Parent:    {parent_repo}")

    run_git("add", repo_name, cwd=parent_repo)

    diff_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=parent_repo,
    )

    if diff_result.returncode == 0:
        print("Parent already up to date.")
        return 0

    full_commit_msg = f"""chore: update {repo_name} submodule to {commit_hash}

Submodule commit: {commit_msg}

Co-Authored-By: Claude <noreply@anthropic.com>"""

    subprocess.run(
        ["git", "commit", "-m", full_commit_msg],
        cwd=parent_repo,
    )

    print("Parent updated successfully.")
    print("================================")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
