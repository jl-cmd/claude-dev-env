"""Tests for untracked_repo_detector — SessionStart hook for new repo detection."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

_SESSION_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _SESSION_DIR.parent
for each_sys_path_entry in (str(_SESSION_DIR), str(_HOOKS_ROOT)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

import untracked_repo_detector as detector
from config.project_paths_reader import registry_file_path
from config.setup_project_paths_constants import GIT_DIRECTORY_SEGMENT_NAME


def _run_main_with_cwd(cwd: str, known_registry: dict) -> tuple[str, str, int]:
    """Return (stdout, stderr, exit_code) from running main() with patched cwd and registry."""
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    exit_code = 0
    try:
        with (
            patch(
                "untracked_repo_detector.current_working_directory", return_value=cwd
            ),
            patch("untracked_repo_detector.load_registry", return_value=known_registry),
            patch("sys.stdout", captured_stdout),
            patch("sys.stderr", captured_stderr),
        ):
            detector.main()
    except SystemExit as e:
        exit_code = e.code or 0
    return captured_stdout.getvalue(), captured_stderr.getvalue(), exit_code


class TestFindGitRoot:
    def test_returns_none_when_no_git_directory_found(self, tmp_path: Path) -> None:
        non_repo_path = tmp_path / "not-a-repo"
        non_repo_path.mkdir()
        original_exists = Path.exists

        def exists_without_ambient_git(self_path: Path) -> bool:
            if self_path.name == ".git" and tmp_path.resolve() not in self_path.resolve().parents and self_path.resolve().parent != tmp_path.resolve():
                return False
            return original_exists(self_path)

        with patch.object(Path, "exists", exists_without_ambient_git):
            found_root = detector.find_git_root(str(non_repo_path))
        assert found_root is None

    def test_returns_root_when_dot_git_exists(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "my-repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        found_root = detector.find_git_root(str(repo_root))
        assert found_root is not None
        assert Path(found_root).resolve() == repo_root.resolve()

    def test_returns_root_when_cwd_is_subdirectory(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "my-repo"
        nested_directory = repo_root / "src" / "deep"
        nested_directory.mkdir(parents=True)
        (repo_root / ".git").mkdir()
        found_root = detector.find_git_root(str(nested_directory))
        assert found_root is not None
        assert Path(found_root).resolve() == repo_root.resolve()


class TestRegistryContainsRepo:
    def test_cwd_inside_tracked_repo_produces_no_output(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "tracked-repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        known_registry = {"tracked-repo": str(repo_root)}
        stdout, _, _ = _run_main_with_cwd(str(repo_root), known_registry)
        assert stdout.strip() == ""

    def test_cwd_outside_any_git_repo_produces_no_output(self, tmp_path: Path) -> None:
        non_repo = tmp_path / "not-a-repo"
        non_repo.mkdir()
        with patch("untracked_repo_detector.find_git_root", return_value=None):
            stdout, _, _ = _run_main_with_cwd(str(non_repo), {})
        assert stdout.strip() == ""


class TestUntrackedRepoDetection:
    def test_cwd_inside_untracked_repo_produces_additional_context(
        self, tmp_path: Path
    ) -> None:
        repo_root = tmp_path / "new-repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        stdout, _, _ = _run_main_with_cwd(str(repo_root), {})
        assert stdout.strip() != ""
        emitted = json.loads(stdout)
        assert "additionalContext" in emitted

    def test_emitted_context_names_the_detected_repo_path(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "new-repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        stdout, _, _ = _run_main_with_cwd(str(repo_root), {})
        emitted = json.loads(stdout)
        context_text = emitted["additionalContext"]
        assert str(repo_root) in context_text

    def test_emitted_context_names_the_config_file_path(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "new-repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        stdout, _, _ = _run_main_with_cwd(str(repo_root), {})
        emitted = json.loads(stdout)
        context_text = emitted["additionalContext"]
        assert "project-paths.json" in context_text

    def test_emitted_context_instructs_claude_to_use_ask_user_question(
        self, tmp_path: Path
    ) -> None:
        repo_root = tmp_path / "new-repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        stdout, _, _ = _run_main_with_cwd(str(repo_root), {})
        emitted = json.loads(stdout)
        context_text = emitted["additionalContext"]
        assert "AskUserQuestion" in context_text

    def test_emitted_context_states_hook_has_written_nothing(
        self, tmp_path: Path
    ) -> None:
        repo_root = tmp_path / "new-repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        stdout, _, _ = _run_main_with_cwd(str(repo_root), {})
        emitted = json.loads(stdout)
        context_text = emitted["additionalContext"]
        assert (
            "written nothing" in context_text.lower()
            or "has not written" in context_text.lower()
        )


class TestSharedRegistryPath:
    def test_config_file_path_not_a_module_level_attribute(self) -> None:
        """Pin PR #230 round 7: _CONFIG_FILE_PATH inlined into _build_confirm_instruction.

        Single-consumer module-level constant moved to local per file-global-constants rule.
        """
        assert not hasattr(detector, "_CONFIG_FILE_PATH")

    def test_confirm_instruction_contains_registry_file_path(
        self, tmp_path: Path
    ) -> None:
        repo_root = str(tmp_path / "some-repo")
        instruction_text = detector._build_confirm_instruction(repo_root)
        assert str(registry_file_path()) in instruction_text

    def test_confirm_instruction_contains_project_paths_json(
        self, tmp_path: Path
    ) -> None:
        repo_root = str(tmp_path / "some-repo")
        instruction_text = detector._build_confirm_instruction(repo_root)
        assert "project-paths.json" in instruction_text


class TestSharedGitDirectoryConstant:
    def test_find_git_root_uses_shared_git_directory_constant(self, tmp_path: Path) -> None:
        """Pin: find_git_root must use GIT_DIRECTORY_SEGMENT_NAME from shared constants."""
        repo_root = tmp_path / "uses-shared-constant"
        repo_root.mkdir()
        (repo_root / GIT_DIRECTORY_SEGMENT_NAME).mkdir()
        found_root = detector.find_git_root(str(repo_root))
        assert found_root is not None


class TestPathNormalization:
    def test_windows_and_posix_forms_of_same_path_compare_equal(
        self, tmp_path: Path
    ) -> None:
        repo_root = tmp_path / "cross-platform-repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        windows_path = str(repo_root)
        posix_path = str(repo_root).replace("\\", "/")
        registry_with_posix = {"cross-platform-repo": posix_path}
        stdout, _, _ = _run_main_with_cwd(windows_path, registry_with_posix)
        assert stdout.strip() == ""
