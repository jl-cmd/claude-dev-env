"""Find every gated ``git commit``/``git push`` and the directory it targets.

::

    git commit -m x                    -> gated in the session directory
    cd subdir && git commit -m x       -> gated in session_directory/subdir
    git -C /repo commit -m x           -> gated in /repo
    git stash push                     -> not gated (push is an argument)

Walks the ``git`` words and directory-change verbs in a command, in the order
they appear, so a commit after a ``cd`` gates against the directory the shell
is actually in when it runs.
"""

from __future__ import annotations

import re

from config.verified_commit_constants import (
    DIRECTORY_CHANGE_PATTERN_PREFIX,
    DIRECTORY_CHANGE_PATTERN_SUFFIX,
    DIRECTORY_CHANGE_VERBS,
    GATED_GIT_SUBCOMMANDS,
    OPTION_WITH_VALUE_STEP,
    REPO_DIRECTORY_OPTION,
    VALUE_TAKING_GIT_OPTIONS,
    WORK_TREE_OPTION,
)
from config.verified_commit_gate_output_constants import REGEX_ALTERNATION_SEPARATOR
from verified_commit_gate_parts.command_tokenization import (
    collapse_line_continuations,
    git_word_match_gates,
    is_inside_quoted_region,
    quoted_spans,
    strip_token_quotes,
)
from verified_commit_gate_parts.directory_resolution import (
    directory_change_target,
    expand_home_prefix,
    resolve_against,
    split_option_value,
    value_after_option,
)


def _record_directory_option(
    option_name: str,
    option_value: str | None,
    repo_directory: str | None,
    work_tree_directory: str | None,
) -> tuple[str | None, str | None]:
    """Fold one value-taking git option into the tracked target directories."""
    if option_value is None:
        return repo_directory, work_tree_directory
    if option_name == REPO_DIRECTORY_OPTION:
        return expand_home_prefix(option_value), work_tree_directory
    if option_name == WORK_TREE_OPTION:
        return repo_directory, expand_home_prefix(option_value)
    return repo_directory, work_tree_directory


def _resolved_option_value(
    attached_value: str | None, all_following_tokens: list[str], option_index: int
) -> str | None:
    """Read a value-taking option's value: attached (``--opt=v``) or the next token.

    An attached value is used as given, even when it is the empty string
    (``--work-tree=``), so an empty value never falls through to read the
    following subcommand token as the value.

    Args:
        attached_value: The ``=``-attached value, or None when none was attached.
        all_following_tokens: Quote-stripped tokens after the ``git`` word.
        option_index: Index of the value-taking option token.

    Returns:
        The attached value when present, otherwise the separate value token.
    """
    if attached_value is not None:
        return attached_value
    return value_after_option(all_following_tokens, option_index)


def gated_invocation_directory(
    all_following_tokens: list[str],
    all_gated_subcommands: frozenset[str] = GATED_GIT_SUBCOMMANDS,
) -> tuple[bool, str | None]:
    """Walk the quote-stripped tokens after a ``git`` word to its subcommand.

    Args:
        all_following_tokens: Quote-stripped tokens after the ``git`` word.
        all_gated_subcommands: Subcommand names that gate; defaults to commit+push.
    """
    repo_directory: str | None = None
    work_tree_directory: str | None = None
    token_index = 0
    while token_index < len(all_following_tokens):
        each_token = all_following_tokens[token_index]
        option_name, attached_value = split_option_value(each_token)
        if option_name in VALUE_TAKING_GIT_OPTIONS:
            option_value = _resolved_option_value(
                attached_value, all_following_tokens, token_index
            )
            repo_directory, work_tree_directory = _record_directory_option(
                option_name, option_value, repo_directory, work_tree_directory
            )
            token_index += 1 if attached_value is not None else OPTION_WITH_VALUE_STEP
            continue
        if each_token.startswith("-"):
            token_index += 1
            continue
        return each_token.lower() in all_gated_subcommands, repo_directory or work_tree_directory
    return False, repo_directory or work_tree_directory


def _directory_change_verb_pattern() -> re.Pattern[str]:
    """Build the regex matching any directory-change verb spelling."""
    verb_alternation = REGEX_ALTERNATION_SEPARATOR.join(
        re.escape(each_verb) for each_verb in sorted(DIRECTORY_CHANGE_VERBS)
    )
    return re.compile(
        DIRECTORY_CHANGE_PATTERN_PREFIX + verb_alternation + DIRECTORY_CHANGE_PATTERN_SUFFIX,
        re.IGNORECASE,
    )


def _ordered_gate_matches(command_text: str) -> list[re.Match[str]]:
    """Collect every ``git`` word and directory-change verb match, in order."""
    git_word_pattern = re.compile(
        r"(?:^|(?<=[\s;&|(\"'/\\]))git(?:\.exe)?(?:[\"'](?=\s|$)|(?=\s|$))",
        re.IGNORECASE,
    )
    all_quoted_spans = quoted_spans(command_text)
    all_directory_change_matches = [
        each_match
        for each_match in _directory_change_verb_pattern().finditer(command_text)
        if not is_inside_quoted_region(each_match.start(), all_quoted_spans)
    ]
    all_git_word_matches = [
        each_match
        for each_match in git_word_pattern.finditer(command_text)
        if git_word_match_gates(each_match, command_text, all_quoted_spans)
    ]
    return sorted(
        all_git_word_matches + all_directory_change_matches,
        key=lambda each_match: each_match.start(),
    )


def _following_tokens(command_text: str, match_end: int) -> list[str]:
    """Quote-strip the tokens following a ``git`` word match."""
    command_token_pattern = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")
    following_text = command_text[match_end:]
    return [
        strip_token_quotes(each_token)
        for each_token in command_token_pattern.findall(following_text)
    ]


def _apply_directory_change(
    command_text: str, directory_change_match: re.Match[str], active_directory: str
) -> str:
    """Resolve the active directory after one ``cd``/``pushd`` match."""
    changed_directory = directory_change_target(command_text, directory_change_match.end())
    if changed_directory is None:
        return active_directory
    return resolve_against(active_directory, changed_directory)


def _target_directory_for_match(
    command_text: str,
    git_word_match: re.Match[str],
    active_directory: str,
    all_gated_subcommands: frozenset[str],
) -> str | None:
    """Resolve the gated directory for one ``git`` word match, or None."""
    all_following_tokens = _following_tokens(command_text, git_word_match.end())
    is_gated, flagged_directory = gated_invocation_directory(
        all_following_tokens, all_gated_subcommands
    )
    if not is_gated:
        return None
    if flagged_directory is None:
        return active_directory
    return resolve_against(active_directory, flagged_directory)


def gated_repo_directories(
    command_text: str,
    fallback_directory: str,
    all_gated_subcommands: frozenset[str] = GATED_GIT_SUBCOMMANDS,
) -> list[str]:
    """Collect the directories of every gated git call found in a command.

    Args:
        command_text: The raw command string from the tool payload.
        fallback_directory: The session working directory, the active directory
            until a directory-change verb or a ``-C`` flag overrides it.
        all_gated_subcommands: Subcommand names that gate; defaults to commit+push.

    Returns:
        One directory per detected gated invocation, in order; empty when the
        command carries no gated git verb.
    """
    command_text = collapse_line_continuations(command_text)
    active_directory = fallback_directory
    target_directories: list[str] = []
    for each_match in _ordered_gate_matches(command_text):
        if each_match.group().lower().strip("\"'") in DIRECTORY_CHANGE_VERBS:
            active_directory = _apply_directory_change(command_text, each_match, active_directory)
            continue
        target_directory = _target_directory_for_match(
            command_text, each_match, active_directory, all_gated_subcommands
        )
        if target_directory is not None:
            target_directories.append(target_directory)
    return target_directories
