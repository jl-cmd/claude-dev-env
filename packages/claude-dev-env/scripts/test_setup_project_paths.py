"""Tests for setup_project_paths — one-time bootstrap script."""

import inspect
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
_HOOKS_DIR = _SCRIPTS_DIR.parent / "hooks"
_SESSION_HOOKS_PACKAGE_DIR = _SCRIPTS_DIR.parent / "hooks" / "session"
for each_sys_path_entry in (
    str(_SCRIPTS_DIR),
    str(_HOOKS_DIR),
    str(_SESSION_HOOKS_PACKAGE_DIR),
):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

import setup_project_paths as setup
import untracked_repo_detector as detector_module
from config.project_paths_reader import registry_file_path
from config.setup_project_paths_constants import (
    ABORTED_NOTHING_WRITTEN_MESSAGE,
    CONFIRMATION_PROMPT_TEXT,
    ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS,
    WROTE_ENTRIES_STATUS_TEMPLATE,
)


class TestFinalSegmentFilter:
    def test_retains_dot_git_directory(self) -> None:
        all_paths = ["C:\\Projects\\my-repo\\.git"]
        retained = setup.filter_to_git_roots(all_paths)
        assert retained == ["C:\\Projects\\my-repo"]

    def test_rejects_dot_gitignore(self) -> None:
        all_paths = ["C:\\Projects\\my-repo\\.gitignore"]
        retained = setup.filter_to_git_roots(all_paths)
        assert retained == []

    def test_rejects_dot_github(self) -> None:
        all_paths = ["C:\\Projects\\my-repo\\.github"]
        retained = setup.filter_to_git_roots(all_paths)
        assert retained == []

    def test_accepts_dot_git_with_forward_slashes(self) -> None:
        all_paths = ["C:/Projects/my-repo/.git"]
        retained = setup.filter_to_git_roots(all_paths)
        assert retained == ["C:/Projects/my-repo"]

    def test_retains_multiple_valid_git_roots(self) -> None:
        all_paths = [
            "C:\\Projects\\alpha\\.git",
            "D:\\Work\\beta\\.git",
        ]
        retained = setup.filter_to_git_roots(all_paths)
        assert "C:\\Projects\\alpha" in retained
        assert "D:\\Work\\beta" in retained

    def test_rejects_dot_git_attributes(self) -> None:
        all_paths = ["C:\\Projects\\my-repo\\.gitattributes"]
        retained = setup.filter_to_git_roots(all_paths)
        assert retained == []


class TestExclusionFilter:
    def test_drops_path_with_temp_segment(self) -> None:
        all_candidates = ["C:\\temp\\my-repo"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_drops_path_with_tmp_segment(self) -> None:
        all_candidates = ["C:\\tmp\\my-repo"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_drops_path_with_worktree_segment(self) -> None:
        all_candidates = ["C:\\Projects\\main\\worktree\\feature"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_drops_path_with_node_modules_segment(self) -> None:
        all_candidates = ["C:\\Projects\\app\\node_modules\\pkg"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_drops_path_with_dot_cache_segment(self) -> None:
        all_candidates = ["C:\\Users\\jon\\.cache\\build"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_drops_path_with_recycle_bin_segment(self) -> None:
        all_candidates = ["C:\\$Recycle.Bin\\S-1-5\\my-repo"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_preserves_path_with_template_segment(self) -> None:
        all_candidates = ["C:\\Projects\\template"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == ["C:\\Projects\\template"]

    def test_preserves_legitimate_project_path(self) -> None:
        all_candidates = ["Y:\\Projects\\my-app"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == ["Y:\\Projects\\my-app"]

    def test_whole_segment_match_does_not_drop_template(self) -> None:
        all_candidates = ["C:\\Projects\\my-templates\\repo"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == ["C:\\Projects\\my-templates\\repo"]


class TestMergeRegistries:
    def test_merge_preserves_pre_existing_entries(self) -> None:
        existing_registry = {
            "_meta": {"schema_version": 1, "last_scan": "2026-01-01T00:00:00Z"},
            "old-repo": "C:\\Old\\old-repo",
        }
        new_path_by_name = {"new-repo": "D:\\New\\new-repo"}
        merged = setup.merge_registries(existing_registry, new_path_by_name)
        assert merged["old-repo"] == "C:\\Old\\old-repo"
        assert merged["new-repo"] == "D:\\New\\new-repo"

    def test_merge_updates_meta_last_scan(self) -> None:
        existing_registry: dict = {}
        new_path_by_name = {"alpha": "C:\\alpha"}
        merged = setup.merge_registries(existing_registry, new_path_by_name)
        assert "_meta" in merged
        assert "last_scan" in merged["_meta"]

    def test_merge_new_entry_wins_on_name_collision(self) -> None:
        existing_registry = {"my-repo": "C:\\Old\\path"}
        new_path_by_name = {"my-repo": "D:\\New\\path"}
        merged = setup.merge_registries(existing_registry, new_path_by_name)
        assert merged["my-repo"] == "D:\\New\\path"


class TestAtomicWrite:
    def test_write_creates_file_with_correct_content(self, tmp_path: Path) -> None:
        target_file = tmp_path / "project-paths.json"
        registry_to_write = {"_meta": {"schema_version": 1}, "repo": "C:\\repo"}
        setup.write_registry_atomically(registry_to_write, target_file)
        written_content = json.loads(target_file.read_text(encoding="utf-8"))
        assert written_content["repo"] == "C:\\repo"

    def test_write_leaves_no_temp_file_on_success(self, tmp_path: Path) -> None:
        target_file = tmp_path / "project-paths.json"
        registry_to_write = {"_meta": {"schema_version": 1}}
        setup.write_registry_atomically(registry_to_write, target_file)
        all_files = list(tmp_path.iterdir())
        assert all_files == [target_file]

    def test_write_overwrites_without_schema_check(self, tmp_path: Path) -> None:
        target_file = tmp_path / "project-paths.json"
        target_file.write_text(
            json.dumps({"_meta": {"schema_version": 99}}), encoding="utf-8"
        )
        registry_to_write = {"_meta": {"schema_version": 1}, "repo": "C:\\repo"}
        setup.write_registry_atomically(registry_to_write, target_file)
        written_content = json.loads(target_file.read_text(encoding="utf-8"))
        assert written_content["repo"] == "C:\\repo"


class TestEsExeQueryArguments:
    def test_arguments_do_not_include_name_flag(self) -> None:
        assert "-name" not in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS

    def test_arguments_include_folders_only_flag(self) -> None:
        assert "/ad" in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS

    def test_arguments_include_git_folder_query(self) -> None:
        assert "folder:.git" in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS

    def test_filter_to_git_roots_processes_full_absolute_paths(self) -> None:
        all_raw_paths = [
            "C:\\Projects\\my-repo\\.git",
            "D:\\Work\\other-repo\\.git",
        ]
        all_roots = setup.filter_to_git_roots(all_raw_paths)
        assert "C:\\Projects\\my-repo" in all_roots
        assert "D:\\Work\\other-repo" in all_roots


class TestUserRejection:
    def test_user_rejection_at_final_prompt_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        target_file = tmp_path / "project-paths.json"
        assert not target_file.exists()
        with patch("builtins.input", return_value="no"):
            setup.prompt_and_write(
                path_by_name={"my-repo": "C:\\my-repo"},
                save_path=target_file,
            )
        assert not target_file.exists()


class TestDuplicateLeafName:
    def test_duplicate_leaf_name_keeps_first_seen_entry(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        all_roots = sorted(["Y:\\A\\foo", "Y:\\B\\foo"])
        path_by_name = setup._build_path_by_name_from_roots(all_roots)
        assert len(path_by_name) == 1
        assert path_by_name["foo"] == "Y:\\A\\foo"

    def test_duplicate_leaf_name_prints_collision_warning(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        all_roots = sorted(["Y:\\A\\foo", "Y:\\B\\foo"])
        setup._build_path_by_name_from_roots(all_roots)
        captured = capsys.readouterr()
        assert "Duplicate leaf name 'foo'" in captured.out
        assert "Y:\\A\\foo" in captured.out
        assert "Y:\\B\\foo" in captured.out


class TestMapNamingConvention:
    def test_merge_registries_signature_uses_path_by_name(self) -> None:
        """Pin PR #230 round 3 rename: X_by_Y means X indexed by Y.

        The map's keys are repo names and values are paths, so the correct
        name is `path_by_name` (path indexed by name). The old inverted
        name `name_by_path` must not reappear.
        """
        merge_signature = inspect.signature(setup.merge_registries)
        assert "new_path_by_name" in merge_signature.parameters
        assert "new_name_by_path" not in merge_signature.parameters

    def test_build_helper_is_named_path_by_name(self) -> None:
        assert hasattr(setup, "_build_path_by_name_from_roots")
        assert not hasattr(setup, "_build_name_by_path_from_roots")


class TestRegistryReadError:
    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        missing_file = tmp_path / "nonexistent.json"
        result = setup._read_existing_registry(missing_file)
        assert result == {}

    def test_malformed_json_raises_registry_read_error(self, tmp_path: Path) -> None:
        corrupt_file = tmp_path / "project-paths.json"
        corrupt_file.write_text("{ not valid json", encoding="utf-8")
        with pytest.raises(setup.RegistryReadError):
            setup._read_existing_registry(corrupt_file)

    def test_non_dict_top_level_raises_registry_read_error(self, tmp_path: Path) -> None:
        non_dict_file = tmp_path / "project-paths.json"
        non_dict_file.write_text(json.dumps(["a", "b"]), encoding="utf-8")
        with pytest.raises(setup.RegistryReadError):
            setup._read_existing_registry(non_dict_file)

    def test_oserror_raises_registry_read_error(self, tmp_path: Path) -> None:
        existing_file = tmp_path / "project-paths.json"
        existing_file.write_text("{}", encoding="utf-8")
        with patch.object(
            type(existing_file),
            "read_text",
            side_effect=OSError("permission denied"),
        ):
            with pytest.raises(setup.RegistryReadError):
                setup._read_existing_registry(existing_file)

    def test_registry_read_error_in_prompt_and_write_exits_nonzero(
        self, tmp_path: Path
    ) -> None:
        corrupt_file = tmp_path / "project-paths.json"
        corrupt_file.write_text("{ not valid json", encoding="utf-8")
        with patch("builtins.input", return_value="yes"):
            with pytest.raises(SystemExit) as raised_exit:
                setup.prompt_and_write(
                    path_by_name={"my-repo": "C:\\my-repo"},
                    save_path=corrupt_file,
                )
        assert raised_exit.value.code != 0

    def test_registry_read_error_does_not_overwrite_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        corrupt_file = tmp_path / "project-paths.json"
        original_content = "{ not valid json"
        corrupt_file.write_text(original_content, encoding="utf-8")
        with patch("builtins.input", return_value="yes"):
            with pytest.raises(SystemExit):
                setup.prompt_and_write(
                    path_by_name={"my-repo": "C:\\my-repo"},
                    save_path=corrupt_file,
                )
        assert corrupt_file.read_text(encoding="utf-8") == original_content


class TestEarlyRegistryValidation:
    def test_malformed_registry_exits_before_prompting(self, tmp_path: Path) -> None:
        corrupt_file = tmp_path / "project-paths.json"
        corrupt_file.write_text("{ not valid json", encoding="utf-8")
        prompt_call_count = 0

        def counting_input(prompt_text: str) -> str:
            nonlocal prompt_call_count
            prompt_call_count += 1
            return "yes"

        with patch("builtins.input", side_effect=counting_input):
            with pytest.raises(SystemExit) as raised_exit:
                setup.prompt_and_write(
                    path_by_name={"my-repo": "C:\\my-repo"},
                    save_path=corrupt_file,
                )
        assert raised_exit.value.code != 0
        assert prompt_call_count == 0

    def test_malformed_registry_leaves_file_untouched(self, tmp_path: Path) -> None:
        corrupt_file = tmp_path / "project-paths.json"
        original_content = "{ not valid json"
        corrupt_file.write_text(original_content, encoding="utf-8")
        with patch("builtins.input", return_value="yes"):
            with pytest.raises(SystemExit):
                setup.prompt_and_write(
                    path_by_name={"my-repo": "C:\\my-repo"},
                    save_path=corrupt_file,
                )
        assert corrupt_file.read_text(encoding="utf-8") == original_content

    def test_schema_mismatch_exits_before_prompting(self, tmp_path: Path) -> None:
        target_file = tmp_path / "project-paths.json"
        target_file.write_text(
            json.dumps({"_meta": {"schema_version": 99}}), encoding="utf-8"
        )
        prompt_call_count = 0

        def counting_input(prompt_text: str) -> str:
            nonlocal prompt_call_count
            prompt_call_count += 1
            return "yes"

        with patch("builtins.input", side_effect=counting_input):
            with pytest.raises(SystemExit) as raised_exit:
                setup.prompt_and_write(
                    path_by_name={"my-repo": "C:\\my-repo"},
                    save_path=target_file,
                )
        assert raised_exit.value.code != 0
        assert prompt_call_count == 0

    def test_schema_mismatch_leaves_file_untouched(self, tmp_path: Path) -> None:
        target_file = tmp_path / "project-paths.json"
        original_registry = {"_meta": {"schema_version": 99}}
        target_file.write_text(json.dumps(original_registry), encoding="utf-8")
        with patch("builtins.input", return_value="yes"):
            with pytest.raises(SystemExit):
                setup.prompt_and_write(
                    path_by_name={"my-repo": "C:\\my-repo"},
                    save_path=target_file,
                )
        written_back = json.loads(target_file.read_text(encoding="utf-8"))
        assert written_back == original_registry

    def test_registry_read_exactly_once_across_full_write_path(
        self, tmp_path: Path
    ) -> None:
        target_file = tmp_path / "project-paths.json"
        target_file.write_text(
            json.dumps({"_meta": {"schema_version": 1}, "existing-repo": "C:\\existing"}),
            encoding="utf-8",
        )
        read_call_count = 0
        original_read = setup._read_existing_registry

        def counting_read(target: Path) -> dict:
            nonlocal read_call_count
            read_call_count += 1
            return original_read(target)

        with patch("setup_project_paths._read_existing_registry", side_effect=counting_read):
            with patch("builtins.input", return_value="yes"):
                setup.prompt_and_write(
                    path_by_name={"my-repo": "C:\\my-repo"},
                    save_path=target_file,
                )
        assert read_call_count == 1


class TestDiscoverRepoRootsDedup:
    def test_discover_returns_sorted_unique_paths(self) -> None:
        all_paths = [
            "C:\\Projects\\beta\\.git",
            "C:\\Projects\\alpha\\.git",
            "C:\\Projects\\alpha\\.git",
        ]
        with patch("setup_project_paths._run_es_exe_folders_query", return_value=all_paths):
            all_roots = setup.discover_repo_roots_via_everything()
        assert all_roots == sorted(set(all_roots))
        assert len(all_roots) == len(set(all_roots))


class TestPromptAndWriteUsesConstants:
    def test_confirmation_prompt_text_comes_from_constants(self) -> None:
        captured_prompts: list[str] = []

        def capturing_input(prompt_text: str) -> str:
            captured_prompts.append(prompt_text)
            return "no"

        with patch("builtins.input", side_effect=capturing_input):
            setup.prompt_and_write(
                path_by_name={"my-repo": "C:\\my-repo"},
                save_path=Path("/nonexistent/path.json"),
            )
        assert len(captured_prompts) == 1
        assert captured_prompts[0] == CONFIRMATION_PROMPT_TEXT

    def test_abort_message_comes_from_constants(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        with patch("builtins.input", return_value="no"):
            setup.prompt_and_write(
                path_by_name={"my-repo": "C:\\my-repo"},
                save_path=Path("/nonexistent/path.json"),
            )
        captured = capsys.readouterr()
        assert ABORTED_NOTHING_WRITTEN_MESSAGE in captured.out

    def test_wrote_entries_status_uses_constants_template(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        target_file = tmp_path / "project-paths.json"
        with patch("builtins.input", return_value="yes"):
            setup.prompt_and_write(
                path_by_name={"my-repo": "C:\\my-repo"},
                save_path=target_file,
            )
        captured = capsys.readouterr()
        expected_message = WROTE_ENTRIES_STATUS_TEMPLATE.format(
            entry_count=1, save_path=target_file
        )
        assert expected_message in captured.out


class TestEverythingScanError:
    def test_nonzero_return_code_raises_everything_scan_error(self) -> None:
        failed_completion = subprocess.CompletedProcess(
            args=["es.exe"],
            returncode=1,
            stdout="",
            stderr="service not running",
        )
        with patch("subprocess.run", return_value=failed_completion):
            with pytest.raises(setup.EverythingScanError) as raised_error:
                setup._run_es_exe_folders_query()
        assert "service not running" in str(raised_error.value)

    def test_nonzero_return_code_includes_return_code_in_message(self) -> None:
        failed_completion = subprocess.CompletedProcess(
            args=["es.exe"],
            returncode=2,
            stdout="",
            stderr="access denied",
        )
        with patch("subprocess.run", return_value=failed_completion):
            with pytest.raises(setup.EverythingScanError) as raised_error:
                setup._run_es_exe_folders_query()
        assert "2" in str(raised_error.value)

    def test_zero_return_code_returns_parsed_paths(self) -> None:
        successful_completion = subprocess.CompletedProcess(
            args=["es.exe"],
            returncode=0,
            stdout="C:\\Projects\\alpha\\.git\nD:\\Work\\beta\\.git\n",
            stderr="",
        )
        with patch("subprocess.run", return_value=successful_completion):
            all_paths = setup._run_es_exe_folders_query()
        assert all_paths == ["C:\\Projects\\alpha\\.git", "D:\\Work\\beta\\.git"]

    def test_main_catches_everything_scan_error_and_exits_nonzero(self) -> None:
        with (
            patch(
                "setup_project_paths._everything_binary_is_available",
                return_value=True,
            ),
            patch(
                "setup_project_paths._run_es_exe_folders_query",
                side_effect=setup.EverythingScanError("service not running: exit 1"),
            ),
            pytest.raises(SystemExit) as raised_exit,
        ):
            setup.main()
        assert raised_exit.value.code != 0

    def test_main_prints_clear_error_to_stderr_on_everything_scan_error(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        with (
            patch(
                "setup_project_paths._everything_binary_is_available",
                return_value=True,
            ),
            patch(
                "setup_project_paths._run_es_exe_folders_query",
                side_effect=setup.EverythingScanError("service not running: exit 1"),
            ),
            pytest.raises(SystemExit),
        ):
            setup.main()
        captured = capsys.readouterr()
        assert "Everything scan failed" in captured.err
        assert "service" in captured.err.lower()


class TestSharedConfigPath:
    def test_default_user_config_path_matches_project_paths_reader(self) -> None:
        assert setup._default_user_config_path() == registry_file_path()

    def test_untracked_repo_detector_config_path_matches_project_paths_reader(
        self,
    ) -> None:
        shared_path = registry_file_path()
        assert str(shared_path) in detector_module._build_confirm_instruction(
            str(shared_path.parent)
        ) or "project-paths.json" in detector_module._build_confirm_instruction(
            str(shared_path.parent)
        )

    def test_all_three_modules_resolve_identical_config_path(self) -> None:
        shared_path = registry_file_path()
        assert shared_path == setup._default_user_config_path()
        assert shared_path.name == "project-paths.json"
        assert shared_path.parent.name == ".claude"
