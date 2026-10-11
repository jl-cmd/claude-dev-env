"""Tests for the second-account profile sync and its launcher."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

import claude_account_profile as profile
from dev_env_scripts_constants.claude_account_constants import (
    CLAUDE_LAUNCHER_PROGRAM,
    LauncherProgram,
)
from dev_env_scripts_constants.codex_account_constants import CODEX_LAUNCHER_PROGRAM

NOW = datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc)


def build_main_home(tmp_path: Path) -> Path:
    main_home = tmp_path / "main"
    (main_home / "skills" / "tdd").mkdir(parents=True)
    (main_home / "rules").mkdir()
    (main_home / "projects").mkdir()
    (main_home / "CLAUDE.md").write_text("main instructions", encoding="utf-8")
    (main_home / "settings.json").write_text("{}", encoding="utf-8")
    (main_home / ".credentials.json").write_text("main sign-in", encoding="utf-8")
    (main_home / ".claude.json").write_text("main state", encoding="utf-8")
    (main_home / ".claude.json.backup").write_text("main backup", encoding="utf-8")
    return main_home


def sync(main_home: Path, profile_home: Path) -> profile.ProfileSyncReport:
    return profile.sync_profile(main_home=main_home, profile_home=profile_home, now=NOW)


class TestDefaultProfileHome:
    def test_should_use_the_profiles_root_the_environment_names(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_SETTINGS_PROFILES_ROOT", str(tmp_path))
        assert profile.default_profile_home() == tmp_path / "ev"

    def test_should_fall_back_to_the_profiles_root_in_the_user_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LLM_SETTINGS_PROFILES_ROOT", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert profile.default_profile_home() == tmp_path / ".claude-profiles" / "ev"


class TestValidateProfileName:
    def test_should_accept_letters_digits_hyphens_and_underscores(self) -> None:
        assert profile.validate_profile_name("alpha_2-b") == "alpha_2-b"

    @pytest.mark.parametrize("profile_name", ["bad name", "-alpha", "CON", "main", "wait"])
    def test_should_refuse_an_unsafe_or_reserved_name(self, profile_name: str) -> None:
        with pytest.raises(ValueError):
            profile.validate_profile_name(profile_name)


class TestIsAccountLocal:
    def test_should_keep_sign_in_state_and_history_local(self) -> None:
        for each_name in (
            ".credentials.json",
            ".credentials.json.bak-session-dashboard",
            ".claude.json",
            ".claude.json.backup",
            "extra-profiles.json",
            "projects",
        ):
            assert profile.is_account_local(each_name)

    def test_should_share_skills_rules_and_settings(self) -> None:
        for each_name in ("skills", "rules", "CLAUDE.md", "settings.json", "plugins"):
            assert not profile.is_account_local(each_name)


class TestSyncProfile:
    def test_should_link_every_shared_entry_to_the_main_home(self, tmp_path: Path) -> None:
        main_home = build_main_home(tmp_path)
        profile_home = tmp_path / "ev"
        sync(main_home, profile_home)
        assert (profile_home / "skills" / "tdd").is_dir()
        assert (profile_home / "CLAUDE.md").read_text(
            encoding="utf-8"
        ) == "main instructions"
        assert profile.links_to(profile_home / "rules", main_home / "rules")
        assert profile.links_to(
            profile_home / "settings.json", main_home / "settings.json"
        )

    def test_should_link_only_what_the_callers_rule_shares(self, tmp_path: Path) -> None:
        main_home = build_main_home(tmp_path)
        profile_home = tmp_path / "codex-1"
        report = profile.sync_profile(
            main_home=main_home,
            profile_home=profile_home,
            now=NOW,
            is_local=lambda entry_name: entry_name != "rules",
        )
        assert report.all_linked == ("rules",)
        assert not (profile_home / "skills").exists()

    def test_should_keep_the_accounts_own_sign_in_state_and_history_apart(
        self, tmp_path: Path
    ) -> None:
        main_home = build_main_home(tmp_path)
        profile_home = tmp_path / "ev"
        profile_home.mkdir()
        (profile_home / ".credentials.json").write_text(
            "second sign-in", encoding="utf-8"
        )
        sync(main_home, profile_home)
        assert (profile_home / ".credentials.json").read_text(
            encoding="utf-8"
        ) == "second sign-in"
        assert not (profile_home / ".claude.json").exists()
        assert not (profile_home / ".claude.json.backup").exists()
        assert not (profile_home / "projects").exists()

    def test_should_move_a_stale_copy_aside_and_keep_its_content(
        self, tmp_path: Path
    ) -> None:
        main_home = build_main_home(tmp_path)
        profile_home = tmp_path / "ev"
        profile_home.mkdir()
        (profile_home / "CLAUDE.md").write_text("stale copy", encoding="utf-8")
        report = sync(main_home, profile_home)
        moved_copy = (
            profile_home / ".replaced" / NOW.strftime("%Y%m%dT%H%M%SZ") / "CLAUDE.md"
        )
        assert moved_copy.read_text(encoding="utf-8") == "stale copy"
        assert profile.links_to(profile_home / "CLAUDE.md", main_home / "CLAUDE.md")
        assert report.all_moved_aside == ("CLAUDE.md",)

    def test_should_remove_a_same_content_copy_without_moving_it_aside(
        self, tmp_path: Path
    ) -> None:
        main_home = build_main_home(tmp_path)
        profile_home = tmp_path / "ev"
        profile_home.mkdir()
        (profile_home / "CLAUDE.md").write_text("main instructions", encoding="utf-8")
        report = sync(main_home, profile_home)
        assert report.all_moved_aside == ()
        assert not (profile_home / ".replaced").exists()
        assert profile.links_to(profile_home / "CLAUDE.md", main_home / "CLAUDE.md")

    def test_should_move_aside_a_link_that_points_somewhere_else(
        self, tmp_path: Path
    ) -> None:
        main_home = build_main_home(tmp_path)
        elsewhere = tmp_path / "old-shared" / "rules"
        elsewhere.mkdir(parents=True)
        (elsewhere / "keep.md").write_text("old rule", encoding="utf-8")
        profile_home = tmp_path / "ev"
        profile_home.mkdir()
        (profile_home / "rules").symlink_to(elsewhere, target_is_directory=True)
        report = sync(main_home, profile_home)
        assert (elsewhere / "keep.md").read_text(encoding="utf-8") == "old rule"
        assert profile.links_to(profile_home / "rules", main_home / "rules")
        assert report.all_moved_aside == ("rules",)

    def test_should_change_nothing_on_a_second_run(self, tmp_path: Path) -> None:
        main_home = build_main_home(tmp_path)
        profile_home = tmp_path / "ev"
        sync(main_home, profile_home)
        second_report = sync(main_home, profile_home)
        assert second_report.all_linked == ()
        assert second_report.all_moved_aside == ()
        assert second_report.all_unlinked == ()

    def test_should_unlink_an_entry_the_main_home_no_longer_has(
        self, tmp_path: Path
    ) -> None:
        main_home = build_main_home(tmp_path)
        profile_home = tmp_path / "ev"
        sync(main_home, profile_home)
        (main_home / "rules").rmdir()
        report = sync(main_home, profile_home)
        assert not os.path.lexists(profile_home / "rules")
        assert report.all_unlinked == ("rules",)

    def test_should_keep_a_link_whose_target_refuses_access(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        main_home = build_main_home(tmp_path)
        (main_home / ".pytest_cache").mkdir()
        profile_home = tmp_path / "ev"
        profile_home.mkdir()
        locked_link = profile_home / ".pytest_cache"
        locked_link.symlink_to(main_home / ".pytest_cache", target_is_directory=True)
        unlocked_stat = Path.stat

        def stat_refusing_the_locked_link(
            self: Path, *, follow_symlinks: bool = True
        ) -> os.stat_result:
            if self == locked_link and follow_symlinks:
                raise PermissionError(5, "Access is denied", str(self))
            return unlocked_stat(self, follow_symlinks=follow_symlinks)

        monkeypatch.setattr(Path, "stat", stat_refusing_the_locked_link)
        report = sync(main_home, profile_home)
        assert profile.links_to(locked_link, main_home / ".pytest_cache")
        assert ".pytest_cache" not in report.all_unlinked


    def test_should_remove_a_main_link_left_under_an_account_local_name(
        self, tmp_path: Path
    ) -> None:
        main_home = build_main_home(tmp_path)
        (main_home / ".credentials.json.bak").write_text("main backup", encoding="utf-8")
        profile_home = tmp_path / "ev"
        profile_home.mkdir()
        os.link(main_home / ".credentials.json.bak", profile_home / ".credentials.json.bak")
        report = sync(main_home, profile_home)
        assert not os.path.lexists(profile_home / ".credentials.json.bak")
        assert (main_home / ".credentials.json.bak").read_text(
            encoding="utf-8"
        ) == "main backup"
        assert report.all_unlinked == (".credentials.json.bak",)


class TestWriteLauncher:
    def test_should_point_claude_at_the_profile_and_pass_every_argument(
        self, tmp_path: Path
    ) -> None:
        profile_home = tmp_path / "ev"
        launcher_path = profile.write_launcher(
            launcher_directory=tmp_path / "bin",
            profile_home=profile_home,
            now=NOW,
            profile_name="ev",
            launcher_program=CLAUDE_LAUNCHER_PROGRAM,
        )
        launcher_text = launcher_path.read_text(encoding="utf-8")
        assert f'set "CLAUDE_CONFIG_DIR={profile_home}"' in launcher_text
        assert "call claude %*" in launcher_text

    def test_should_move_an_older_launcher_aside(self, tmp_path: Path) -> None:
        launcher_directory = tmp_path / "bin"
        launcher_directory.mkdir()
        (launcher_directory / "claude-ev.cmd").write_text(
            "old launcher", encoding="utf-8"
        )
        profile.write_launcher(
            launcher_directory=launcher_directory,
            profile_home=tmp_path / "ev",
            now=NOW,
            profile_name="ev",
            launcher_program=CLAUDE_LAUNCHER_PROGRAM,
        )
        moved_launcher = launcher_directory / (
            "claude-ev.cmd.replaced-" + NOW.strftime("%Y%m%dT%H%M%SZ")
        )
        assert moved_launcher.read_text(encoding="utf-8") == "old launcher"

    def test_should_write_the_launcher_for_the_callers_program(
        self, tmp_path: Path
    ) -> None:
        launcher_path = profile.write_launcher(
            launcher_directory=tmp_path / "bin",
            profile_home=tmp_path / "alpha",
            now=NOW,
            profile_name="alpha",
            launcher_program=LauncherProgram(
                program="tool",
                environment_variable="TOOL_HOME",
                file_name_template="tool-{profile_name}.cmd",
            ),
        )
        assert launcher_path == tmp_path / "bin" / "tool-alpha.cmd"
        assert launcher_path.read_bytes() == (
            "@echo off\r\n"
            "setlocal\r\n"
            f'set "TOOL_HOME={tmp_path / "alpha"}"\r\n'
            "call tool %*\r\n"
            "exit /b %ERRORLEVEL%\r\n"
        ).encode()


NPM_SHIM_TEXT_TEMPLATE = (
    "@ECHO off\r\n"
    "GOTO start\r\n"
    ":find_dp0\r\n"
    "SET dp0=%~dp0\r\n"
    "EXIT /b\r\n"
    ":start\r\n"
    "SETLOCAL\r\n"
    "CALL :find_dp0\r\n"
    'SET "_prog=cmd"\r\n'
    "endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% &"
    ' "%_prog%" /d /c "echo %%{environment_variable}%%"\r\n'
)


class TestNpmShimLauncher:
    @pytest.mark.skipif(os.name != "nt", reason="runs the launcher through cmd.exe")
    @pytest.mark.parametrize(
        "launcher_program",
        [
            pytest.param(CLAUDE_LAUNCHER_PROGRAM, id="claude"),
            pytest.param(CODEX_LAUNCHER_PROGRAM, id="codex"),
        ],
    )
    def should_hand_the_profile_home_to_the_npm_shim(
        self, tmp_path: Path, launcher_program: LauncherProgram
    ) -> None:
        profile_home = tmp_path / "profiles" / "alpha"
        launcher_path = profile.write_launcher(
            launcher_directory=tmp_path / "bin",
            profile_home=profile_home,
            now=NOW,
            profile_name="alpha",
            launcher_program=launcher_program,
        )
        fake_directory = tmp_path / "fake"
        fake_directory.mkdir()
        (fake_directory / f"{launcher_program.program}.cmd").write_bytes(
            NPM_SHIM_TEXT_TEMPLATE.format(
                environment_variable=launcher_program.environment_variable
            ).encode("utf-8")
        )
        environment = dict(os.environ)
        environment["PATH"] = str(fake_directory) + os.pathsep + environment["PATH"]
        environment[launcher_program.environment_variable] = str(tmp_path / "decoy")
        completed = subprocess.run(
            ["cmd", "/c", str(launcher_path)],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.stdout.strip() == str(profile_home)


class TestMoveLauncherAside:
    def test_should_rename_the_launcher_with_the_run_time(self, tmp_path: Path) -> None:
        launcher_path = tmp_path / "tool-alpha.cmd"
        launcher_path.write_text("launcher", encoding="utf-8")
        moved_path = profile.move_launcher_aside(launcher_path, NOW)
        assert moved_path == tmp_path / "tool-alpha.cmd.replaced-20260922T210000Z"
        assert moved_path.read_text(encoding="utf-8") == "launcher"
        assert not launcher_path.exists()


class TestMain:
    def test_should_print_what_the_sync_changed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main_home = build_main_home(tmp_path)
        exit_code = profile.main(
            [
                "--main-home",
                str(main_home),
                "--profile-home",
                str(tmp_path / "ev"),
                "--launcher-directory",
                str(tmp_path / "bin"),
            ]
        )
        printed = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        assert "CLAUDE.md" in printed["linked"]
        assert printed["launcher"] == str(tmp_path / "bin" / "claude-ev.cmd")


def test_should_create_named_profile_and_launcher_without_changes_on_repeat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    main_home = build_main_home(tmp_path)
    (main_home / "extra-profiles.json").write_text("[]", encoding="utf-8")
    profiles_root = tmp_path / "profiles"
    launcher_directory = tmp_path / "bin"
    monkeypatch.setenv("LLM_SETTINGS_PROFILES_ROOT", str(profiles_root))
    arguments = [
        "--main-home",
        str(main_home),
        "--profile-name",
        "profile-3",
        "--launcher-directory",
        str(launcher_directory),
    ]

    assert profile.main(arguments) == 0
    first_report = json.loads(capsys.readouterr().out)
    profile_home = profiles_root / "profile-3"
    launcher_path = launcher_directory / "claude-profile-3.cmd"
    assert profile.links_to(profile_home / "CLAUDE.md", main_home / "CLAUDE.md")
    assert not (profile_home / "extra-profiles.json").exists()
    assert first_report["launcher"] == str(launcher_path)
    assert f'set "CLAUDE_CONFIG_DIR={profile_home}"' in launcher_path.read_text(
        encoding="utf-8"
    )

    assert profile.main(arguments) == 0
    second_report = json.loads(capsys.readouterr().out)
    assert second_report["linked"] == []
    assert second_report["moved_aside"] == []
    assert second_report["unlinked"] == []
    assert list(launcher_directory.glob("*.replaced-*")) == []


@pytest.mark.parametrize(
    "profile_name", ["../outside", "bad name", "CON", "main", "wait"]
)
def test_should_reject_unsafe_profile_names(profile_name: str) -> None:
    with pytest.raises(ValueError):
        profile.default_profile_home(profile_name)


def test_sync_report_payload_should_list_each_entry_under_its_own_key() -> None:
    report = profile.ProfileSyncReport(
        all_linked=("CLAUDE.md", "skills"),
        all_moved_aside=("settings.json",),
        all_unlinked=("rules",),
    )

    assert profile.sync_report_payload(report) == {
        "linked": ["CLAUDE.md", "skills"],
        "moved_aside": ["settings.json"],
        "unlinked": ["rules"],
    }
