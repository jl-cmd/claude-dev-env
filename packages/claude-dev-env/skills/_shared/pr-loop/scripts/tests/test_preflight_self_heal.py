"""Tests for the preflight self-heal helper.

Each test mocks ``subprocess.run`` with an ordered ``side_effect`` list so the
helper's three potential calls (local read, global read, local unset) are
distinguishable.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import preflight_self_heal


CANONICAL_SUFFIX = "hooks/git-hooks"


def _make_completed_process(
    stdout: str, returncode: int
) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = returncode
    return process


def _was_called_with_argument(
    mock_subprocess_run: MagicMock, expected_argument: str
) -> bool:
    """Return True when *expected_argument* appears as an element of any call's argv.

    Uses list-membership (Python ``in`` on a list is element-equality), so
    `"--get"` matches `["git", "config", "--get", ...]` but not
    `["git", "config", "--get-all", ...]`.
    """
    return any(
        expected_argument in each_call_args[0][0]
        for each_call_args in mock_subprocess_run.call_args_list
    )


def test_is_canonical_when_suffix_matches() -> None:
    assert preflight_self_heal._is_canonical_hooks_path_entry(
        "/home/me/.claude/hooks/git-hooks", CANONICAL_SUFFIX
    )


def test_is_canonical_normalizes_windows_separators_and_trailing_slash() -> None:
    assert preflight_self_heal._is_canonical_hooks_path_entry(
        "C:\\Users\\me\\.claude\\hooks\\git-hooks\\", CANONICAL_SUFFIX
    )


def test_is_canonical_rejects_non_matching_suffix() -> None:
    assert not preflight_self_heal._is_canonical_hooks_path_entry(
        "/some/other/path/.husky", CANONICAL_SUFFIX
    )


def test_is_canonical_rejects_seeded_git_hooks_path() -> None:
    assert not preflight_self_heal._is_canonical_hooks_path_entry(
        "/repo/.git/hooks", CANONICAL_SUFFIX
    )


def test_canonical_global_helper_returns_true_for_canonical_value() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "/home/me/.claude/hooks/git-hooks\n", returncode=0
        )
        assert preflight_self_heal._canonical_global_hooks_path_is_set(CANONICAL_SUFFIX)


def test_canonical_global_helper_returns_false_when_unset() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        assert not preflight_self_heal._canonical_global_hooks_path_is_set(
            CANONICAL_SUFFIX
        )


def test_canonical_global_helper_returns_false_when_non_canonical() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "/some/other/path/.husky\n", returncode=0
        )
        assert not preflight_self_heal._canonical_global_hooks_path_is_set(
            CANONICAL_SUFFIX
        )


def test_canonical_global_helper_normalizes_trailing_whitespace_and_separators() -> (
    None
):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "  C:\\Users\\me\\.claude\\hooks\\git-hooks  \n", returncode=0
        )
        assert preflight_self_heal._canonical_global_hooks_path_is_set(CANONICAL_SUFFIX)


def test_canonical_global_helper_returns_true_when_any_multi_value_is_canonical() -> (
    None
):
    multi_global_entries = "/some/other/path/.husky\n/home/me/.claude/hooks/git-hooks\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            multi_global_entries, returncode=0
        )
        assert preflight_self_heal._canonical_global_hooks_path_is_set(CANONICAL_SUFFIX)


def test_canonical_global_helper_returns_false_when_git_missing() -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        assert not preflight_self_heal._canonical_global_hooks_path_is_set(
            CANONICAL_SUFFIX
        )


def test_canonical_global_helper_returns_false_when_os_error() -> None:
    with patch("subprocess.run", side_effect=OSError("permission denied")):
        assert not preflight_self_heal._canonical_global_hooks_path_is_set(
            CANONICAL_SUFFIX
        )


def test_silent_clear_is_noop_when_repository_root_is_none() -> None:
    with patch("subprocess.run") as mock_run:
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            None, CANONICAL_SUFFIX
        )
    assert mock_run.call_count == 0


def test_silent_clear_is_noop_when_local_core_hooks_path_unset() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            Path("."), CANONICAL_SUFFIX
        )
    assert mock_run.call_count == 1
    assert not _was_called_with_argument(mock_run, "--unset-all")


def test_silent_clear_is_noop_when_local_value_is_canonical(tmp_path: Path) -> None:
    canonical_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    canonical_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(canonical_hooks_path) + "\n", returncode=0
        )
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            Path("."), CANONICAL_SUFFIX
        )
    assert not _was_called_with_argument(mock_run, "--unset-all")


def test_silent_clear_unsets_stale_worktree_seeded_local_value(tmp_path: Path) -> None:
    """Git seeds <repo>/.git/hooks into worktree-local config; preflight must heal it."""
    seeded_local_path_text = "/repo/.git/hooks"
    canonical_global_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    canonical_global_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_completed_process(seeded_local_path_text + "\n", returncode=0),
            _make_completed_process(
                str(canonical_global_hooks_path) + "\n", returncode=0
            ),
            _make_completed_process("", returncode=0),
        ]
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            Path("/repo"), CANONICAL_SUFFIX
        )
    assert _was_called_with_argument(mock_run, "--unset-all")
    assert _was_called_with_argument(mock_run, "--local")


def test_silent_clear_unsets_when_any_local_entry_is_non_canonical(
    tmp_path: Path,
) -> None:
    canonical_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    canonical_hooks_path.mkdir(parents=True)
    mixed_entries_text = f"{canonical_hooks_path}\n/some/other/path/.husky\n"
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_completed_process(mixed_entries_text, returncode=0),
            _make_completed_process(str(canonical_hooks_path) + "\n", returncode=0),
            _make_completed_process("", returncode=0),
        ]
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            Path("."), CANONICAL_SUFFIX
        )
    assert _was_called_with_argument(mock_run, "--unset-all")


def test_silent_clear_stands_down_when_global_is_unset() -> None:
    seeded_local_path_text = "/repo/.git/hooks"
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_completed_process(seeded_local_path_text + "\n", returncode=0),
            _make_completed_process("", returncode=1),
        ]
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            Path("/repo"), CANONICAL_SUFFIX
        )
    assert not _was_called_with_argument(mock_run, "--unset-all")


def test_silent_clear_stands_down_when_global_is_non_canonical() -> None:
    seeded_local_path_text = "/repo/.git/hooks"
    non_canonical_global_text = "/some/other/path/.husky"
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_completed_process(seeded_local_path_text + "\n", returncode=0),
            _make_completed_process(non_canonical_global_text + "\n", returncode=0),
        ]
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            Path("/repo"), CANONICAL_SUFFIX
        )
    assert not _was_called_with_argument(mock_run, "--unset-all")


def test_silent_clear_swallows_file_not_found_error() -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            Path("."), CANONICAL_SUFFIX
        )


def test_silent_clear_swallows_os_error() -> None:
    with patch("subprocess.run", side_effect=OSError("permission denied")):
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            Path("."), CANONICAL_SUFFIX
        )


def test_silent_clear_swallows_file_not_found_error_on_unset_call(tmp_path: Path) -> None:
    """A spawn-level FileNotFoundError on the unset-all write must not crash preflight."""
    seeded_local_path_text = "/repo/.git/hooks"
    canonical_global_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    canonical_global_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_completed_process(seeded_local_path_text + "\n", returncode=0),
            _make_completed_process(str(canonical_global_hooks_path) + "\n", returncode=0),
            FileNotFoundError(),
        ]
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            Path("/repo"), CANONICAL_SUFFIX
        )


def test_silent_clear_swallows_os_error_on_unset_call(tmp_path: Path) -> None:
    """A spawn-level OSError on the unset-all write must not crash preflight."""
    seeded_local_path_text = "/repo/.git/hooks"
    canonical_global_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    canonical_global_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_completed_process(seeded_local_path_text + "\n", returncode=0),
            _make_completed_process(str(canonical_global_hooks_path) + "\n", returncode=0),
            OSError("permission denied"),
        ]
        preflight_self_heal.silently_clear_stale_local_hooks_path_override(
            Path("/repo"), CANONICAL_SUFFIX
        )
