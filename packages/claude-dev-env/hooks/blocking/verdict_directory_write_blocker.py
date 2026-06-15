#!/usr/bin/env python3
"""PreToolUse guard: deny shell access to the verification verdict directory.

The verified-commit gate trusts a single invariant — only
``verifier_verdict_minter.py`` (a SubagentStop hook running in-process)
writes verdict files. settings.json denies the Write/Edit/MultiEdit file
tools against ``~/.claude/verification/**``, but a Bash or PowerShell
command reaches the same directory through ``python -c``, a redirect, or an
``Out-File``/``Set-Content`` cmdlet. A forged verdict only needs the file to
exist with ``all_pass`` true and the live manifest hash — both values the
session can derive — so an unguarded shell write defeats the whole gate.

This guard fires on Bash and PowerShell tool calls and denies any command
whose text references the verdict directory — whether by an absolute
``.claude/verification/`` path, by changing into the Claude home directory
and then writing a relative ``verification/`` path, by naming a verdict
file's ``verification/<root-key>.json`` shape directly, or by pairing a
path-obfuscation primitive (``chr(``, ``bytes.fromhex(``, base64 decode,
``codecs.decode(``, a ``bytes([...])``/``bytearray([...])`` int-list
constructor) with a file write so a path assembled from codes cannot
slip past the literal matchers. No legitimate workflow reaches that
directory through a shell: the minter runs in-process and the gate reads
verdicts in-process, so blocking every shell reference is the fail-closed
stance that keeps the verdict store unforgeable.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import sys
from pathlib import Path

blocking_directory = str(Path(__file__).resolve().parent)
if blocking_directory not in sys.path:
    sys.path.insert(0, blocking_directory)

from config.verified_commit_constants import (
    ALL_GATED_TOOL_NAMES,
    ALL_VERDICT_PATH_SEGMENT_BODIES,
    ALL_VERDICT_PATH_SEGMENT_NAMES,
    BASE64_TOKEN_PATTERN,
    CHARACTER_CODE_SEQUENCE_PATTERN,
    CHR_CALL_CHAIN_PATTERN,
    CHR_CALL_CODE_PATTERN,
    CLAUDE_HOME_DIRECTORY_NAME,
    CLAUDE_HOME_TARGET_BOUNDARY_PATTERN,
    COMMAND_AFTER_DIRECTORY_CHANGE_PATTERN,
    DIRECTORY_CHANGE_OPTION_PREFIX_PATTERN,
    DIRECTORY_CHANGE_OPTION_TERMINATOR,
    DIRECTORY_CHANGE_PATH_OPTIONS,
    DIRECTORY_CHANGE_PATTERN_PREFIX,
    DIRECTORY_CHANGE_PATTERN_SUFFIX,
    DIRECTORY_CHANGE_TARGET_PATTERN,
    DIRECTORY_CHANGE_VERBS,
    FILE_WRITE_PRIMITIVE_PATTERN,
    HEX_DIGITS_PER_BYTE,
    HEX_TOKEN_PATTERN,
    NON_REDIRECT_FILE_WRITE_PRIMITIVE_PATTERN,
    PATH_OBFUSCATION_PRIMITIVE_PATTERN,
    RELATIVE_VERDICT_DIRECTORY_PATTERN,
    VERDICT_DIRECTORY_GUARD_MESSAGE,
    VERDICT_DIRECTORY_NAME,
    VERDICT_DIRECTORY_NAME_SEPARATOR_PATTERN,
    VERDICT_DIRECTORY_PATH_BOUNDARY_PATTERN,
    VERDICT_DIRECTORY_CHANGE_TARGET_PATTERN,
    VERDICT_DIRECTORY_TARGET_BOUNDARY_PATTERN,
    VERDICT_FILE_RELATIVE_REFERENCE_PATTERN,
    VERDICT_PATH_GLUE_PATTERN,
    VERDICT_PATH_JOINED_VARIABLE_PATTERN,
    VERDICT_PATH_VARIABLE_ASSIGNMENT_PATTERN,
    WRITE_CALL_REGION_PATTERN,
)


def _directory_change_verbs_pattern() -> str:
    """Build the alternation of directory-change verbs for a change matcher.

    Returns:
        The regex alternation of escaped directory-change verbs in sorted
        order, ready to sit between the change prefix and suffix patterns.
    """
    return "|".join(re.escape(each_verb) for each_verb in sorted(DIRECTORY_CHANGE_VERBS))


def _directory_change_option_prefix_pattern() -> str:
    """Build the optional path-option prefix that may precede a change target.

    A PowerShell directory change names its destination after a path flag
    (``Set-Location -Path ~/.claude/verification``,
    ``Set-Location -LiteralPath ...``), and a POSIX ``cd`` may guard the
    destination with the ``--`` end-of-options terminator
    (``cd -- ~/.claude/verification``). Consuming any run of those tokens
    before the target keeps the flag from being read as the destination, so
    the change matchers see the real path the same way the sibling gate's
    ``_directory_change_target`` token-walk does.

    Returns:
        The regex matching zero or more leading path-option or terminator
        tokens, ready to sit between the change suffix and target patterns.
    """
    option_alternation = "|".join(
        re.escape(each_option)
        for each_option in sorted(DIRECTORY_CHANGE_PATH_OPTIONS | {DIRECTORY_CHANGE_OPTION_TERMINATOR})
    )
    return DIRECTORY_CHANGE_OPTION_PREFIX_PATTERN % option_alternation


def _references_absolute_verdict_path(command_text: str) -> bool:
    """Decide whether a command names an absolute ``.claude/verification/`` path.

    Matches the Claude-home/verdict-directory name pair joined by any run of
    path separators, quotes, commas, or whitespace, anchored by a trailing
    path separator. That separator class catches every home prefix form
    (``~``, ``$HOME``, an expanded absolute path), either path separator, and
    the ``joinpath('.claude', 'verification', ...)`` / ``os.path.join``
    spellings; the trailing path boundary keeps sibling directories
    (``verification-docs``) and bare prose mentions of the path from matching.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when the command names an absolute verdict-directory path.
    """
    verdict_directory_pattern = re.compile(
        re.escape(CLAUDE_HOME_DIRECTORY_NAME)
        + VERDICT_DIRECTORY_NAME_SEPARATOR_PATTERN
        + re.escape(VERDICT_DIRECTORY_NAME)
        + VERDICT_DIRECTORY_PATH_BOUNDARY_PATTERN,
        re.IGNORECASE,
    )
    return verdict_directory_pattern.search(command_text) is not None


def _changes_into_claude_home_then_writes_relative(command_text: str) -> bool:
    """Decide whether a command enters the Claude home then writes ``verification/``.

    A ``cd ~/.claude`` (or ``pushd``/``Set-Location``/``sl`` into any path
    ending in ``.claude``) followed by a relative ``verification/`` write
    lands in the verdict directory without ever naming the two segments
    adjacently, so the absolute-path matcher alone misses it.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when a directory change into ``.claude`` precedes a relative
        verdict-directory reference.
    """
    directory_change_into_claude_pattern = re.compile(
        DIRECTORY_CHANGE_PATTERN_PREFIX
        + _directory_change_verbs_pattern()
        + DIRECTORY_CHANGE_PATTERN_SUFFIX
        + _directory_change_option_prefix_pattern()
        + DIRECTORY_CHANGE_TARGET_PATTERN
        + re.escape(CLAUDE_HOME_DIRECTORY_NAME)
        + CLAUDE_HOME_TARGET_BOUNDARY_PATTERN,
        re.IGNORECASE,
    )
    change_match = directory_change_into_claude_pattern.search(command_text)
    if change_match is None:
        return False
    relative_verdict_pattern = re.compile(RELATIVE_VERDICT_DIRECTORY_PATTERN, re.IGNORECASE)
    return relative_verdict_pattern.search(command_text, change_match.end()) is not None


def _changes_into_verdict_directory_then_writes(command_text: str) -> bool:
    """Decide whether a command enters the verdict directory then runs a command.

    A ``cd ~/.claude/verification`` (or ``pushd``/``Set-Location``/``sl`` into
    any path ending in ``.claude/verification``, with or without a trailing
    separator) followed by any further command lands a forged verdict in the
    verdict directory without naming the ``verification/`` prefix on the file,
    so the other matchers miss it. The trust contract denies every shell
    command that reaches the verdict directory, so any command after the
    change — a redirect, ``cp``, ``mv``, ``tee``, ``install``, or a
    ``python -c`` write — is a forge vector. Matching any command separator
    followed by content keeps the guard write-agnostic rather than chasing an
    open-ended verb list.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when a directory change into the verdict directory precedes any
        further command.
    """
    directory_change_into_verdict_pattern = re.compile(
        DIRECTORY_CHANGE_PATTERN_PREFIX
        + _directory_change_verbs_pattern()
        + DIRECTORY_CHANGE_PATTERN_SUFFIX
        + _directory_change_option_prefix_pattern()
        + DIRECTORY_CHANGE_TARGET_PATTERN
        + re.escape(CLAUDE_HOME_DIRECTORY_NAME)
        + r"[\\/]"
        + re.escape(VERDICT_DIRECTORY_NAME)
        + VERDICT_DIRECTORY_TARGET_BOUNDARY_PATTERN,
        re.IGNORECASE,
    )
    change_match = directory_change_into_verdict_pattern.search(command_text)
    if change_match is None:
        return False
    command_after_change_pattern = re.compile(COMMAND_AFTER_DIRECTORY_CHANGE_PATTERN)
    return command_after_change_pattern.search(command_text, change_match.end()) is not None


def _references_verdict_file_shape(command_text: str) -> bool:
    """Decide whether a command names a verdict file's ``verification/<key>.json`` shape.

    A verdict file name is ``verification/<root-key-hex>.json``, where the
    root key is the leading hex digits of a repo-path digest. Naming that
    shape relative to any directory is a forge vector on its own, so it is
    flagged regardless of a preceding directory change.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when the command names the verdict-file shape.
    """
    verdict_file_pattern = re.compile(VERDICT_FILE_RELATIVE_REFERENCE_PATTERN, re.IGNORECASE)
    return verdict_file_pattern.search(command_text) is not None


def _decoded_texts_from_command(command_text: str) -> list[str]:
    """Decode every hex, base64, character-code, and chr-chain token a command embeds.

    A path-obfuscation forge hides ``.claude`` or ``verification`` inside hex
    digits, a base64 token, a comma-separated character-code sequence, or a
    run of ``+``-joined ``chr(<int>)`` calls. Decoding each token back to text
    lets the segment matcher see the hidden name. Tokens that fail to decode or
    carry an out-of-range code are skipped.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        The lowercase decoded text for every token that decodes cleanly.
    """
    all_decoded_texts: list[str] = []
    for each_hex_token in re.findall(HEX_TOKEN_PATTERN, command_text, re.IGNORECASE):
        decoded_hex_text = _decode_hex_token(each_hex_token)
        if decoded_hex_text:
            all_decoded_texts.append(decoded_hex_text.lower())
    for each_base64_token in re.findall(BASE64_TOKEN_PATTERN, command_text):
        decoded_base64_text = _decode_base64_token(each_base64_token)
        if decoded_base64_text:
            all_decoded_texts.append(decoded_base64_text.lower())
    for each_code_sequence in re.findall(CHARACTER_CODE_SEQUENCE_PATTERN, command_text):
        decoded_code_text = _decode_character_code_sequence(each_code_sequence)
        if decoded_code_text:
            all_decoded_texts.append(decoded_code_text.lower())
    for each_chr_chain in re.findall(CHR_CALL_CHAIN_PATTERN, command_text, re.IGNORECASE):
        decoded_chain_text = _decode_chr_call_chain(each_chr_chain)
        if decoded_chain_text:
            all_decoded_texts.append(decoded_chain_text.lower())
    return all_decoded_texts


def _decode_hex_token(hex_token: str) -> str:
    """Decode a hex-digit token to text, returning empty text on failure.

    Args:
        hex_token: A run of hex digits taken from the command.

    Returns:
        The decoded ASCII text, or empty text when the token is odd-length,
        not valid hex, or not decodable as ASCII.
    """
    if len(hex_token) % HEX_DIGITS_PER_BYTE == 1:
        return ""
    try:
        return bytes.fromhex(hex_token).decode("ascii")
    except (ValueError, binascii.Error):
        return ""


def _decode_base64_token(base64_token: str) -> str:
    """Decode a base64 token to text, returning empty text on failure.

    Args:
        base64_token: A base64-shaped token taken from the command.

    Returns:
        The decoded ASCII text, or empty text when the token is not valid
        base64 or not decodable as ASCII.
    """
    try:
        return base64.b64decode(base64_token, validate=True).decode("ascii")
    except (ValueError, binascii.Error):
        return ""


def _decode_character_code_sequence(code_sequence: str) -> str:
    """Decode a comma-separated character-code sequence to text.

    The ``CHARACTER_CODE_SEQUENCE_PATTERN`` source caps each code at three
    decimal digits, so every code is a valid ``chr`` argument and decoding
    always succeeds.

    Args:
        code_sequence: A comma-separated run of decimal character codes, each
            within the three-digit range the source pattern admits.

    Returns:
        The decoded text.
    """
    decoded_characters: list[str] = []
    for each_code in code_sequence.split(","):
        code_point = int(each_code.strip())
        decoded_characters.append(chr(code_point))
    return "".join(decoded_characters)


def _decode_chr_call_chain(chr_chain: str) -> str:
    """Decode a run of ``+``-joined ``chr(<int>)`` calls to text.

    A forge assembles ``/.claude/verification/`` from a run of
    ``chr(<code>)+chr(<code>)+...`` calls so the path carries no comma-separated
    code list and no literal segment name. The ``CHR_CALL_CHAIN_PATTERN``
    source caps each code at three decimal digits, so every captured int is a
    valid ``chr`` argument and decoding always succeeds.

    Args:
        chr_chain: A run of two or more ``+``-joined ``chr(<int>)`` calls
            taken from the command.

    Returns:
        The decoded text.
    """
    decoded_characters: list[str] = []
    for each_code in re.findall(CHR_CALL_CODE_PATTERN, chr_chain, re.IGNORECASE):
        decoded_characters.append(chr(int(each_code)))
    return "".join(decoded_characters)


def _decoded_token_references_verdict_segment(command_text: str) -> bool:
    """Decide whether a decodable token in a command hides a verdict-path segment.

    A forge hides ``.claude`` or ``verification`` inside a hex, base64,
    character-code, or ``+``-joined ``chr(<int>)`` chain token
    (``bytes.fromhex('2e636c61756465')`` and a ``chr(<code>)+chr(<code>)+...``
    run both decode to a ``.claude`` segment). Such a token carries no
    incidental meaning — text that decodes to a verdict-path segment body
    (``claude``) is forge evidence wherever it sits in the command, so this
    check is not scoped to the write call.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when a decodable token decodes to a verdict-path segment body.
    """
    all_decoded_texts = _decoded_texts_from_command(command_text)
    for each_decoded_text in all_decoded_texts:
        for each_segment_body in ALL_VERDICT_PATH_SEGMENT_BODIES:
            if each_segment_body in each_decoded_text:
                return True
    return False


def _write_call_region_names_verdict_segment(command_text: str) -> bool:
    """Decide whether a write call's argument region names a verdict-path segment.

    The region runs from a non-redirect write primitive (``open(``,
    ``write_text``, ``Out-File``, ``Set-Content``, ``Add-Content``, ``tee``)
    to the next statement separator (``;``, ``|``, ``&``, newline) or the end
    of the command. A plain-text ``.claude`` or ``verification`` inside that
    region is part of the path being written, so it is a forge signal; the
    same word in a later statement (``open(chr(...)+chr(...));
    print('verification done')``) sits past the separator and does not count.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when a verdict-path segment name appears inside a write call's
        argument region.
    """
    write_call_region_pattern = re.compile(WRITE_CALL_REGION_PATTERN, re.IGNORECASE)
    for each_region_match in write_call_region_pattern.finditer(command_text):
        lowercased_region = each_region_match.group(0).lower()
        for each_segment_name in ALL_VERDICT_PATH_SEGMENT_NAMES:
            if each_segment_name in lowercased_region:
                return True
    return False


def _uses_obfuscated_path_write(command_text: str) -> bool:
    """Decide whether a command builds a verdict path with obfuscation and writes.

    A character-construction primitive (``chr(``, ``bytes.fromhex(``, base64
    decode, ``codecs.decode(``, a ``bytes([...])``/``bytearray([...])``
    int-list constructor) assembles a path from codes that carry no
    literal ``verification`` or ``.claude`` substring, so the text-pattern
    matchers miss it. The pairing fires only when three conditions hold
    together: an obfuscation primitive, a non-redirect write call (``open(``,
    ``write_text``, ``Out-File``, ``Set-Content``, ``Add-Content``, ``tee``),
    and a verdict-path segment reachable by that write — either a decodable
    token that decodes to a segment body anywhere in the command, or a
    plain-text segment name inside the write call's argument region.

    Scoping the plain-text segment to the write region leaves an unrelated
    decode-and-print one-liner whose write targets another path
    (``open(chr(...)+chr(...)); print('verification done')``) alone, because
    the incidental ``verification`` sits in a later statement rather than the
    write call. A decode-to-file one-liner with no segment
    (``open('decoded.bin','wb').write(b64decode(x))``) is also left alone,
    while a forge whose path decodes to the verdict directory is still caught.
    A bare ``>`` redirect to the verdict path is caught by the literal-path
    matchers, so a command whose only write is a redirect is left alone here.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when the command pairs a path-obfuscation primitive with a
        non-redirect file write and a verdict-path segment reachable by that
        write.
    """
    has_obfuscation_primitive = re.search(PATH_OBFUSCATION_PRIMITIVE_PATTERN, command_text) is not None
    has_non_redirect_write = (
        re.search(NON_REDIRECT_FILE_WRITE_PRIMITIVE_PATTERN, command_text) is not None
    )
    if not (has_obfuscation_primitive and has_non_redirect_write):
        return False
    if _decoded_token_references_verdict_segment(command_text):
        return True
    return _write_call_region_names_verdict_segment(command_text)


def _segments_join_as_verdict_path(command_text: str) -> bool:
    """Decide whether the two name segments sit adjacent in a path-join shape.

    The ``.claude`` home name and the ``verification`` directory name connect
    through only path-join glue — quotes, a ``+`` concatenation operator,
    whitespace, and a path separator — in either order, so a string
    concatenation (``'/.claude'+'/verification'``) reads as one verdict path
    while a prose mention (``.claude docs about the verification flow``) does
    not, because the words between the segments are not path-join glue.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when the two segments connect through a path-join shape.
    """
    home_name = re.escape(CLAUDE_HOME_DIRECTORY_NAME)
    verdict_name = re.escape(VERDICT_DIRECTORY_NAME)
    path_join_pattern = re.compile(
        home_name + VERDICT_PATH_GLUE_PATTERN + verdict_name
        + "|"
        + verdict_name + VERDICT_PATH_GLUE_PATTERN + home_name,
        re.IGNORECASE,
    )
    return path_join_pattern.search(command_text) is not None


def _segments_join_through_shell_variable(command_text: str) -> bool:
    """Decide whether a shell variable path-joins the two name segments.

    One segment binds to a shell variable (``p=~/.claude``,
    ``VDIR=verification``) whose ``$p``/``$VDIR`` reference is then
    path-joined toward the verdict directory (``$p/verification``,
    ``$VDIR/a.json``); the other segment appears elsewhere in the command. A
    redirect to ``/tmp/notes.txt`` carries no path-joined variable reference,
    so a benign mention of both words passes.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when a path-joined variable reference binds one segment while the
        other segment appears in the command.
    """
    lowercased_command = command_text.lower()
    home_name = CLAUDE_HOME_DIRECTORY_NAME.lower()
    verdict_name = VERDICT_DIRECTORY_NAME.lower()
    joined_variable_pattern = re.compile(VERDICT_PATH_JOINED_VARIABLE_PATTERN)
    for each_prefix_name, each_suffix_name in joined_variable_pattern.findall(command_text):
        variable_name = each_prefix_name or each_suffix_name
        assignment_pattern = re.compile(
            VERDICT_PATH_VARIABLE_ASSIGNMENT_PATTERN % re.escape(variable_name)
        )
        assignment_match = assignment_pattern.search(command_text)
        if assignment_match is None:
            continue
        assigned_value = assignment_match.group(1).lower()
        binds_home = home_name in assigned_value
        binds_verdict = verdict_name in assigned_value
        if binds_home and verdict_name in lowercased_command:
            return True
        if binds_verdict and home_name in lowercased_command:
            return True
    return False


def _changes_through_split_directory_change_into_verdict(command_text: str) -> bool:
    """Decide whether a split directory change reaches the verdict directory then runs a command.

    A change into the Claude home (``cd ~/.claude``) followed by a change into
    a relative ``verification`` directory (``cd verification``) lands in the
    verdict directory without naming the two segments adjacently. The trust
    contract denies every shell command that reaches the verdict directory, so
    any command after the second change — a redirect, ``cp``, ``mv``, ``tee``,
    ``install``, or a ``python -c`` write — is a forge vector, mirroring the
    single-step ``cd ~/.claude/verification`` case. An unrelated second change
    (``cd hooks``) lands elsewhere and passes.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when a change into the Claude home precedes a change into a
        relative verdict directory that is itself followed by any further
        command.
    """
    change_into_claude_pattern = re.compile(
        DIRECTORY_CHANGE_PATTERN_PREFIX
        + _directory_change_verbs_pattern()
        + DIRECTORY_CHANGE_PATTERN_SUFFIX
        + _directory_change_option_prefix_pattern()
        + DIRECTORY_CHANGE_TARGET_PATTERN
        + re.escape(CLAUDE_HOME_DIRECTORY_NAME)
        + CLAUDE_HOME_TARGET_BOUNDARY_PATTERN,
        re.IGNORECASE,
    )
    change_into_claude_match = change_into_claude_pattern.search(command_text)
    if change_into_claude_match is None:
        return False
    change_into_verdict_pattern = re.compile(
        DIRECTORY_CHANGE_PATTERN_PREFIX
        + _directory_change_verbs_pattern()
        + DIRECTORY_CHANGE_PATTERN_SUFFIX
        + _directory_change_option_prefix_pattern()
        + VERDICT_DIRECTORY_CHANGE_TARGET_PATTERN,
        re.IGNORECASE,
    )
    change_into_verdict_match = change_into_verdict_pattern.search(
        command_text, change_into_claude_match.end()
    )
    if change_into_verdict_match is None:
        return False
    command_after_change_pattern = re.compile(COMMAND_AFTER_DIRECTORY_CHANGE_PATTERN)
    return (
        command_after_change_pattern.search(command_text, change_into_verdict_match.end())
        is not None
    )


def _writes_with_verdict_path_intent(command_text: str) -> bool:
    """Decide whether a write builds a verdict path from joined segments.

    A path split across string concatenation (``'/.claude'+'/verification'``)
    or a shell variable (``$p/verification``, ``$VDIR/a.json``) lands in the
    verdict directory while breaking the adjacency the literal-path matchers
    require, yet the two name segments still connect through a path-join shape.
    The literal-concatenation shape is paired with a non-redirect write
    (``open(``, ``write_text``, ``Out-File``, ``Set-Content``, ``Add-Content``,
    ``tee``): a bare ``>`` redirect to an adjacent ``.claude/verification``
    literal is already caught by the absolute-path matcher, so requiring a
    non-redirect write here leaves a commit message that merely quotes the
    path before a redirect (``git commit -m "fix .claude/verification gate"
    > /tmp/commit.log``) alone. The shell-variable shape is paired with any
    write primitive, including a redirect, because ``echo x > $p/verification``
    is itself the forge. A command whose two name segments only co-occur as
    free prose inside a quoted message
    (``echo "updated .claude docs about the verification flow"
    > /tmp/notes.txt``) carries no path-join shape and passes, as does a plain
    ``git commit -m "fix .claude/verification gate"`` with no write primitive.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when a non-redirect write co-occurs with a literal concatenation
        of the two verdict-path name segments, or when any write co-occurs
        with a shell variable that path-joins the two segments.
    """
    has_non_redirect_write = (
        re.search(NON_REDIRECT_FILE_WRITE_PRIMITIVE_PATTERN, command_text) is not None
    )
    if has_non_redirect_write and _segments_join_as_verdict_path(command_text):
        return True
    has_write_primitive = re.search(FILE_WRITE_PRIMITIVE_PATTERN, command_text) is not None
    if not has_write_primitive:
        return False
    return _segments_join_through_shell_variable(command_text)


def references_verdict_directory(command_text: str) -> bool:
    """Decide whether a command references the verification verdict directory.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when the command names an absolute verdict path, changes into
        the Claude home before a relative verdict write, changes directly
        into the verdict directory before any command, steps through a split
        directory change into the verdict directory before any command, names
        a verdict file's ``verification/<root-key>.json`` shape, pairs a
        path-obfuscation primitive with a non-redirect file write, or pairs a
        file write with a path-join shape connecting both verdict-path name
        segments.
    """
    if _references_absolute_verdict_path(command_text):
        return True
    if _changes_into_claude_home_then_writes_relative(command_text):
        return True
    if _changes_into_verdict_directory_then_writes(command_text):
        return True
    if _changes_through_split_directory_change_into_verdict(command_text):
        return True
    if _references_verdict_file_shape(command_text):
        return True
    if _writes_with_verdict_path_intent(command_text):
        return True
    return _uses_obfuscated_path_write(command_text)


def decision_for_payload(pretooluse_payload: dict) -> dict | None:
    """Build the deny decision for a verdict-directory shell access.

    Args:
        pretooluse_payload: The PreToolUse hook payload.

    Returns:
        The deny decision mapping when a gated shell command references the
        verdict directory; None when the command may proceed.
    """
    if pretooluse_payload.get("tool_name", "") not in ALL_GATED_TOOL_NAMES:
        return None
    command_text = pretooluse_payload.get("tool_input", {}).get("command", "")
    if not command_text:
        return None
    if not references_verdict_directory(command_text):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": VERDICT_DIRECTORY_GUARD_MESSAGE,
        }
    }


def main() -> None:
    """Read the PreToolUse payload and deny verdict-directory shell access."""
    try:
        pretooluse_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    if not isinstance(pretooluse_payload, dict):
        return
    deny_decision = decision_for_payload(pretooluse_payload)
    if deny_decision is None:
        return
    print(json.dumps(deny_decision))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
