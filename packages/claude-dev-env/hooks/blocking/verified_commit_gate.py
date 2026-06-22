"""PreToolUse gate: git commit/push lands only behind a minted verifier verdict.

Fires on Bash and PowerShell tool calls. When the command carries a
``git commit`` or ``git push``, the gate resolves the repository the command
targets, computes the live change-surface manifest against the merge base,
and allows the command only when one of these holds:

- the command carries the verification bypass marker (``# verify-skip``),
  a manual on-the-fly override that skips the gate for that one command,
- the repository has no resolvable upstream base — no ``origin/HEAD``, no
  configured tracking ref, and neither ``origin/main`` nor ``origin/master``
  (scratch repos with no remote branch are out of scope),
- the surface is mechanically exempt (docs/images by extension, pytest
  test files by name convention, Python files whose docstring-stripped
  AST is unchanged), or
- a passing verifier verdict binds to the exact live manifest hash —
  matched by content hash, not by work-tree location, so a verdict
  ``verifier_verdict_minter.py`` minted while verifying any work tree of
  the surface clears the commit, as does one a workflow ``code-verifier``
  emitted in its own transcript.

The surface binds every changed and untracked file's content, so slicing
work into small commits or staging files cannot move the hash, while any
content edit or new file after verification invalidates the verdict.
Verdict files live under ``~/.claude/verification/`` and are minted only by
the SubagentStop hook when a ``code-verifier`` agent finishes.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

blocking_directory = str(Path(__file__).resolve().parent)
if blocking_directory not in sys.path:
    sys.path.insert(0, blocking_directory)

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from config.verified_commit_constants import (
    ALL_GIT_BINARY_NAMES,
    CORRECTIVE_MESSAGE,
    DIRECTORY_CHANGE_OPTION_TERMINATOR,
    DIRECTORY_CHANGE_PATH_OPTIONS,
    DIRECTORY_CHANGE_PATTERN_PREFIX,
    DIRECTORY_CHANGE_PATTERN_SUFFIX,
    DIRECTORY_CHANGE_VERBS,
    GATED_GIT_SUBCOMMANDS,
    ALL_GATED_TOOL_NAMES,
    HASH_PREVIEW_LENGTH,
    OPTION_WITH_VALUE_STEP,
    REPO_DIRECTORY_OPTION,
    VALUE_TAKING_GIT_OPTIONS,
    VERIFICATION_BYPASS_MARKER,
    WORK_TREE_OPTION,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from verification_verdict_store import (
    branch_surface_manifest,
    is_verification_exempt_diff,
    load_valid_verdict,
    manifest_sha256,
    minted_verdict_covers_surface,
    resolve_merge_base,
    resolve_repo_root,
    workflow_verdict_covers_surface,
)


def _collapse_line_continuations(command_text: str) -> str:
    """Remove backslash-newline line continuations the shell would erase.

    Bash joins a line continuation — a backslash immediately followed by a
    newline — by deleting both characters, so ``git \\<newline>commit``,
    ``git commit\\<newline> -m x``, and ``g\\<newline>it commit`` all run as a
    plain ``git commit``. Stripping the pair before tokenizing makes the token
    stream match what the shell executes, so a continuation abutting the
    subcommand or splitting the ``git`` word cannot evade the gate.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        The command with every backslash-newline pair removed.
    """
    return re.sub(r"\\\r?\n", "", command_text)


def _quoted_spans(command_text: str) -> list[tuple[int, int]]:
    """Find the character spans of every quoted region in a command.

    Scans single- and double-quoted runs left to right so a verb sitting
    inside a quoted ``-m`` commit message is recognised as message text
    rather than a real shell directory change.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        The ``(start, end)`` span of each quoted region, in order.
    """
    quoted_region_pattern = re.compile(r"\"[^\"]*\"|'[^']*'")
    return [
        (each_match.start(), each_match.end())
        for each_match in quoted_region_pattern.finditer(command_text)
    ]


def _is_inside_quoted_region(position: int, all_quoted_spans: list[tuple[int, int]]) -> bool:
    """Decide whether a position falls inside any quoted region.

    Args:
        position: A character offset into the command string.
        all_quoted_spans: The quoted-region spans from ``_quoted_spans``.

    Returns:
        True when the offset sits within a quoted region's bounds.
    """
    for each_span_start, each_span_end in all_quoted_spans:
        if each_span_start <= position < each_span_end:
            return True
    return False


def _containing_quoted_span(
    position: int, all_quoted_spans: list[tuple[int, int]]
) -> tuple[int, int] | None:
    """Return the quoted region a position falls inside, or None.

    Args:
        position: A character offset into the command string.
        all_quoted_spans: The quoted-region spans from ``_quoted_spans``.

    Returns:
        The ``(start, end)`` span containing the offset, or None when the
        offset sits outside every quoted region.
    """
    for each_span_start, each_span_end in all_quoted_spans:
        if each_span_start <= position < each_span_end:
            return (each_span_start, each_span_end)
    return None


def _git_word_match_gates(
    git_word_match: re.Match[str],
    command_text: str,
    all_quoted_spans: list[tuple[int, int]],
) -> bool:
    """Decide whether a ``git`` word match counts as a real invocation.

    A ``git`` word outside every quoted region always gates. Inside a quoted
    region the word gates only when the region's content, with edge quotes
    stripped, is a path whose final ``[\\/]``-split segment is ``git`` or
    ``git.exe`` — a wrapper-quoted binary (``"git" commit``), a quoted
    call-operator path (``& 'C:/x/git.exe' commit``), or a quoted install
    path whose directory components carry spaces
    (``& "C:\\Program Files\\Git\\cmd\\git.exe" commit``). A ``git`` word that
    is one word among prose inside a quoted string — an
    ``echo "Next: git commit"`` mention or a ``gh pr comment -b "please git
    commit"`` body — does not gate, because the prose's final path segment is
    the surrounding sentence rather than a bare ``git``/``git.exe`` binary
    name, so the shell never runs that quoted text as a command.

    Args:
        git_word_match: A ``git`` word match in the command.
        command_text: The raw command string from the tool payload.
        all_quoted_spans: The quoted-region spans from ``_quoted_spans``.

    Returns:
        True when the matched ``git`` word counts as a real git invocation.
    """
    containing_span = _containing_quoted_span(git_word_match.start(), all_quoted_spans)
    if containing_span is None:
        return True
    span_start, span_end = containing_span
    quoted_content = _strip_token_quotes(command_text[span_start:span_end])
    final_segment = re.split(r"[\\/]", quoted_content)[-1].lower()
    return final_segment in ALL_GIT_BINARY_NAMES


def _strip_token_quotes(token_text: str) -> str:
    """Remove quote characters from a token's edges.

    Tokens cut from inside a quoted shell-wrapper argument can carry an
    unpaired edge quote (``push"``), so both edges are stripped rather
    than only matched pairs.

    Args:
        token_text: One quote-aware token from a command string.

    Returns:
        The token without leading or trailing quote characters.
    """
    return token_text.strip("\"'")


def _gated_invocation_directory(all_following_tokens: list[str]) -> tuple[bool, str | None]:
    """Walk the tokens after a ``git`` word to its first subcommand.

    Skips git's global options (recording the targeted directory when one
    appears) so a gated verb counts only in subcommand position — never as
    an argument like ``git stash push`` or ``git log --grep commit``. The
    ``-C`` directory wins when both ``-C`` and ``--work-tree`` are present;
    otherwise a ``--work-tree`` value supplies the targeted directory so a
    commit aimed at another repo's work tree gates against that work tree
    rather than the session directory.

    Args:
        all_following_tokens: Quote-stripped tokens after the ``git`` word.

    Returns:
        Whether the first subcommand is gated, and the directory the
        invocation targets via ``-C`` (or ``--work-tree``) when one appears.
    """
    repo_directory: str | None = None
    work_tree_directory: str | None = None
    token_index = 0
    while token_index < len(all_following_tokens):
        each_token = all_following_tokens[token_index]
        option_name, attached_value = _split_option_value(each_token)
        if option_name in VALUE_TAKING_GIT_OPTIONS:
            option_value = (
                attached_value
                if attached_value is not None
                else _value_after_option(all_following_tokens, token_index)
            )
            if option_name == REPO_DIRECTORY_OPTION and option_value is not None:
                repo_directory = _expand_home_prefix(option_value)
            if option_name == WORK_TREE_OPTION and option_value is not None:
                work_tree_directory = _expand_home_prefix(option_value)
            token_index += 1 if attached_value is not None else OPTION_WITH_VALUE_STEP
            continue
        if each_token.startswith("-"):
            token_index += 1
            continue
        return (
            each_token.lower() in GATED_GIT_SUBCOMMANDS,
            repo_directory or work_tree_directory,
        )
    return (False, repo_directory or work_tree_directory)


def _split_option_value(option_token: str) -> tuple[str, str | None]:
    """Split a ``--name=value`` option token into its name and value.

    Args:
        option_token: One quote-stripped token after the ``git`` word.

    Returns:
        The option name and its attached value, or the whole token and None
        when the token carries no ``=`` value.
    """
    if option_token.startswith("--") and "=" in option_token:
        option_name, _, attached_value = option_token.partition("=")
        return (option_name, attached_value)
    return (option_token, None)


def _value_after_option(all_following_tokens: list[str], option_index: int) -> str | None:
    """Read the separate value token that follows a value-taking option.

    Args:
        all_following_tokens: Quote-stripped tokens after the ``git`` word.
        option_index: Index of the value-taking option token.

    Returns:
        The next token when one exists, or None at the end of the tokens.
    """
    if option_index + 1 < len(all_following_tokens):
        return all_following_tokens[option_index + 1]
    return None


def _expand_home_prefix(directory_token: str) -> str:
    """Expand a leading ``~`` to the home directory the shell would use.

    Git does not expand ``~`` for ``-C`` or ``--work-tree`` and never sees a
    shell's ``cd ~`` expansion, so the gate must expand the token itself;
    otherwise it resolves a non-existent ``~/...`` path that git rejects while
    the shell commits in the real home-anchored repo.

    Args:
        directory_token: A directory token that may start with ``~``.

    Returns:
        The token with any leading home prefix expanded, unchanged otherwise.
    """
    if directory_token.startswith("~"):
        return os.path.expanduser(directory_token)
    return directory_token


def _is_absolute_directory(directory_token: str) -> bool:
    """Decide whether a directory-change target is already absolute.

    Treats a POSIX root, a Windows drive or UNC root, a leading slash or
    backslash, and a home-relative ``~`` token as absolute so they are used
    as given rather than joined onto the active directory.

    Args:
        directory_token: The destination of a directory-change verb.

    Returns:
        True when the token names an absolute or home-anchored location.
    """
    if directory_token.startswith("~"):
        return True
    if directory_token.startswith(("/", "\\")):
        return True
    return os.path.isabs(directory_token)


def _resolve_against(active_directory: str, changed_directory: str) -> str:
    """Resolve a directory-change target against the active directory.

    An absolute or home-anchored target replaces the active directory; a
    relative target is joined onto it so a ``cd subdir`` gates against the
    session directory's subdirectory rather than a token git would resolve
    against the hook process's own working directory.

    Args:
        active_directory: The directory in effect before this change.
        changed_directory: The destination of a directory-change verb.

    Returns:
        The directory the shell runs in after the change.
    """
    if _is_absolute_directory(changed_directory):
        return _expand_home_prefix(changed_directory)
    return os.path.join(active_directory, changed_directory)


def _directory_change_target(command_text: str, match_end: int) -> str | None:
    """Read the destination of a directory-change verb.

    Walks the arguments after the verb, skipping a leading ``--`` terminator
    and consuming the value after a PowerShell path option
    (``-Path``/``-LiteralPath``) so the destination is the path rather than
    the flag. A leading shell operator (``cd && git ...``) means no argument
    and the active directory stays unchanged. Applies to every spelling in
    ``DIRECTORY_CHANGE_VERBS`` (``cd``, ``pushd``, ``Set-Location``, ``sl``).

    Args:
        command_text: The raw command string from the tool payload.
        match_end: The offset just past the directory-change verb word.

    Returns:
        The destination path when one follows the verb, or None for a bare
        ``cd`` (a return to the home directory, which the gate ignores).
    """
    all_argument_tokens = _argument_tokens_after_verb(command_text, match_end)
    token_index = 0
    while token_index < len(all_argument_tokens):
        each_token = _strip_token_quotes(all_argument_tokens[token_index])
        if each_token == DIRECTORY_CHANGE_OPTION_TERMINATOR:
            token_index += 1
            continue
        if each_token.lower() in DIRECTORY_CHANGE_PATH_OPTIONS:
            token_index += 1
            continue
        return each_token
    return None


def _argument_tokens_after_verb(command_text: str, match_end: int) -> list[str]:
    """Cut the run of argument tokens that follows a directory-change verb.

    Reads tokens until the first shell command separator (``;``, ``&``,
    ``|``, or a newline), so only the verb's own arguments are returned and a
    following command is left untouched.

    Args:
        command_text: The raw command string from the tool payload.
        match_end: The offset just past the directory-change verb word.

    Returns:
        The quote-aware argument tokens following the verb, in order.
    """
    argument_run_pattern = re.compile(r"[ \t]+((?:\"[^\"]*\"|'[^']*'|[^\s;&|])+)")
    argument_token_pattern = re.compile(r"\"[^\"]*\"|'[^']*'|[^\s;&|]+")
    all_argument_tokens: list[str] = []
    scan_position = match_end
    while True:
        run_match = argument_run_pattern.match(command_text, scan_position)
        if run_match is None:
            return all_argument_tokens
        all_argument_tokens.extend(argument_token_pattern.findall(run_match.group(1)))
        scan_position = run_match.end()


def gated_repo_directories(command_text: str, fallback_directory: str) -> list[str]:
    """Collect the directories of every git commit/push found in a command.

    Backslash-newline line continuations are removed first so the token
    stream matches what the shell runs (``git \\<newline>commit`` is a real
    commit). Scans every ``git`` word in the command — the bare ``git`` and
    the Windows ``git.exe`` spelling, a path-prefixed binary whose final
    segment is ``git``/``git.exe`` (``/usr/bin/git``,
    ``C:\\...\\git.exe``), and a quoted git binary whose stripped content is
    a single token ending in ``git``/``git.exe`` (``"git" commit``,
    ``& 'C:/x/git.exe' commit``) — and token-walks from each to its first
    subcommand. A ``git`` word that is one word among prose inside a quoted
    string (``echo "Next: git commit"``, a ``gh pr comment -b`` body) is left
    alone, because the shell never runs that quoted text. A
    directory-change verb (``cd``, ``pushd``, PowerShell ``Set-Location``,
    or its ``sl`` alias) earlier in the command moves the active directory,
    so a following un-``-C``'d commit/push gates against the directory the
    shell actually runs it in rather than the session cwd. A relative
    change target joins onto the active directory so it resolves the same
    way the shell would, not against the hook process's own cwd.

    Args:
        command_text: The raw command string from the tool payload.
        fallback_directory: The session working directory, used as the
            active directory until a directory-change verb changes it and
            when the git call carries no ``-C`` flag.

    Returns:
        One directory per detected commit/push invocation, in order; empty
        when the command carries no gated git verb.
    """
    command_text = _collapse_line_continuations(command_text)
    git_word_pattern = re.compile(
        r"(?:^|(?<=[\s;&|(\"'/\\]))git(?:\.exe)?(?:[\"'](?=\s|$)|(?=\s|$))",
        re.IGNORECASE,
    )
    directory_change_verb_alternation = "|".join(
        re.escape(each_verb) for each_verb in sorted(DIRECTORY_CHANGE_VERBS)
    )
    directory_change_pattern = re.compile(
        DIRECTORY_CHANGE_PATTERN_PREFIX
        + directory_change_verb_alternation
        + DIRECTORY_CHANGE_PATTERN_SUFFIX,
        re.IGNORECASE,
    )
    command_token_pattern = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")
    all_quoted_spans = _quoted_spans(command_text)
    all_directory_change_matches = [
        each_match
        for each_match in directory_change_pattern.finditer(command_text)
        if not _is_inside_quoted_region(each_match.start(), all_quoted_spans)
    ]
    all_git_word_matches = [
        each_match
        for each_match in git_word_pattern.finditer(command_text)
        if _git_word_match_gates(each_match, command_text, all_quoted_spans)
    ]
    all_ordered_matches = sorted(
        all_git_word_matches + all_directory_change_matches,
        key=lambda each_match: each_match.start(),
    )
    active_directory = fallback_directory
    target_directories: list[str] = []
    for each_match in all_ordered_matches:
        if each_match.group().lower().strip("\"'") in DIRECTORY_CHANGE_VERBS:
            changed_directory = _directory_change_target(command_text, each_match.end())
            if changed_directory is not None:
                active_directory = _resolve_against(active_directory, changed_directory)
            continue
        following_text = command_text[each_match.end():]
        all_following_tokens = [
            _strip_token_quotes(each_token)
            for each_token in command_token_pattern.findall(following_text)
        ]
        is_gated, flagged_directory = _gated_invocation_directory(all_following_tokens)
        if is_gated:
            target_directories.append(
                _resolve_against(active_directory, flagged_directory)
                if flagged_directory is not None
                else active_directory
            )
    return target_directories


def deny_reason_for_directory(target_directory: str, transcript_path: str) -> str | None:
    """Decide whether a commit/push in a directory must be blocked.

    Accepts the command when a minted verdict binds to the live surface, or
    when a workflow-spawned code-verifier emitted a passing verdict bound to
    the same surface in its own transcript — the latter covers workflow runs,
    where SubagentStop never fires to mint a verdict file.

    Args:
        target_directory: The directory the git command targets.
        transcript_path: The live session's transcript path from the payload,
            used to find a workflow code-verifier's verdict.

    Returns:
        The deny reason when the branch diff needs a verdict and neither a
        minted nor a workflow verdict binds to it; None when the command may
        proceed.
    """
    repo_root = resolve_repo_root(target_directory)
    if repo_root is None:
        return None
    merge_base_sha = resolve_merge_base(repo_root)
    if merge_base_sha is None:
        return None
    if is_verification_exempt_diff(repo_root, merge_base_sha):
        return None
    surface_manifest_text = branch_surface_manifest(repo_root, merge_base_sha)
    if surface_manifest_text is None:
        return f"{CORRECTIVE_MESSAGE} (surface manifest failed in {repo_root})"
    live_manifest_sha256 = manifest_sha256(surface_manifest_text)
    if load_valid_verdict(repo_root, live_manifest_sha256) is not None:
        return None
    if minted_verdict_covers_surface(live_manifest_sha256):
        return None
    if workflow_verdict_covers_surface(transcript_path, live_manifest_sha256):
        return None
    hash_preview = live_manifest_sha256[:HASH_PREVIEW_LENGTH]
    return f"{CORRECTIVE_MESSAGE} (repo: {repo_root}, surface sha256 {hash_preview}...)"


def main() -> None:
    """Read the PreToolUse payload and decide whether to allow the command.

    Allows the command without a verdict when it carries the verification
    bypass marker (``VERIFICATION_BYPASS_MARKER``), a manual on-the-fly
    override; otherwise denies an unverified commit or push.
    """
    try:
        pretooluse_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    if pretooluse_payload.get("tool_name", "") not in ALL_GATED_TOOL_NAMES:
        return
    command_text = pretooluse_payload.get("tool_input", {}).get("command", "")
    if not command_text:
        return
    if VERIFICATION_BYPASS_MARKER in command_text:
        return
    session_directory = pretooluse_payload.get("cwd", ".")
    transcript_path = pretooluse_payload.get("transcript_path", "")
    for each_target_directory in gated_repo_directories(command_text, session_directory):
        deny_reason = deny_reason_for_directory(each_target_directory, transcript_path)
        if deny_reason is None:
            continue
        deny_payload = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        }
        log_hook_block(
            calling_hook_name="verified_commit_gate.py",
            hook_event="PreToolUse",
            block_reason=deny_reason,
            tool_name=pretooluse_payload.get("tool_name", "") if isinstance(pretooluse_payload.get("tool_name"), str) else None,
        )
        print(json.dumps(deny_payload))
        return


if __name__ == "__main__":
    main()
