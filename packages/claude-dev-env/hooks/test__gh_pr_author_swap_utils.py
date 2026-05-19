"""Canonical-location tests for the gh-pr-author swap utils module.

The TDD enforcer matches a production filename ``X.py`` to ``test_X.py``;
``_gh_pr_author_swap_utils.py`` carries a leading underscore that the
enforcer treats as part of the name. This file's tests are the canonical
match. The broader behavioural suite lives alongside in
``blocking/test_gh_pr_author_swap_utils.py``.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import tempfile

import pytest

from config.gh_pr_author_swap_constants import STATE_FILE_PERMISSION_MODE

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

utils_module_spec = importlib.util.spec_from_file_location(
    "_gh_pr_author_swap_utils",
    _HOOKS_ROOT / "_gh_pr_author_swap_utils.py",
)
assert utils_module_spec is not None
assert utils_module_spec.loader is not None
utils_module = importlib.util.module_from_spec(utils_module_spec)
utils_module_spec.loader.exec_module(utils_module)


def test_state_file_path_rejects_path_traversal_session_id() -> None:
    """A session_id containing path-traversal characters must not escape tempdir.

    Regression guard: an unsanitised ``session_id`` containing ``../`` or
    ``/`` would interpolate into the filename and let the resulting path
    land outside ``tempfile.gettempdir()``. The sanitiser strips every
    character outside ``[A-Za-z0-9_-]`` and falls back to the default
    session id when the result is empty.
    """
    sanitised_path = utils_module._state_file_path("../../tmp/evil")
    temporary_directory_path = pathlib.Path(tempfile.gettempdir()).resolve()
    assert sanitised_path.parent.resolve() == temporary_directory_path


def test_state_file_path_rejects_backslash_in_session_id() -> None:
    """Backslashes are also unsafe path separators on Windows."""
    sanitised_path = utils_module._state_file_path("evil\\..\\..\\system32")
    temporary_directory_path = pathlib.Path(tempfile.gettempdir()).resolve()
    assert sanitised_path.parent.resolve() == temporary_directory_path


def test_state_file_path_rejects_nul_byte_in_session_id() -> None:
    """A NUL byte inside the session id must not reach the filename."""
    sanitised_path = utils_module._state_file_path("abc\x00../def")
    temporary_directory_path = pathlib.Path(tempfile.gettempdir()).resolve()
    assert sanitised_path.parent.resolve() == temporary_directory_path
    assert "\x00" not in sanitised_path.name


def test_state_file_path_preserves_safe_session_id() -> None:
    """A well-formed session id passes through unchanged."""
    safe_session_id = "session-001_abc"
    produced_path = utils_module._state_file_path(safe_session_id)
    assert safe_session_id in produced_path.name


def test_backtick_substitution_blanks_inner_quoted_literals() -> None:
    """A ``gh pr create`` literal inside a single-quoted argument of a backtick body must not trigger.

    Mirrors ``$(printf '...')`` behaviour: when the backtick body's
    quoted literal contains the token, the matcher must blank the
    quoted region before searching.
    """
    stripped_command = utils_module._strip_quoted_regions("foo `printf ';gh pr create'`")
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(stripped_command)


def test_backtick_substitution_matches_unquoted_gh_pr_create_inside_body() -> None:
    """A bare ``gh pr create`` inside a backtick body still matches.

    Symmetric to ``$(gh pr create)`` — the substitution body is real
    code, so the matcher must see it.
    """
    stripped_command = utils_module._strip_quoted_regions("echo `gh pr create --title T`")
    assert utils_module._command_invokes_gh_pr_create_in_stripped(stripped_command)


def test_state_file_is_attacker_planted_returns_true_for_world_readable_mode(
    tmp_path: pathlib.Path,
) -> None:
    """A state file with mode 0o644 is flagged as attacker-planted on POSIX.

    The enforcer always atomically creates state files at 0o600. A file
    at the predictable swap-state path with any other mode bits cannot
    have come from the enforcer running as this user.
    """
    if not hasattr(os, "getuid"):
        return
    state_file = tmp_path / "gh_pr_author_swap_session-attacker.json"
    state_file.write_text("{}", encoding="utf-8")
    os.chmod(state_file, 0o644)

    assert utils_module._state_file_is_attacker_planted(state_file) is True


def test_state_file_is_attacker_planted_returns_false_for_well_formed_file(
    tmp_path: pathlib.Path,
) -> None:
    """A state file written exactly the way the enforcer writes is not flagged."""
    state_file = tmp_path / "gh_pr_author_swap_session-good.json"
    state_file.write_text("{}", encoding="utf-8")
    if hasattr(os, "getuid"):
        os.chmod(state_file, STATE_FILE_PERMISSION_MODE)

    assert utils_module._state_file_is_attacker_planted(state_file) is False


def test_state_file_is_attacker_planted_returns_false_for_missing_file(
    tmp_path: pathlib.Path,
) -> None:
    """A missing state file is treated as not-planted so callers can no-op cleanly."""
    missing_state_file = tmp_path / "gh_pr_author_swap_session-missing.json"

    assert utils_module._state_file_is_attacker_planted(missing_state_file) is False


def test_state_file_is_attacker_planted_returns_true_for_non_regular_file(
    tmp_path: pathlib.Path,
) -> None:
    """A FIFO at the predictable swap-state path is flagged as attacker-planted.

    The enforcer only writes regular files; any non-regular file type
    (symlink, FIFO, device) at the predictable path indicates another
    party pre-created it to redirect the restore or cleanup hook.
    """
    if not hasattr(os, "mkfifo"):
        pytest.skip("mkfifo not available on this platform")
    if not hasattr(os, "getuid"):
        pytest.skip("POSIX ownership semantics not available on this platform")
    fifo_state_file = tmp_path / "gh_pr_author_swap_session-fifo.json"
    os.mkfifo(fifo_state_file, STATE_FILE_PERMISSION_MODE)

    assert utils_module._state_file_is_attacker_planted(fifo_state_file) is True


def test_state_file_is_attacker_planted_returns_true_when_lstat_raises_os_error(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ``OSError`` from ``lstat`` fails closed — the path is treated as planted.

    A path that exists but is unreadable (permission denied, broken
    filesystem mount, etc.) cannot be proven safe, so the helper
    returns True to keep the restore or cleanup hook from trusting it.
    """
    if not hasattr(os, "getuid"):
        pytest.skip("POSIX ownership semantics not available on this platform")
    unreadable_state_file = tmp_path / "gh_pr_author_swap_session-unreadable.json"
    unreadable_state_file.write_text("{}", encoding="utf-8")

    def raise_permission_error(self: pathlib.Path) -> os.stat_result:
        raise PermissionError("simulated lstat failure")

    monkeypatch.setattr(pathlib.Path, "lstat", raise_permission_error)

    assert utils_module._state_file_is_attacker_planted(unreadable_state_file) is True


def test_strip_bash_comments_preserves_substitution_body_when_hash_is_inside_dollar_paren() -> None:
    """Regression: ``$(date +%H # 24h) && gh pr create`` must not let the regex eat past the substitution closer.

    Before this fix ``_strip_bash_comments`` ran a flat regex sweep that
    blanked from ``#`` to end-of-line regardless of substitution depth.
    A ``#`` preceded by whitespace inside a ``$(...)`` body consumed
    the closing ``)`` AND every byte after it on the same line,
    erasing a real ``gh pr create`` invocation from the enforcer's
    view and silently bypassing the swap.
    """
    raw_command = "$(date +%H # 24h) && gh pr create --title T"
    preprocessed_command = utils_module._preprocess_command_for_matching(raw_command)
    assert "gh pr create" in preprocessed_command
    assert utils_module._command_invokes_gh_pr_create_in_stripped(preprocessed_command)


def test_strip_bash_comments_preserves_substitution_body_when_hash_is_inside_backtick() -> None:
    """Regression: a ``#`` inside a backtick body must not erase a trailing ``gh pr create``.

    Backtick substitution is symmetric with ``$(...)``; the
    substitution-aware comment walker must treat both shapes the same.
    """
    raw_command = "foo `cmd # comment` bar && gh pr create"
    preprocessed_command = utils_module._preprocess_command_for_matching(raw_command)
    assert "gh pr create" in preprocessed_command
    assert utils_module._command_invokes_gh_pr_create_in_stripped(preprocessed_command)


def test_strip_bash_comments_strips_top_level_trailing_comment() -> None:
    """Existing behaviour: a top-level trailing ``#`` comment after ``gh pr create`` is blanked.

    The comment-stripping pass must still erase a real top-level
    comment so the enforcer treats only the command portion as code.
    """
    raw_command = "gh pr create # this is a comment"
    preprocessed_command = utils_module._preprocess_command_for_matching(raw_command)
    assert "this is a comment" not in preprocessed_command


def test_strip_bash_comments_strips_prior_line_comment_only() -> None:
    """Existing behaviour: a comment on line 1 is blanked but a ``gh pr create`` on line 2 still matches.

    The newline is preserved so the matcher can still tell the two
    lines apart, and the second-line command stays intact.
    """
    raw_command = "echo a # b\ngh pr create"
    preprocessed_command = utils_module._preprocess_command_for_matching(raw_command)
    assert "gh pr create" in preprocessed_command
    assert "# b" not in preprocessed_command
    assert utils_module._command_invokes_gh_pr_create_in_stripped(preprocessed_command)


def test_lstat_indicates_attacker_planted_returns_false_for_well_formed_lstat(
    tmp_path: pathlib.Path,
) -> None:
    """A 0o600 regular file owned by the current user is not flagged.

    Mirrors ``test_state_file_is_attacker_planted_returns_false_for_well_formed_file``
    but feeds the helper a pre-computed ``lstat`` result so the helper
    does not perform its own syscall.
    """
    state_file = tmp_path / "gh_pr_author_swap_session-well_formed.json"
    state_file.write_text("{}", encoding="utf-8")
    if hasattr(os, "getuid"):
        os.chmod(state_file, STATE_FILE_PERMISSION_MODE)

    file_lstat_result = state_file.lstat()

    assert utils_module._lstat_indicates_attacker_planted(file_lstat_result) is False


def test_lstat_indicates_attacker_planted_returns_true_for_world_readable_mode(
    tmp_path: pathlib.Path,
) -> None:
    """A 0o644 regular file is flagged as attacker-planted on POSIX.

    The enforcer always creates state files at 0o600, so a divergent
    mode is treated as a plant.
    """
    if not hasattr(os, "getuid"):
        pytest.skip("POSIX ownership semantics not available on this platform")
    state_file = tmp_path / "gh_pr_author_swap_session-mode_wrong.json"
    state_file.write_text("{}", encoding="utf-8")
    os.chmod(state_file, 0o644)

    file_lstat_result = state_file.lstat()

    assert utils_module._lstat_indicates_attacker_planted(file_lstat_result) is True


def test_lstat_indicates_attacker_planted_returns_true_for_foreign_uid(
    tmp_path: pathlib.Path,
) -> None:
    """A regular 0o600 file owned by a different uid is flagged on POSIX.

    The helper sees only the ``stat_result`` it is given, so the test
    builds a synthetic ``os.stat_result`` whose ``st_uid`` does not match
    ``os.getuid()`` and feeds it directly to the helper.
    """
    if not hasattr(os, "getuid"):
        pytest.skip("POSIX ownership semantics not available on this platform")
    state_file = tmp_path / "gh_pr_author_swap_session-foreign_uid.json"
    state_file.write_text("{}", encoding="utf-8")
    os.chmod(state_file, STATE_FILE_PERMISSION_MODE)
    real_lstat_result = state_file.lstat()
    foreign_user_id = os.getuid() + 1
    synthetic_stat_fields = (
        real_lstat_result.st_mode,
        real_lstat_result.st_ino,
        real_lstat_result.st_dev,
        real_lstat_result.st_nlink,
        foreign_user_id,
        real_lstat_result.st_gid,
        real_lstat_result.st_size,
        real_lstat_result.st_atime,
        real_lstat_result.st_mtime,
        real_lstat_result.st_ctime,
    )
    synthetic_stat_result = os.stat_result(synthetic_stat_fields)

    assert utils_module._lstat_indicates_attacker_planted(synthetic_stat_result) is True


def test_lstat_indicates_attacker_planted_returns_true_for_non_regular_file(
    tmp_path: pathlib.Path,
) -> None:
    """A FIFO at the predictable swap-state path is flagged.

    Mirrors ``test_state_file_is_attacker_planted_returns_true_for_non_regular_file``
    but feeds the helper the FIFO's own ``lstat`` result rather than the
    path.
    """
    if not hasattr(os, "mkfifo"):
        pytest.skip("mkfifo not available on this platform")
    if not hasattr(os, "getuid"):
        pytest.skip("POSIX ownership semantics not available on this platform")
    fifo_state_file = tmp_path / "gh_pr_author_swap_session-fifo.json"
    os.mkfifo(fifo_state_file, STATE_FILE_PERMISSION_MODE)

    file_lstat_result = fifo_state_file.lstat()

    assert utils_module._lstat_indicates_attacker_planted(file_lstat_result) is True


def test_lstat_indicates_attacker_planted_returns_false_on_windows(
    tmp_path: pathlib.Path,
) -> None:
    """On Windows (no ``os.getuid``) the helper short-circuits to False.

    Windows tempdir is already per-user, so the cross-user attack
    surface this check guards against on POSIX does not exist there.
    """
    if hasattr(os, "getuid"):
        pytest.skip("POSIX has os.getuid; this case asserts Windows-only behaviour")
    state_file = tmp_path / "gh_pr_author_swap_session-windows.json"
    state_file.write_text("{}", encoding="utf-8")

    file_lstat_result = state_file.lstat()

    assert utils_module._lstat_indicates_attacker_planted(file_lstat_result) is False
