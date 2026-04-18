from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


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
