"""Tests for the second-account profile sync and its launcher."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

import claude_account_profile as profile

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
    def should_use_the_profiles_root_the_environment_names(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_SETTINGS_PROFILES_ROOT", str(tmp_path))
        assert profile.default_profile_home() == tmp_path / "ev"

    def should_fall_back_to_the_profiles_root_in_the_user_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LLM_SETTINGS_PROFILES_ROOT", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert profile.default_profile_home() == tmp_path / ".claude-profiles" / "ev"


class TestIsAccountLocal:
    def should_keep_sign_in_state_and_history_local(self) -> None:
        for each_name in (
            ".credentials.json",
            ".credentials.json.bak-session-dashboard",
            ".claude.json",
            ".claude.json.backup",
            "projects",
        ):
            assert profile.is_account_local(each_name)

    def should_share_skills_rules_and_settings(self) -> None:
        for each_name in ("skills", "rules", "CLAUDE.md", "settings.json", "plugins"):
            assert not profile.is_account_local(each_name)


class TestSyncProfile:
    def should_link_every_shared_entry_to_the_main_home(self, tmp_path: Path) -> None:
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

    def should_link_only_what_the_callers_rule_shares(self, tmp_path: Path) -> None:
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

    def should_keep_the_accounts_own_sign_in_state_and_history_apart(
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

    def should_move_a_stale_copy_aside_and_keep_its_content(
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

    def should_remove_a_same_content_copy_without_moving_it_aside(
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

    def should_move_aside_a_link_that_points_somewhere_else(
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

    def should_change_nothing_on_a_second_run(self, tmp_path: Path) -> None:
        main_home = build_main_home(tmp_path)
        profile_home = tmp_path / "ev"
        sync(main_home, profile_home)
        second_report = sync(main_home, profile_home)
        assert second_report.all_linked == ()
        assert second_report.all_moved_aside == ()
        assert second_report.all_unlinked == ()

    def should_unlink_an_entry_the_main_home_no_longer_has(
        self, tmp_path: Path
    ) -> None:
        main_home = build_main_home(tmp_path)
        profile_home = tmp_path / "ev"
        sync(main_home, profile_home)
        (main_home / "rules").rmdir()
        report = sync(main_home, profile_home)
        assert not os.path.lexists(profile_home / "rules")
        assert report.all_unlinked == ("rules",)


    def should_remove_a_main_link_left_under_an_account_local_name(
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
    def should_point_claude_at_the_profile_and_pass_every_argument(
        self, tmp_path: Path
    ) -> None:
        profile_home = tmp_path / "ev"
        launcher_path = profile.write_launcher(
            launcher_directory=tmp_path / "bin", profile_home=profile_home, now=NOW
        )
        launcher_text = launcher_path.read_text(encoding="utf-8")
        assert f'set "CLAUDE_CONFIG_DIR={profile_home}"' in launcher_text
        assert "claude %*" in launcher_text

    def should_move_an_older_launcher_aside(self, tmp_path: Path) -> None:
        launcher_directory = tmp_path / "bin"
        launcher_directory.mkdir()
        (launcher_directory / "claude-ev.cmd").write_text(
            "old launcher", encoding="utf-8"
        )
        profile.write_launcher(
            launcher_directory=launcher_directory, profile_home=tmp_path / "ev", now=NOW
        )
        moved_launcher = launcher_directory / (
            "claude-ev.cmd.replaced-" + NOW.strftime("%Y%m%dT%H%M%SZ")
        )
        assert moved_launcher.read_text(encoding="utf-8") == "old launcher"


class TestMain:
    def should_print_what_the_sync_changed(
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
