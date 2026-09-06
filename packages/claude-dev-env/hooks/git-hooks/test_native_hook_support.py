from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_git(
    repository_path: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def run_native_git_action(
    repository_path: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository_path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def run_native_hook(
    repository_path: Path,
    hook_script_name: str,
) -> subprocess.CompletedProcess[str]:
    hook_script_path = Path(__file__).resolve().parent / hook_script_name
    return subprocess.run(
        [sys.executable, str(hook_script_path)],
        cwd=repository_path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def read_git_head(repository_path: Path, reference_name: str) -> str:
    return run_git(repository_path, "rev-parse", reference_name).stdout.strip()


def create_bare_repository(temporary_directory: Path) -> Path:
    bare_repository_path = temporary_directory / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "--quiet", str(bare_repository_path)],
        cwd=temporary_directory,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return bare_repository_path


def configure_remote_url_rewrite(
    repository_path: Path,
    bare_repository_path: Path,
    remote_url: str,
) -> None:
    run_git(
        repository_path,
        "config",
        f"url.{bare_repository_path.as_uri()}.insteadOf",
        remote_url,
    )


def configure_native_repository(repository_path: Path, remote_url: str) -> None:
    run_git(repository_path, "init", "--quiet")
    run_git(repository_path, "config", "user.email", "test@example.invalid")
    run_git(repository_path, "config", "user.name", "Verification Test")
    run_git(repository_path, "remote", "add", "origin", remote_url)
    (repository_path / "README.md").write_text("check\n", encoding="utf-8")


def create_native_repository(
    temporary_directory: Path,
    repository_name: str,
    remote_url: str,
    initial_branch: str | None = None,
) -> Path:
    repository_path = temporary_directory / repository_name
    repository_path.mkdir()
    all_init_arguments = ["init", "--quiet"]
    if initial_branch:
        all_init_arguments.insert(1, f"--initial-branch={initial_branch}")
    run_git(repository_path, *all_init_arguments)
    run_git(repository_path, "config", "user.email", "test@example.invalid")
    run_git(repository_path, "config", "user.name", "Verification Test")
    run_git(repository_path, "remote", "add", "origin", remote_url)
    (repository_path / "README.md").write_text("check\n", encoding="utf-8")
    return repository_path


def install_native_hook(
    repository_path: Path,
    hook_directory: Path,
    hook_name: str,
    module_name: str,
) -> None:
    source_directory = Path(__file__).resolve().parent
    hook_directory.mkdir()
    shim_text = (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"hook_source_directory = Path({str(source_directory)!r})\n"
        "if str(hook_source_directory) not in sys.path:\n"
        "    sys.path.insert(0, str(hook_source_directory))\n"
        f"import {module_name}\n"
        f"sys.exit({module_name}.main())\n"
    )
    hook_path = hook_directory / hook_name
    hook_path.write_text(shim_text, encoding="utf-8")
    hook_path.chmod(0o755)
    run_git(repository_path, "config", "core.hooksPath", str(hook_directory))
