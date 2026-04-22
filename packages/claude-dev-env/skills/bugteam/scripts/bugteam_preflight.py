from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def verify_git_hooks_path(repository_root: Path | None = None) -> int:
    """Check that core.hooksPath resolves to the claude-dev-env git-hooks directory.

    When *repository_root* is provided, queries the effective config for that
    repository (``git -C <root> config --get``), which detects repo-level
    overrides such as Husky or lefthook. Falls back to the current working
    directory's effective config when *repository_root* is None.

    Returns zero when the configured path ends with the expected hooks suffix.
    Returns non-zero and prints a correction message when unset or pointing elsewhere.
    """
    expected_hooks_path_suffix = "hooks/git-hooks"
    enforcement_absent_message = (
        "Git-side CODE_RULES enforcement is not active on this host.\n"
        "Run: npx claude-dev-env .\n"
        "Or set core.hooksPath at any scope, e.g.:\n"
        "  git config --global core.hooksPath ~/.claude/hooks/git-hooks"
    )
    git_command: list[str] = ["git"]
    if repository_root is not None:
        git_command.extend(["-C", str(repository_root)])
    git_command.extend(["config", "--get", "core.hooksPath"])
    try:
        query_result = subprocess.run(
            git_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        print(
            "bugteam_preflight: git is not installed or not available on PATH.\n"
            f"{enforcement_absent_message}",
            file=sys.stderr,
        )
        return 1
    except OSError as os_error:
        print(
            f"bugteam_preflight: failed to run git: {os_error}\n"
            f"{enforcement_absent_message}",
            file=sys.stderr,
        )
        return 1
    if query_result.returncode != 0:
        print(
            f"bugteam_preflight: {enforcement_absent_message}",
            file=sys.stderr,
        )
        return 1
    configured_path = query_result.stdout.strip().replace("\\", "/").rstrip("/")
    if not configured_path.endswith(expected_hooks_path_suffix):
        print(
            f"bugteam_preflight: core.hooksPath is '{configured_path}' — "
            f"expected path ending in '{expected_hooks_path_suffix}'.\n"
            f"{enforcement_absent_message}",
            file=sys.stderr,
        )
        return 1
    return 0


def find_repository_root(start: Path) -> Path:
    resolved = start.resolve()
    candidates = [resolved, *resolved.parents]
    for candidate in candidates:
        if (candidate / ".git").is_dir() or (candidate / ".git").is_file():
            return candidate
    for candidate in candidates:
        if (candidate / "pytest.ini").is_file():
            return candidate
    return resolved


def has_pytest_configuration(root: Path) -> bool:
    if (root / "pytest.ini").is_file():
        return True
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    text = pyproject.read_text(encoding="utf-8", errors="replace")
    return "[tool.pytest" in text


def has_discoverable_tests(root: Path) -> bool:
    ignore = {"site-packages", ".venv", "venv", "node_modules"}
    for path in root.rglob("test_*.py"):
        if any(part in ignore for part in path.parts):
            continue
        return True
    for path in root.rglob("*_test.py"):
        if any(part in ignore for part in path.parts):
            continue
        return True
    return False


def _pytest_exit_code_no_tests_collected() -> int:
    return 5


def run_pytest(repository_root: Path, verbose: bool) -> int:
    command = [sys.executable, "-m", "pytest"]
    if not verbose:
        command.append("-q")
    completed = subprocess.run(
        command,
        cwd=str(repository_root),
        check=False,
    )
    if completed.returncode == _pytest_exit_code_no_tests_collected():
        return 0
    return completed.returncode


def run_pre_commit(repository_root: Path) -> int:
    completed = subprocess.run(
        ["pre-commit", "run", "--all-files"],
        cwd=str(repository_root),
        check=False,
    )
    return completed.returncode


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local checks before /bugteam (pytest, optional pre-commit).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: discover from cwd).",
    )
    parser.add_argument(
        "--no-pytest",
        action="store_true",
        help="Skip pytest.",
    )
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        help="Run pre-commit when .pre-commit-config.yaml exists.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose pytest output.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    if os.environ.get("BUGTEAM_PREFLIGHT_SKIP", "").strip() == "1":
        print("bugteam_preflight: skipped (BUGTEAM_PREFLIGHT_SKIP=1).", file=sys.stderr)
        return 0
    start = Path.cwd()
    repository_root = (
        arguments.repo_root.resolve()
        if arguments.repo_root is not None
        else find_repository_root(start)
    )
    hooks_path_exit_code = verify_git_hooks_path(repository_root)
    if hooks_path_exit_code != 0:
        return hooks_path_exit_code
    if not arguments.no_pytest and has_pytest_configuration(repository_root):
        if not has_discoverable_tests(repository_root):
            print(
                "bugteam_preflight: pytest configured but no tests found; skipping pytest.",
                file=sys.stderr,
            )
        else:
            exit_code = run_pytest(repository_root, arguments.verbose)
            if exit_code != 0:
                return exit_code
    elif not arguments.no_pytest:
        print(
            "bugteam_preflight: no pytest configuration found; skipping pytest.",
            file=sys.stderr,
        )
    if arguments.pre_commit and (repository_root / ".pre-commit-config.yaml").is_file():
        exit_code = run_pre_commit(repository_root)
        if exit_code != 0:
            return exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
