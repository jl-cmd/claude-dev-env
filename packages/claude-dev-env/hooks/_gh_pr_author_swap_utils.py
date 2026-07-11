"""Shared utilities for the gh-pr-author swap hook trio.

The PreToolUse enforcer (``hooks/blocking/gh_pr_author_enforcer.py``), the
PostToolUse restore (``hooks/blocking/gh_pr_author_restore.py``), and the
SessionStart cleanup (``hooks/session/gh_pr_author_session_cleanup.py``)
all share a small set of helpers: write a line to a stream, build the
per-session state-file path, run ``gh auth switch``, read the
original-account login from a state file, delete a state file, and
detect a ``gh pr create`` invocation while ignoring quoted regions.

Centralising these helpers keeps the three hooks' contracts in
lock-step — a fix in the shared ``_command_invokes_gh_pr_create_in_stripped``
detector lands in the enforcer and the restore hook from a single edit,
and the state-file path and gh subprocess shape stay uniform across the
trio so a file written by the enforcer is always resolvable by the
restore and cleanup hooks.

Layout: a leading underscore marks the module as internal to the swap
feature, and the file lives directly under ``hooks/`` so both
``hooks/blocking/`` and ``hooks/session/`` consumers can import it
without a per-directory path shim.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TextIO

from hooks_constants.gh_pr_author_swap_constants import (
    ALL_GH_AUTH_SWITCH_COMMAND_HEAD,
    ALL_SHELL_QUOTE_CHARACTERS,
    BASH_COMMENT_INTRODUCER_CHARACTER,
    COMMAND_SEPARATOR_PATTERN,
    COMMAND_SUBSTITUTION_OPENER_LENGTH,
    GH_AUTH_SWITCH_TIMEOUT_SECONDS,
    GH_PR_CREATE_PATTERN,
    HEREDOC_OPENER_TAG_PATTERN,
    HEREDOC_OPENER_TOKEN_LENGTH,
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
    SHELL_BACKSLASH_CHARACTER,
    SHELL_BACKSLASH_ESCAPE_PAIR_LENGTH,
    SHELL_BACKTICK_CHARACTER,
    SHELL_DOLLAR_CHARACTER,
    SHELL_LESS_THAN_CHARACTER,
    SHELL_NEWLINE_CHARACTER,
    SHELL_PAREN_CLOSE_CHARACTER,
    SHELL_PAREN_OPEN_CHARACTER,
    SHELL_QUOTE_REPLACEMENT_CHARACTER,
    STATE_FILE_DEFAULT_SESSION_ID,
    STATE_FILE_ORIGINAL_ACCOUNT_KEY,
    STATE_FILE_PERMISSION_MODE,
    STATE_FILE_PREFIX,
    STATE_FILE_SUFFIX,
)


def _write_line(message: str, into_stream: TextIO) -> None:
    """Write a single line to the caller-provided text stream.

    Wrapping ``stream.write`` in a function that accepts an explicit
    ``into_stream`` parameter satisfies the project's logging rule
    (route through logger or accept an explicit stream parameter) without
    pulling the logging module into a self-contained hook script.

    Args:
        message: Single line of output. A trailing newline is appended.
        into_stream: Destination stream (typically ``sys.stdout`` for
            the JSON deny payload or ``sys.stderr`` for diagnostics).
            Each caller formats its own prefix into ``message``.
    """
    into_stream.write(message + "\n")
    into_stream.flush()


def _sanitize_session_id(session_id: str) -> str:
    """Strip every character outside ``[A-Za-z0-9_-]`` from a session id.

    The raw session id comes from the Claude Code hook input JSON, which
    is attacker-influenceable. Path-traversal characters (``/``, ``\\``,
    ``..``), NUL bytes, and any other shell-metacharacter must be removed
    before the value participates in a filename so the produced path
    stays anchored inside ``tempfile.gettempdir()``.

    Args:
        session_id: Raw session id value.

    Returns:
        The input with every unsafe character removed. An empty result
        signals the caller to fall back to the default session id.
    """
    return SESSION_ID_UNSAFE_CHARACTERS_PATTERN.sub("", session_id)


def _state_file_path(session_id: str) -> Path:
    """Return the per-session state-file path used by the hook trio.

    The enforcer writes the file, the restore hook reads and deletes it,
    and the session-cleanup hook globs the prefix to recover stranded
    files. All three share this naming convention so a state file
    written by one hook is always resolvable by the others.

    Args:
        session_id: ``session_id`` from the Claude Code hook input JSON.
            Empty string falls back to ``STATE_FILE_DEFAULT_SESSION_ID``.
            Unsafe characters (path-traversal, NUL, shell metacharacters)
            are stripped before the value participates in the filename so
            the returned path stays anchored inside the temp directory.

    Returns:
        Absolute path to the state file in the system temp directory.
    """
    sanitized_session_id = _sanitize_session_id(session_id)
    effective_session_id = sanitized_session_id or STATE_FILE_DEFAULT_SESSION_ID
    filename = f"{STATE_FILE_PREFIX}{effective_session_id}{STATE_FILE_SUFFIX}"
    return Path(tempfile.gettempdir()) / filename


def _switch_gh_account(to_account: str) -> bool:
    """Run ``gh auth switch --user <to_account>`` and report success.

    Diagnostics on failure are intentionally not written here. Callers
    decide whether a failed switch is worth a stderr line (the restore
    and cleanup hooks log; the enforcer suppresses to keep the deny-path
    payload the only output on the failure branch).

    Args:
        to_account: Login to switch the active gh CLI account to.

    Returns:
        True when the switch command exits zero. False when gh is missing,
        the switch command exits non-zero, times out, lacks executable
        permission on the gh binary, or otherwise fails. ``OSError``
        covers every spawn-time failure (``FileNotFoundError`` when gh is
        absent, ``PermissionError`` when gh exists but is not executable,
        and any other platform-specific spawn errors) so the hook follows
        its documented non-blocking failure path rather than crashing.
    """
    switch_command = list(ALL_GH_AUTH_SWITCH_COMMAND_HEAD) + [to_account]
    try:
        completed_process = subprocess.run(
            switch_command,
            capture_output=True,
            text=True,
            timeout=GH_AUTH_SWITCH_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed_process.returncode == 0


def _read_original_account(state_file: Path) -> str | None:
    """Read the original-account login from a swap-state file.

    Args:
        state_file: Path produced by ``_state_file_path``.

    Returns:
        The original account login when the file exists and parses to a
        JSON object with a non-empty string ``original_account`` value.
        None when the file is absent, unreadable, malformed JSON, the
        wrong shape, missing the key, holds a non-string value, or holds
        a blank value. Diagnostics for unreadable or malformed files are
        written to stderr so the caller can see why a state file was not
        consumed.
    """
    try:
        raw_contents = state_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as os_error:
        _write_line(
            f"[gh-pr-author-utils] failed to read state file {state_file}: {os_error}",
            sys.stderr,
        )
        return None
    try:
        parsed_state = json.loads(raw_contents)
    except json.JSONDecodeError as decode_error:
        _write_line(
            f"[gh-pr-author-utils] malformed state file {state_file}: {decode_error}",
            sys.stderr,
        )
        return None
    if not isinstance(parsed_state, dict):
        return None
    original_account = parsed_state.get(STATE_FILE_ORIGINAL_ACCOUNT_KEY, "")
    if not isinstance(original_account, str):
        return None
    stripped_original_account = original_account.strip()
    return stripped_original_account or None


def _delete_state_file(state_file: Path) -> None:
    """Remove a state file, ignoring an already-absent file.

    Args:
        state_file: Path produced by ``_state_file_path``.
    """
    try:
        state_file.unlink()
    except FileNotFoundError:
        return
    except OSError as os_error:
        _write_line(
            f"[gh-pr-author-utils] failed to delete state file {state_file}: {os_error}",
            sys.stderr,
        )


def _state_file_is_attacker_planted(state_file: Path) -> bool:
    """Return True when the state file's mode or owner does not match an enforcer-written file.

    The enforcer atomically creates each swap-state file with mode
    ``STATE_FILE_PERMISSION_MODE`` (``0o600``) owned by the current
    user. A file at the predictable swap-state path that diverges on
    either axis is overwhelmingly likely to be an attacker plant —
    another user on the same workstation pre-creating a file to trick
    the restore or cleanup hook into running
    ``gh auth switch --user <attacker-controlled-login>``.

    The candidate is inspected via ``lstat`` rather than ``stat`` so a
    symlink at the predictable path is screened on its own metadata,
    not on whatever the symlink resolves to. The enforcer creates state
    files with ``O_NOFOLLOW`` to prevent symlink hijacking; this helper
    mirrors that contract.

    The mode-bit and uid checks only apply on POSIX. Windows reports
    ``0o666`` from ``stat`` for files chmod'd to ``0o600`` because
    ``os.chmod`` on Windows only toggles the read-only attribute, and
    ``os.getuid`` is absent there. ``tempfile.gettempdir()`` on Windows
    is already per-user (``%LOCALAPPDATA%\\Temp``), which closes the
    cross-user attack surface this check guards against on POSIX, so
    the check is a no-op on Windows.

    A missing file returns False so callers can treat the missing-file
    case the same way they treat a normal absent-state-file path.

    For callers that already hold an ``lstat`` result for the candidate
    path, prefer ``_lstat_indicates_attacker_planted`` to avoid a
    redundant syscall and the TOCTOU window between two ``lstat`` calls.

    Args:
        state_file: Path produced by ``_state_file_path``.

    Returns:
        True when the file exists on POSIX with wrong mode bits or
        wrong uid, or the path is not a regular file (symlink, FIFO,
        device, etc.), or ``os.lstat`` raises ``OSError``. False when
        the file matches the enforcer's write contract, is absent, or
        the platform lacks POSIX ownership semantics.
    """
    if not hasattr(os, "getuid"):
        return False
    try:
        file_lstat_result = state_file.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return _lstat_indicates_attacker_planted(file_lstat_result)


def _lstat_indicates_attacker_planted(file_lstat_result: os.stat_result) -> bool:
    """Return True when an ``lstat`` result does not match an enforcer-written state file.

    Callers that already hold a fresh ``lstat`` result for a candidate
    state-file path use this helper directly instead of
    ``_state_file_is_attacker_planted``, which would re-stat the path.
    Skipping the second stat avoids a redundant syscall and the TOCTOU
    window where an attacker could swap the inode between the two stat
    calls.

    The mode-bit and uid checks only apply on POSIX. Windows ``stat``
    semantics differ (see ``_state_file_is_attacker_planted`` for the
    full rationale) so the helper is a no-op on platforms without
    ``os.getuid``.

    Args:
        file_lstat_result: Result of ``os.lstat`` (or ``Path.lstat``)
            on the candidate state-file path. The caller is responsible
            for using ``lstat`` rather than ``stat`` so symlinks are
            screened on their own metadata.

    Returns:
        True on POSIX when the file is not a regular file, the mode
        bits do not equal ``STATE_FILE_PERMISSION_MODE``, or the uid
        does not match the current user. False on POSIX when the
        candidate matches the enforcer's write contract, and on Windows
        unconditionally.
    """
    if not hasattr(os, "getuid"):
        return False
    if not stat.S_ISREG(file_lstat_result.st_mode):
        return True
    actual_permission_bits = stat.S_IMODE(file_lstat_result.st_mode)
    if actual_permission_bits != STATE_FILE_PERMISSION_MODE:
        return True
    current_user_id = os.getuid()
    if file_lstat_result.st_uid != current_user_id:
        return True
    return False


def _index_after_command_substitution(all_scanned_characters: list[str], opener_index: int) -> int:
    """Return the index one past the closing ``)`` of a ``$(...)`` substitution.

    Walks from the opening ``$(`` past nested ``$(...)`` substitutions
    and through inner quoted regions and backtick substitutions so the
    closing paren matched is the one that actually balances the opener.
    Bash executes the substitution body as its own command, so the
    walker treats the body the same way the outer ``_strip_quoted_regions``
    scan treats top-level text: single- and double-quoted regions inside
    the body are BLANKED (replaced with spaces) so a literal token
    sitting inside a quoted argument cannot leak out as if it were a
    command. For example, ``$(printf 'gh pr create')`` runs ``printf``
    against the literal data ``gh pr create`` — the data must not be
    confused with a real ``gh pr create`` invocation.

    Quote handling mirrors ``_strip_quoted_regions``:

    * A single-quoted region (``'...'``) has no escape mechanism in bash —
      the walker advances to the next ``'`` and blanks every character
      between the openers.
    * A double-quoted region (``"..."``) honors backslash escapes — a
      ``\\`` followed by any character is consumed as a two-character
      unit, so ``\\"`` does not terminate the region. Backslash-escape
      pairs are blanked too.
    * A backtick substitution (``` `...` ```) inside the ``$(...)`` body
      is itself a subshell — the walker advances past the next backtick
      so that a ``)`` sitting inside the backtick body does not flip the
      surrounding paren depth. Backtick bodies are kept scannable for
      the same reason as ``$(...)`` bodies: bash executes them, so any
      ``gh pr create`` token sitting inside is a real invocation.

    Bare ``(`` and ``)`` characters inside the substitution body
    (bash subshells like ``(echo b)``, array assignments like
    ``arr=(a b c)``, function definitions like ``f() { ...; }``) also
    track paren depth so they cancel out before a bare ``)`` can
    prematurely close the outer ``$(...)`` substitution.

    Unterminated quotes and backticks consume to the end of the buffer,
    matching the behavior of ``_strip_quoted_regions``.

    Args:
        all_scanned_characters: Mutable list view of the command string.
            The walker MUTATES the buffer to blank quoted regions inside
            the substitution body. The substitution opener (``$(``) and
            closer (``)``) and any unquoted body characters remain
            intact so the outer matcher can scan the body for real
            commands.
        opener_index: Index of the ``$`` that begins ``$(``.

    Returns:
        The index just past the matching ``)``. When no closing paren is
        found the length of the buffer is returned, matching how an
        interactive shell would consume the rest of the input on an
        unterminated substitution.
    """
    paren_depth = 1
    interior_index = opener_index + COMMAND_SUBSTITUTION_OPENER_LENGTH
    buffer_length = len(all_scanned_characters)
    while interior_index < buffer_length and paren_depth > 0:
        interior_character = all_scanned_characters[interior_index]
        if (
            interior_character == SHELL_DOLLAR_CHARACTER
            and interior_index + 1 < buffer_length
            and all_scanned_characters[interior_index + 1] == SHELL_PAREN_OPEN_CHARACTER
        ):
            paren_depth += 1
            interior_index += COMMAND_SUBSTITUTION_OPENER_LENGTH
            continue
        if interior_character == SHELL_BACKTICK_CHARACTER:
            interior_index = _index_after_backtick_substitution(
                all_scanned_characters, interior_index, buffer_length
            )
            continue
        if interior_character in ALL_SHELL_QUOTE_CHARACTERS:
            interior_index = _blank_quoted_region(
                all_scanned_characters, interior_index, buffer_length, interior_character
            )
            continue
        if interior_character == SHELL_PAREN_OPEN_CHARACTER:
            paren_depth += 1
            interior_index += 1
            continue
        if interior_character == SHELL_PAREN_CLOSE_CHARACTER:
            paren_depth -= 1
            interior_index += 1
            continue
        interior_index += 1
    return interior_index


def _index_after_backtick_substitution(
    all_scanned_characters: list[str],
    opener_index: int,
    buffer_length: int,
) -> int:
    """Return the index one past the closing backtick of a ``` `...` ``` region.

    The backtick body is executed by bash, so the walker mirrors the
    ``$(...)`` helper: a single- or double-quoted region inside the
    body is blanked via ``_blank_quoted_region`` so a literal token
    sitting inside a quoted argument (for example
    ``` `printf ';gh pr create'` ```) cannot leak out as if it were a
    real command.

    Args:
        all_scanned_characters: Mutable list view of the command string.
            The walker MUTATES the buffer to blank quoted regions inside
            the substitution body.
        opener_index: Index of the opening backtick.
        buffer_length: Length of ``all_scanned_characters``, hoisted by
            the caller to avoid a recomputation per call.

    Returns:
        The index just past the matching backtick, or ``buffer_length``
        when the backtick region is unterminated.
    """
    interior_index = opener_index + 1
    while interior_index < buffer_length:
        interior_character = all_scanned_characters[interior_index]
        if interior_character == SHELL_BACKTICK_CHARACTER:
            return interior_index + 1
        if interior_character in ALL_SHELL_QUOTE_CHARACTERS:
            interior_index = _blank_quoted_region(
                all_scanned_characters, interior_index, buffer_length, interior_character
            )
            continue
        interior_index += 1
    return interior_index


def _blank_quoted_region(
    all_scanned_characters: list[str],
    opener_index: int,
    buffer_length: int,
    quote_character: str,
) -> int:
    """Blank the interior of a ``'...'`` or ``"..."`` region in place.

    The opening quote, every character inside the region, and the closing
    quote are all replaced with ``SHELL_QUOTE_REPLACEMENT_CHARACTER`` so
    that downstream regex matching sees only whitespace where quoted text
    used to live. Offsets are preserved end-to-end — the returned index
    always lands one past the position the closing quote occupied
    (whether or not a closing quote was found).

    Single quotes have no escape mechanism in bash, so the walker advances
    to the next matching ``'`` and blanks every character along the way.
    Double quotes honor ``\\`` escapes, so a ``\\`` followed by any
    character is blanked as a two-character unit (``\\"`` does not
    terminate the region).

    Within a double-quoted region, bash still expands ``$(...)`` and
    ``` `...` ``` substitutions. The walker recognizes both openers and
    descends into their matching closer via the substitution helpers
    instead of blanking, so a ``gh pr create`` token sitting inside the
    substitution body remains scannable while the surrounding quoted
    text is blanked. Single-quoted regions intentionally do NOT descend
    into substitutions because ``$`` and ``` ` ``` are literal text
    inside ``'...'``.

    Args:
        all_scanned_characters: Mutable list view of the command string.
            The walker MUTATES the buffer to blank the entire quoted
            region (both quotes included).
        opener_index: Index of the opening quote.
        buffer_length: Length of ``all_scanned_characters``, hoisted by
            the caller to avoid a recomputation per call.
        quote_character: ``'`` or ``"`` — the quote whose match closes
            the region.

    Returns:
        The index just past the matching closing quote, or ``buffer_length``
        when the quoted region is unterminated.
    """
    all_scanned_characters[opener_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
    interior_index = opener_index + 1
    while interior_index < buffer_length:
        interior_character = all_scanned_characters[interior_index]
        if (
            quote_character == '"'
            and interior_character == "\\"
            and interior_index + 1 < buffer_length
        ):
            all_scanned_characters[interior_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
            all_scanned_characters[interior_index + 1] = SHELL_QUOTE_REPLACEMENT_CHARACTER
            interior_index += SHELL_BACKSLASH_ESCAPE_PAIR_LENGTH
            continue
        if (
            quote_character == '"'
            and interior_character == SHELL_DOLLAR_CHARACTER
            and interior_index + 1 < buffer_length
            and all_scanned_characters[interior_index + 1] == SHELL_PAREN_OPEN_CHARACTER
        ):
            interior_index = _index_after_command_substitution(
                all_scanned_characters, interior_index
            )
            continue
        if quote_character == '"' and interior_character == SHELL_BACKTICK_CHARACTER:
            interior_index = _index_after_backtick_substitution(
                all_scanned_characters, interior_index, buffer_length
            )
            continue
        if interior_character == quote_character:
            all_scanned_characters[interior_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
            return interior_index + 1
        all_scanned_characters[interior_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
        interior_index += 1
    return interior_index


def _strip_quoted_regions(command: str) -> str:
    """Replace inert quoted regions with spaces, leaving substitutions scannable.

    Single quotes (``'...'``) and double quotes (``"..."``) wrap inert
    text in bash, so their interior is replaced with spaces. ``$(...)``
    command substitution and backtick command substitution
    (``` `...` ```) execute their bodies in a subshell, so the substitution
    OPENER and CLOSER and the unquoted body characters are left intact —
    any ``gh pr create`` token sitting unquoted inside either form must
    remain visible to the matchers, otherwise the enforcer would
    silently no-op on ``echo "$(gh pr create --title T)"``.

    The substitution bodies themselves are recursively quote-stripped:
    a single- or double-quoted argument INSIDE a substitution body is
    blanked the same way as a top-level quoted region. That keeps shapes
    like ``echo $(printf 'gh pr create')`` from leaking the literal
    ``gh pr create`` string out of ``printf``'s single-quoted argument
    and tricking the matcher into thinking the substitution invokes
    ``gh pr create`` when it actually invokes ``printf`` against the
    literal data.

    Within a double-quoted region, ``$(...)`` substitution windows are
    still expanded, so the walker recognizes the ``$(`` opener inside
    the quoted scan and stops stripping until the matching ``)`` —
    leaving the substitution body scannable while keeping the surrounding
    quoted text inert. Backtick command substitution (``` `...` ```) is
    likewise expanded by bash inside double quotes, so the same
    skip-past-body behavior applies: the walker advances past the closing
    backtick without stripping the interior, so any ``gh pr create`` token
    sitting inside ``"`...`"`` remains visible to the matcher.

    Backslash-escaped quotes inside a double-quoted segment (``\\"``) do
    not terminate the region. An unterminated quote consumes the rest of
    the string, matching how an interactive shell parses the same input.

    Args:
        command: Raw bash command string from PreToolUse hook input.

    Returns:
        A string of identical length to ``command`` with single- and
        double-quoted region interiors replaced by spaces — including
        quoted regions nested inside ``$(...)`` / ``` `...` ``` bodies —
        and the unquoted body characters of the substitutions themselves
        left intact.
    """
    all_scanned_characters = list(command)
    cursor_index = 0
    command_length = len(command)
    while cursor_index < command_length:
        current_character = all_scanned_characters[cursor_index]
        if (
            current_character == SHELL_DOLLAR_CHARACTER
            and cursor_index + 1 < command_length
            and all_scanned_characters[cursor_index + 1] == SHELL_PAREN_OPEN_CHARACTER
        ):
            cursor_index = _index_after_command_substitution(all_scanned_characters, cursor_index)
            continue
        if current_character == SHELL_BACKTICK_CHARACTER:
            cursor_index = _index_after_backtick_substitution(
                all_scanned_characters, cursor_index, command_length
            )
            continue
        if current_character not in ALL_SHELL_QUOTE_CHARACTERS:
            cursor_index += 1
            continue
        cursor_index = _blank_quoted_region(
            all_scanned_characters, cursor_index, command_length, current_character
        )
    return "".join(all_scanned_characters)


def _strip_bash_comments(quote_stripped_command: str) -> str:
    """Replace bash comments with spaces so a hash-prefixed token is inert.

    Bash treats a hash character as the start of a comment only when it
    appears at the beginning of the command or immediately after
    whitespace. Inside a quoted region the hash character is literal,
    but the caller is responsible for running ``_strip_quoted_regions``
    first, which already blanks quoted text, so any hash character
    reaching this helper is either a real comment introducer or a
    token-internal character (for example
    ``--body-file body.md@@HASH@@fragment`` where ``@@HASH@@`` stands
    in for the literal hash byte).

    The walker is substitution-aware: it descends INTO ``$(...)`` and
    ``` `...` ``` bodies so a hash character inside a substitution
    body is processed as a comment too — bash executes the substitution
    body as its own command, so a hash after whitespace inside the
    body really does start a comment. The substitution-bounded comment
    runs to the next newline OR to the substitution closer (``)`` for
    ``$(...)``, backtick for ``` `...` ```), whichever comes first.
    The substitution OPENER and CLOSER characters themselves are
    preserved so the outer paren-depth tracking remains intact and the
    surrounding command structure stays scannable.

    A hash character at the top level (outside every substitution)
    consumes until the next newline as usual. A comment inside a
    substitution body must NOT escape outward — that is why the closer
    bounds the consumption. Without that bound, a flat regex sweep
    would consume the closing ``)`` or backtick and every byte after
    it on the same line, silently erasing a real ``gh pr create``
    invocation that follows the substitution.

    Args:
        quote_stripped_command: Output of ``_strip_quoted_regions``.

    Returns:
        A string of identical length with every bash comment replaced
        by spaces. The trailing newline of each commented line is
        retained so the matcher can still tell where one command ended
        and the next began. Substitution openers and closers stay
        intact.
    """
    all_scanned_characters = list(quote_stripped_command)
    command_length = len(quote_stripped_command)
    _walk_and_blank_comments(
        all_scanned_characters,
        cursor_start_index=0,
        end_index=command_length,
        bounded_by_substitution_closer=None,
    )
    return "".join(all_scanned_characters)


def _walk_and_blank_comments(
    all_scanned_characters: list[str],
    cursor_start_index: int,
    end_index: int,
    bounded_by_substitution_closer: str | None,
) -> int:
    """Walk a region of the character buffer and blank every comment found.

    The walker is recursive over substitution bodies: when it encounters
    a ``$(...)`` or ``` `...` ``` opener it descends into the body with
    a substitution closer in hand, blanks any comment that appears
    inside the body, and returns control to the outer caller once the
    closer is consumed. The substitution opener and closer characters
    themselves are preserved so paren-depth tracking elsewhere
    (``_index_after_command_substitution``,
    ``_strip_substitution_bodies``) remains correct on the blanked
    string.

    Args:
        all_scanned_characters: Mutable list view of the command string.
            The walker MUTATES the buffer to blank comment text in place.
        cursor_start_index: Index at which to begin scanning.
        end_index: Index at which to stop scanning. The caller passes
            ``len(all_scanned_characters)`` for the top-level walk and
            the same value for substitution-body walks (each recursive
            call independently checks for its closer).
        bounded_by_substitution_closer: ``None`` for the top-level
            walk. ``")"`` when walking inside a ``$(...)`` body so a
            comment inside the body terminates at the matching ``)``.
            When bounded by ``)``, paren depth is tracked so a bare
            ``(`` inside the body matches its own bare ``)`` rather
            than letting that ``)`` exit the walker prematurely.
            ``"`"`` when walking inside a ``` `...` ``` body so a
            comment inside the body terminates at the matching
            backtick. Backtick bodies do not need depth tracking
            because backticks do not nest in unescaped form.

    Returns:
        The index just past the substitution closer when bounded, or
        ``end_index`` when the walker reaches the end of the buffer.
    """
    cursor_index = cursor_start_index
    paren_depth = (
        1 if bounded_by_substitution_closer == SHELL_PAREN_CLOSE_CHARACTER else 0
    )
    while cursor_index < end_index:
        current_character = all_scanned_characters[cursor_index]
        if (
            bounded_by_substitution_closer == SHELL_PAREN_CLOSE_CHARACTER
            and current_character == SHELL_PAREN_CLOSE_CHARACTER
        ):
            paren_depth -= 1
            if paren_depth == 0:
                return cursor_index + 1
            cursor_index += 1
            continue
        if (
            bounded_by_substitution_closer == SHELL_BACKTICK_CHARACTER
            and current_character == SHELL_BACKTICK_CHARACTER
        ):
            return cursor_index + 1
        if (
            current_character == SHELL_DOLLAR_CHARACTER
            and cursor_index + 1 < end_index
            and all_scanned_characters[cursor_index + 1] == SHELL_PAREN_OPEN_CHARACTER
        ):
            cursor_index = _walk_and_blank_comments(
                all_scanned_characters,
                cursor_start_index=cursor_index + COMMAND_SUBSTITUTION_OPENER_LENGTH,
                end_index=end_index,
                bounded_by_substitution_closer=SHELL_PAREN_CLOSE_CHARACTER,
            )
            continue
        if current_character == SHELL_BACKTICK_CHARACTER:
            cursor_index = _walk_and_blank_comments(
                all_scanned_characters,
                cursor_start_index=cursor_index + 1,
                end_index=end_index,
                bounded_by_substitution_closer=SHELL_BACKTICK_CHARACTER,
            )
            continue
        if (
            bounded_by_substitution_closer == SHELL_PAREN_CLOSE_CHARACTER
            and current_character == SHELL_PAREN_OPEN_CHARACTER
        ):
            paren_depth += 1
            cursor_index += 1
            continue
        if (
            current_character == BASH_COMMENT_INTRODUCER_CHARACTER
            and _is_comment_introducer_position(all_scanned_characters, cursor_index)
        ):
            cursor_index = _blank_bounded_comment(
                all_scanned_characters,
                cursor_index,
                end_index,
                bounded_by_substitution_closer,
            )
            continue
        cursor_index += 1
    return cursor_index


def _blank_bounded_comment(
    all_scanned_characters: list[str],
    hash_index: int,
    end_index: int,
    bounded_by_substitution_closer: str | None,
) -> int:
    """Blank a comment in place up to a newline or substitution closer.

    A comment at the top level runs from the hash character to the next
    newline. A comment inside a substitution body has the same upper
    bound but ALSO terminates at the substitution closer (``)`` or
    backtick), so the closer character itself is preserved and the
    outer walker can continue from there.

    Args:
        all_scanned_characters: Mutable list view of the command string.
            The walker MUTATES the buffer to blank the comment body.
        hash_index: Index of the hash character that introduces the
            comment.
        end_index: Buffer length, hoisted by the caller to avoid a
            recomputation per call.
        bounded_by_substitution_closer: ``None`` for the top-level
            walk. ``")"`` when inside a ``$(...)`` body. ``"`"`` when
            inside a ``` `...` ``` body.

    Returns:
        The cursor position the outer walker should resume from. The
        preserved terminating newline (when present) is included in
        the returned range so command-separator detection still sees
        the line break. When the comment terminates at a substitution
        closer, the closer's own index is returned so the recursive
        caller picks up the closer on its next iteration.
    """
    blanking_index = hash_index
    while blanking_index < end_index:
        current_character = all_scanned_characters[blanking_index]
        if current_character == "\n":
            return blanking_index
        if (
            bounded_by_substitution_closer == SHELL_PAREN_CLOSE_CHARACTER
            and current_character == SHELL_PAREN_CLOSE_CHARACTER
        ):
            return blanking_index
        if (
            bounded_by_substitution_closer == SHELL_BACKTICK_CHARACTER
            and current_character == SHELL_BACKTICK_CHARACTER
        ):
            return blanking_index
        all_scanned_characters[blanking_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
        blanking_index += 1
    return blanking_index


def _is_comment_introducer_position(
    all_scanned_characters: list[str], hash_index: int
) -> bool:
    """Return True when the hash at ``hash_index`` introduces a bash comment.

    Bash treats a hash as a comment introducer only at the start of the
    command or immediately after whitespace. This mirrors the lookbehind
    branch of the bash comment rule (``(?<=\\s)|^``) while operating on
    a mutable character list so the substitution-aware walker can
    consult it inline.

    Args:
        all_scanned_characters: Character buffer being walked.
        hash_index: Index of the hash character under test.

    Returns:
        True when ``hash_index`` is zero or the prior character is a
        Python ``str.isspace`` whitespace character.
    """
    if hash_index == 0:
        return True
    prior_character = all_scanned_characters[hash_index - 1]
    return prior_character.isspace()


def _strip_substitution_bodies(quote_stripped_command: str) -> str:
    """Replace ``$(...)`` and ``` `...` ``` bodies with spaces.

    The ``gh pr create`` detection path relies on the substitution body
    being scannable so that ``echo $(gh pr create)`` triggers the
    enforcer. The web-flag detection path has the opposite requirement:
    a ``--web`` token appearing inside a substitution body is an
    argument to whatever command the subshell executes, not a flag on
    the outer ``gh pr create`` invocation. ``gh pr create --title "$(echo --web)"``
    should still trip the enforcer because ``--web`` belongs to ``echo``,
    not to ``gh pr create``.

    This helper blanks the OPENER, the body, and the CLOSER of every
    top-level ``$(...)`` and ``` `...` ``` substitution so the
    web-flag matcher sees only whitespace where a substitution used to
    live. Offsets are preserved so the segment-extraction in
    ``_all_gh_pr_create_segments`` still works on the resulting string.

    Args:
        quote_stripped_command: Output of ``_strip_quoted_regions`` —
            quotes must already be blanked so this helper does not need
            to re-track quoted boundaries.

    Returns:
        A string of identical length with every substitution body
        replaced by spaces.
    """
    all_scanned_characters = list(quote_stripped_command)
    cursor_index = 0
    command_length = len(quote_stripped_command)
    while cursor_index < command_length:
        current_character = all_scanned_characters[cursor_index]
        if (
            current_character == SHELL_DOLLAR_CHARACTER
            and cursor_index + 1 < command_length
            and all_scanned_characters[cursor_index + 1] == SHELL_PAREN_OPEN_CHARACTER
        ):
            substitution_end_index = _index_after_command_substitution(
                all_scanned_characters, cursor_index
            )
            for each_blank_target_index in range(cursor_index, substitution_end_index):
                all_scanned_characters[each_blank_target_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
            cursor_index = substitution_end_index
            continue
        if current_character == SHELL_BACKTICK_CHARACTER:
            substitution_end_index = _index_after_backtick_substitution(
                all_scanned_characters, cursor_index, command_length
            )
            for each_blank_target_index in range(cursor_index, substitution_end_index):
                all_scanned_characters[each_blank_target_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
            cursor_index = substitution_end_index
            continue
        cursor_index += 1
    return "".join(all_scanned_characters)


def _strip_heredoc_bodies(command: str) -> str:
    """Replace heredoc bodies with spaces so embedded text is inert.

    A here-document opener (``<<TAG``, ``<<'TAG'``, ``<<"TAG"``, or
    ``<<-TAG``) followed by a newline begins a body whose contents bash
    treats as literal data, not as commands. The body terminates at the
    first subsequent line whose only content is the tag — or, for the
    ``<<-`` form, leading TAB characters followed by the tag. Any
    ``gh pr create`` token sitting inside a heredoc body is data being
    fed to a command like ``cat`` or ``ssh``, not a command the shell
    will execute, so the matcher must not see it.

    Quote tracking is required because a literal ``<<EOF`` sitting
    inside a quoted argument (for example ``echo "use <<EOF in your
    script"``) is not a heredoc opener — it is literal text. The walker
    skips past single- and double-quoted regions so the opener detector
    only fires on syntactically real openers. ``<<<`` (here-string) is
    explicitly skipped because it carries no body.

    Body characters between the end of the opener line (the newline
    after the opener) and the start of the closing tag line are
    replaced with ``SHELL_QUOTE_REPLACEMENT_CHARACTER`` so offsets are
    preserved end-to-end. The opener line and the closing tag line are
    left intact so the surrounding command structure stays scannable.

    When the closing tag is never found, no blanking happens — the
    function returns the buffer unchanged for that opener. This
    conservative branch protects against false positives where an
    apparent ``<<TAG`` opener inside an unusual context lacks a real
    matching closer; without it the walker would consume to end of
    buffer and silently erase any real ``gh pr create`` that follows.

    Multiple heredocs in one command are all handled — after each
    successful blanking the walker resumes scanning from the closing
    tag line so a second ``<<TAG2`` opener later in the command is
    processed independently.

    Args:
        command: Raw bash command string from the PreToolUse or
            PostToolUse hook input. The helper runs BEFORE
            ``_strip_quoted_regions`` so a heredoc opener whose tag
            is itself quoted (``<<'EOF'``) still has its tag visible
            for closing-tag matching.

    Returns:
        A string of identical length to ``command`` with every heredoc
        body blanked to spaces and opener/closer lines left intact.
    """
    all_scanned_characters = list(command)
    command_length = len(command)
    cursor_index = 0
    while cursor_index < command_length:
        current_character = all_scanned_characters[cursor_index]
        if current_character == "'":
            cursor_index = _advance_past_single_quoted_region(
                all_scanned_characters, cursor_index, command_length
            )
            continue
        if current_character == "\"":
            cursor_index = _advance_past_double_quoted_region(
                all_scanned_characters, cursor_index, command_length
            )
            continue
        if not _is_heredoc_opener_position(all_scanned_characters, cursor_index, command_length):
            cursor_index += 1
            continue
        advance_after_blanking = _try_blank_one_heredoc_body(
            all_scanned_characters, cursor_index, command_length
        )
        if advance_after_blanking is None:
            cursor_index += 1
            continue
        cursor_index = advance_after_blanking
    return "".join(all_scanned_characters)


def _advance_past_single_quoted_region(
    all_scanned_characters: list[str],
    opener_index: int,
    buffer_length: int,
) -> int:
    """Return the index one past the closing ``'`` without mutating the buffer."""
    cursor_index = opener_index + 1
    while cursor_index < buffer_length:
        if all_scanned_characters[cursor_index] == "'":
            return cursor_index + 1
        cursor_index += 1
    return cursor_index


def _advance_past_double_quoted_region(
    all_scanned_characters: list[str],
    opener_index: int,
    buffer_length: int,
) -> int:
    """Return the index one past the closing ``"`` honoring ``\\`` escapes."""
    cursor_index = opener_index + 1
    while cursor_index < buffer_length:
        current_character = all_scanned_characters[cursor_index]
        if (
            current_character == SHELL_BACKSLASH_CHARACTER
            and cursor_index + 1 < buffer_length
        ):
            cursor_index += SHELL_BACKSLASH_ESCAPE_PAIR_LENGTH
            continue
        if current_character == "\"":
            return cursor_index + 1
        cursor_index += 1
    return cursor_index


def _is_heredoc_opener_position(
    all_scanned_characters: list[str],
    cursor_index: int,
    buffer_length: int,
) -> bool:
    """Return True when the cursor sits at a ``<<`` (but not ``<<<``) heredoc opener."""
    if cursor_index + 1 >= buffer_length:
        return False
    if all_scanned_characters[cursor_index] != SHELL_LESS_THAN_CHARACTER:
        return False
    if all_scanned_characters[cursor_index + 1] != SHELL_LESS_THAN_CHARACTER:
        return False
    if (
        cursor_index + HEREDOC_OPENER_TOKEN_LENGTH < buffer_length
        and all_scanned_characters[cursor_index + HEREDOC_OPENER_TOKEN_LENGTH]
        == SHELL_LESS_THAN_CHARACTER
    ):
        return False
    return True


def _try_blank_one_heredoc_body(
    all_scanned_characters: list[str],
    opener_index: int,
    buffer_length: int,
) -> int | None:
    """Blank one heredoc body in place when a matching closing tag is found.

    Args:
        all_scanned_characters: Mutable list view of the command string.
            The function MUTATES the buffer to blank body characters
            with ``SHELL_QUOTE_REPLACEMENT_CHARACTER``.
        opener_index: Index of the first ``<`` in the ``<<`` opener.
        buffer_length: Length of ``all_scanned_characters``, hoisted by
            the caller.

    Returns:
        The index just past the closing tag line on a successful match.
        ``None`` when no tag could be parsed or no matching closing tag
        was found — the buffer is left unchanged in either case so the
        outer walker can advance by one and continue scanning.
    """
    after_opener_index = opener_index + HEREDOC_OPENER_TOKEN_LENGTH
    tag_match = HEREDOC_OPENER_TAG_PATTERN.match(
        "".join(all_scanned_characters), after_opener_index
    )
    if tag_match is None:
        return None
    parsed_tag = (
        tag_match.group("sq_tag")
        or tag_match.group("dq_tag")
        or tag_match.group("bare_tag")
    )
    if not parsed_tag:
        return None
    tag_allows_leading_tabs = tag_match.group("dash") == "-"
    end_of_opener_line_index = _index_of_next_newline(
        all_scanned_characters, tag_match.end(), buffer_length
    )
    if end_of_opener_line_index >= buffer_length:
        return None
    body_start_index = end_of_opener_line_index + 1
    closing_tag_line_start, closing_tag_line_end = _find_closing_heredoc_tag_line(
        all_scanned_characters,
        body_start_index,
        buffer_length,
        parsed_tag,
        tag_allows_leading_tabs,
    )
    if closing_tag_line_start is None:
        return None
    for each_blank_target_index in range(body_start_index, closing_tag_line_start):
        all_scanned_characters[each_blank_target_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
    return closing_tag_line_end


def _index_of_next_newline(
    all_scanned_characters: list[str],
    start_index: int,
    buffer_length: int,
) -> int:
    """Return the index of the next newline at or after ``start_index``."""
    cursor_index = start_index
    while cursor_index < buffer_length:
        if all_scanned_characters[cursor_index] == SHELL_NEWLINE_CHARACTER:
            return cursor_index
        cursor_index += 1
    return cursor_index


def _find_closing_heredoc_tag_line(
    all_scanned_characters: list[str],
    body_start_index: int,
    buffer_length: int,
    expected_tag: str,
    tag_allows_leading_tabs: bool,
) -> tuple[int | None, int]:
    """Return ``(start_of_closing_tag_line, end_of_closing_tag_line)`` for the tag.

    The closing tag must appear on its own line — the entire line, after
    any allowed leading tabs (only when the opener used ``<<-``), is the
    tag and nothing else. Trailing carriage returns and trailing spaces
    are tolerated so heredocs authored in CRLF files still match.

    Args:
        all_scanned_characters: Character buffer being walked.
        body_start_index: Index of the first byte of the heredoc body
            (the character after the newline that ended the opener line).
        buffer_length: Length of ``all_scanned_characters``.
        expected_tag: The tag extracted from the opener.
        tag_allows_leading_tabs: True when the opener used ``<<-`` (so
            leading TAB characters on the closing line are allowed).

    Returns:
        ``(start_of_closing_tag_line, end_of_closing_tag_line)`` when a
        matching closing line is found. ``(None, body_start_index)``
        when no matching line is found.
    """
    line_start_index = body_start_index
    while line_start_index < buffer_length:
        line_end_index = _index_of_next_newline(
            all_scanned_characters, line_start_index, buffer_length
        )
        line_text = "".join(
            all_scanned_characters[line_start_index:line_end_index]
        )
        stripped_line_text = line_text.rstrip(" \t\r")
        if tag_allows_leading_tabs:
            stripped_line_text = stripped_line_text.lstrip("\t")
        if stripped_line_text == expected_tag:
            return line_start_index, line_end_index
        line_start_index = line_end_index + 1
    return None, body_start_index


def _preprocess_command_for_matching(command: str) -> str:
    """Return the canonical preprocessed form used by every command-shape matcher.

    The enforcer, the restore hook, and the web-flag detector all share
    the same preprocessing pipeline: blank heredoc bodies first so a
    literal ``gh pr create`` inside heredoc data text cannot leak out
    as a real command; blank inert quoted regions next; blank bash
    comments last. Running every pass through a single helper keeps the
    three callers in lock-step — adding a new preprocessing pass lands
    on every consumer automatically.

    Heredoc stripping runs BEFORE quoted-region stripping because a
    heredoc tag can itself be quoted (``<<'EOF'``); stripping quotes
    first would blank the tag and break the closing-tag match. The
    heredoc walker carries its own minimal quote skip so a literal
    ``<<EOF`` sitting inside a string is not mistaken for a real opener.

    Args:
        command: Raw bash command string from the PreToolUse or
            PostToolUse hook input.

    Returns:
        The command with heredoc bodies, quoted regions, and bash
        comments blanked, substitution bodies kept scannable, and
        original offsets preserved end-to-end.
    """
    return _strip_bash_comments(_strip_quoted_regions(_strip_heredoc_bodies(command)))


def _all_gh_pr_create_segments(quote_stripped_command: str) -> list[str]:
    """Return every ``gh pr create`` segment in the (quote-stripped) command.

    A "segment" is the substring from the end of a ``gh pr create`` match
    up to the next shell command separator (``&&``, ``||``, ``;``,
    ``|``, ``&``, newline) or the end of the string. The enforcer's
    web-flag detection runs against each segment independently so a
    chained ``gh pr create --web && gh pr create --title T`` does not
    let the second invocation slip through on the strength of the
    first segment's ``--web`` flag.

    Args:
        quote_stripped_command: Output of ``_strip_quoted_regions`` —
            the caller is responsible for stripping inert quoted regions
            before passing in.

    Returns:
        List of segment strings, one per ``gh pr create`` invocation
        found in the command. Empty list when the command does not
        invoke ``gh pr create`` at all.
    """
    all_segments: list[str] = []
    command_length = len(quote_stripped_command)
    for each_gh_pr_create_match in GH_PR_CREATE_PATTERN.finditer(quote_stripped_command):
        segment_start = each_gh_pr_create_match.end()
        separator_match = COMMAND_SEPARATOR_PATTERN.search(quote_stripped_command, segment_start)
        segment_end = separator_match.start() if separator_match else command_length
        all_segments.append(quote_stripped_command[segment_start:segment_end])
    return all_segments


def _command_invokes_gh_pr_create_in_stripped(quote_stripped_command: str) -> bool:
    """Return True when the (quote-stripped) command contains a ``gh pr create`` invocation.

    Both the enforcer's PreToolUse gate and the restore hook's
    PostToolUse gate share this function, so the pair stays in sync —
    a fix here lands on both ends of the swap-restore pair at once.
    A literal ``gh pr create`` inside ``echo "..."`` or any other quoted
    argument is intentionally ignored because the caller has already run
    ``_strip_quoted_regions`` to blank out inert quoted text.

    Args:
        quote_stripped_command: Output of ``_strip_quoted_regions`` —
            the caller is responsible for stripping inert quoted regions
            before passing in. ``main()`` in the enforcer computes this
            once and passes it to both this helper and
            ``_command_uses_web_flag_in_stripped`` so the character-walk
            in ``_strip_quoted_regions`` runs exactly once per command.

    Returns:
        True when ``gh pr create`` appears as a whole-word match in the
        already-stripped command. Matches regardless of whether ``gh``
        is at the start of the command or embedded in a chained pipeline.
    """
    return bool(GH_PR_CREATE_PATTERN.search(quote_stripped_command))
