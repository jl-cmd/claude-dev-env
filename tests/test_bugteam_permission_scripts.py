"""Behavior checks for bugteam grant/revoke permission scripts."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_SHARED_PR_LOOP_SCRIPTS = (
    REPOSITORY_ROOT
    / "packages"
    / "claude-dev-env"
    / "_shared"
    / "pr-loop"
    / "scripts"
)
GRANT_SCRIPT = _SHARED_PR_LOOP_SCRIPTS / "grant_project_claude_permissions.py"
REVOKE_SCRIPT = _SHARED_PR_LOOP_SCRIPTS / "revoke_project_claude_permissions.py"


def run_script(
    script_path: Path,
    *,
    working_directory: Path,
    home_directory: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home_directory)
    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(working_directory),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


class TestBugteamPermissionScripts(unittest.TestCase):
    def test_grant_exits_when_not_project_root(self) -> None:
        temporary_root = Path(__file__).resolve().parent / "_bugteam_perm_tmp"
        temporary_root.mkdir(exist_ok=True)
        fake_home = temporary_root / "home"
        fake_home.mkdir(exist_ok=True)
        (fake_home / ".claude").mkdir(parents=True)
        (fake_home / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
        not_a_repo = temporary_root / "not_a_project"
        not_a_repo.mkdir(exist_ok=True)
        try:
            completed = run_script(
                GRANT_SCRIPT,
                working_directory=not_a_repo,
                home_directory=fake_home,
            )
        finally:
            import shutil

            shutil.rmtree(temporary_root, ignore_errors=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("not a project root", completed.stderr)

    def test_grant_then_revoke_round_trip(self) -> None:
        temporary_root = Path(__file__).resolve().parent / "_bugteam_perm_tmp2"
        temporary_root.mkdir(exist_ok=True)
        fake_home = temporary_root / "home"
        fake_home.mkdir(exist_ok=True)
        (fake_home / ".claude").mkdir(parents=True)
        settings_path = fake_home / ".claude" / "settings.json"
        settings_path.write_text("{}", encoding="utf-8")
        project = temporary_root / "myrepo"
        project.mkdir()
        (project / ".git").mkdir()
        try:
            first_grant = run_script(
                GRANT_SCRIPT,
                working_directory=project,
                home_directory=fake_home,
            )
            self.assertEqual(first_grant.returncode, 0, first_grant.stderr)
            second_grant = run_script(
                GRANT_SCRIPT,
                working_directory=project,
                home_directory=fake_home,
            )
            self.assertEqual(second_grant.returncode, 0, second_grant.stderr)
            self.assertIn("No changes needed", second_grant.stdout)
            revoke = run_script(
                REVOKE_SCRIPT,
                working_directory=project,
                home_directory=fake_home,
            )
            self.assertEqual(revoke.returncode, 0, revoke.stderr)
            second_revoke = run_script(
                REVOKE_SCRIPT,
                working_directory=project,
                home_directory=fake_home,
            )
            self.assertEqual(second_revoke.returncode, 0, second_revoke.stderr)
            self.assertIn("No changes to revoke", second_revoke.stdout)
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertNotIn("permissions", payload)
            self.assertNotIn("autoMode", payload)
        finally:
            import shutil

            shutil.rmtree(temporary_root, ignore_errors=True)
