#!/usr/bin/env python3
import datetime
import enum
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.convergence_branch_constants import (  # noqa: E402
    ALL_CONVERGENCE_BRANCH_PREFIXES,
    CONVERGENCE_BRANCH_SUFFIX_PATTERN,
    CONVERGENCE_FORCE_PUSH_DETECTION_PATTERN,
)
from hooks_constants.destructive_command_segment_constants import (  # noqa: E402
    ALL_BENIGN_COMPOUND_SEGMENT_COMMANDS,
    ALL_COMMAND_LAUNCHER_WRAPPER_COMMANDS,
    ALL_KNOWN_TEMPORARY_ENVIRONMENT_VARIABLE_NAMES,
    ALL_FILE_WRITING_OUTPUT_FLAGS_BY_BENIGN_PROGRAM,
    ALL_FIND_EXEC_ACTION_FLAGS,
    ALL_FIND_EXEC_ACTION_TERMINATORS,
    ALL_FIND_GLOBAL_OPTION_FLAGS_TAKING_A_VALUE,
    ALL_FIND_GLOBAL_OPTION_FLAGS_WITHOUT_VALUE,
    FIND_OPTIMIZATION_LEVEL_OPTION_PREFIX,
    ALL_GH_API_GLUED_REQUEST_BODY_FIELD_FLAG_PREFIXES,
    ALL_GH_API_REQUEST_BODY_FIELD_FLAGS,
    ALL_GH_HTTP_WRITE_METHOD_FLAGS,
    ALL_GH_HTTP_WRITE_METHODS,
    ALL_GIT_CONFIG_READ_ONLY_FLAGS,
    ALL_GIT_FETCH_FORCE_FLAGS,
    ALL_GIT_REMOTE_READ_ONLY_VERBS,
    ALL_INTERPRETER_AND_WRAPPER_COMMANDS,
    ALL_LAUNCHER_OPTIONS_TAKING_SEPARATE_VALUE,
    ALL_LAUNCHERS_REQUIRING_A_POSITIONAL_VALUE,
    ALL_READ_ONLY_SUBCOMMANDS_BY_DISPATCHING_PROGRAM,
    ALL_REMOTE_AND_PROGRAM_STRING_EXECUTORS,
    ALL_SHELL_CONTROL_OPERATOR_TOKENS,
    ALL_STRING_ARGUMENT_EXECUTION_FLAGS,
    ALL_SUBSHELL_GROUPING_CHARACTERS,
    FIND_PROGRAM_NAME,
    GH_HTTP_READ_ONLY_METHOD,
    GH_LONG_METHOD_FLAG_EQUALS_PREFIX,
    GH_SHORT_METHOD_FLAG_PREFIX,
    ALL_READ_ONLY_SUBCOMMAND_POSITION_DEPTHS_BY_DISPATCHING_PROGRAM,
    LAUNCHER_POSITIONAL_VALUE_SHAPE_PATTERN,
    OUTPUT_REDIRECTION_OPERATOR_PATTERN,
)

CLAUDE_DIRECTORY_PATH = os.path.normpath(os.path.expanduser("~/.claude"))
GH_REDIRECT_ACTIVE_ENV_VAR = "CLAUDE_GH_REDIRECT_ACTIVE"
GH_REDIRECT_ACTIVE_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


def gh_redirect_is_active() -> bool:
    env_var_value = os.environ.get(GH_REDIRECT_ACTIVE_ENV_VAR, "").strip().lower()
    return env_var_value in GH_REDIRECT_ACTIVE_TRUTHY_VALUES

def directory_is_ephemeral(directory_path: str) -> bool:
    """Return True when a directory belongs to the ephemeral auto-allow namespace.

    A directory is ephemeral when the environment override has not disabled the
    auto-allow and the path matches one of these sources, in order: a path
    containing a ``/worktrees/`` or ``/worktree/`` segment; a path rooted at ``/tmp``
    or ``/temp`` (drive-letter tolerant); a path under the OS temporary root; a path
    git reports inside a worktree admin directory. Returns False when the
    ``CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW`` override is truthy and when no
    source matches.

    Args:
        directory_path: The filesystem path to classify.

    Returns:
        True when the directory belongs to the ephemeral auto-allow namespace.
    """
    ephemeral_auto_allow_disabled_env_var = "CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW"
    truthy_string_values = frozenset({"1", "true", "yes", "on"})
    if os.environ.get(ephemeral_auto_allow_disabled_env_var, "").strip().lower() in truthy_string_values:
        return False
    forward_slash_normalized_directory_path = os.path.normpath(directory_path).replace("\\", "/").lower()
    all_worktree_path_segments = ("/worktrees/", "/worktree/")
    for each_worktree_segment in all_worktree_path_segments:
        if each_worktree_segment in forward_slash_normalized_directory_path + "/":
            return True
    drive_letter_stripped_path = re.sub(r"^[a-z]:", "", forward_slash_normalized_directory_path)
    all_root_anchored_temporary_directories = ("/tmp", "/temp")
    for each_temporary_root in all_root_anchored_temporary_directories:
        if drive_letter_stripped_path == each_temporary_root or drive_letter_stripped_path.startswith(each_temporary_root + "/"):
            return True
    system_temporary_root = os.path.normpath(tempfile.gettempdir()).replace("\\", "/").lower()
    if forward_slash_normalized_directory_path.startswith(system_temporary_root + "/") or forward_slash_normalized_directory_path == system_temporary_root:
        return True
    try:
        git_rev_parse_completion = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=directory_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if git_rev_parse_completion.returncode != 0:
        return False
    git_directory_path_normalized = git_rev_parse_completion.stdout.strip().replace("\\", "/").lower()
    return "/.git/worktrees/" in git_directory_path_normalized or "/worktrees/" in git_directory_path_normalized


def load_allow_git_reset_hard_projects() -> list[str]:
    allow_git_reset_hard_settings_key = "allowGitResetHardProjects"
    settings_path = Path(CLAUDE_DIRECTORY_PATH) / "settings.json"
    try:
        raw_settings_text = settings_path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        parsed_settings = json.loads(raw_settings_text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed_settings, dict):
        return []
    hooks_section = parsed_settings.get("hooks")
    if not isinstance(hooks_section, dict):
        return []
    raw_allow_list = hooks_section.get(allow_git_reset_hard_settings_key)
    if not isinstance(raw_allow_list, list):
        return []
    return [
        each_project_path
        for each_project_path in raw_allow_list
        if isinstance(each_project_path, str)
    ]

DESTRUCTIVE_BASH_PATTERNS = [
    (re.compile(r'\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r', re.IGNORECASE), "rm -rf (destructive recursive forced delete)"),
    (re.compile(r'\brm\s+--recursive\b.*--force\b|\brm\s+--force\b.*--recursive\b', re.IGNORECASE), "rm --recursive --force (destructive recursive forced delete)"),
    (re.compile(r'\brm\s+-r\s+([/~]|\.(?:\s|$)|\$HOME)', re.IGNORECASE), "rm -r on broad path (/, ~, $HOME, .)"),
    (re.compile(r'\bmkfs\b', re.IGNORECASE), "mkfs (format filesystem)"),
    (re.compile(r'\bdd\s+.*\bif=.*\bof=/dev/', re.IGNORECASE), "dd raw disk write"),
    (re.compile(r'\bgit\s+reset\s+--hard\b', re.IGNORECASE), "git reset --hard (discards uncommitted work)"),
    (re.compile(r'\bgit\s+push\s+--force(?!-with-lease)\b', re.IGNORECASE), "git push --force (rewrites remote history)"),
    (re.compile(r'\bgit\s+push\s+-f\b', re.IGNORECASE), "git push -f (rewrites remote history)"),
    (re.compile(r'\bgit\s+clean\s+(-fd|-df)\b', re.IGNORECASE), "git clean -fd (deletes untracked files and dirs)"),
    (re.compile(r'\bgit\s+clean\s+-f\b', re.IGNORECASE), "git clean -f (deletes untracked files)"),
    (re.compile(r'\bDROP\s+TABLE\b', re.IGNORECASE), "DROP TABLE (destroys database table)"),
    (re.compile(r'\bDROP\s+DATABASE\b', re.IGNORECASE), "DROP DATABASE (destroys entire database)"),
    (re.compile(r'\bTRUNCATE\s+TABLE\b', re.IGNORECASE), "TRUNCATE TABLE (removes all table rows)"),
    (re.compile(r'\bgit\s+(?:[^\s]+\s+)*--no-verify\b', re.IGNORECASE), "git --no-verify (skips pre-commit / pre-push hooks; NON-NEGOTIABLE per git-workflow.md)"),
    (re.compile(r'\bgit\s+(?:[^\s]+\s+)*--no-gpg-sign\b', re.IGNORECASE), "git --no-gpg-sign (bypasses commit signing; NON-NEGOTIABLE per git-workflow.md)"),
    (re.compile(r"\bgit\s+-c\s+['\"]?commit\.gpgsign=['\"]?false['\"]?(?!\w)", re.IGNORECASE), "git -c commit.gpgsign=false (bypasses commit signing; NON-NEGOTIABLE per git-workflow.md)"),
]

def find_destructive_pattern(command: str) -> str | None:
    for pattern_regex, pattern_description in DESTRUCTIVE_BASH_PATTERNS:
        if pattern_regex.search(command):
            return pattern_description
    return None


def find_redirected_gh_pattern(command: str) -> str | None:
    redirected_gh_bash_patterns = [
        (re.compile(r'\bgh\s+api\b.*/(comments|reviews)\b.*-X\s+POST', re.IGNORECASE), "gh api comment/review POST"),
        (re.compile(r'\bgh\s+pr\s+comment\b', re.IGNORECASE), "gh pr comment"),
        (re.compile(r'\bgh\s+pr\s+review\b', re.IGNORECASE), "gh pr review"),
        (re.compile(r'\bgh\s+issue\s+comment\b', re.IGNORECASE), "gh issue comment"),
    ]
    for pattern_regex, pattern_description in redirected_gh_bash_patterns:
        if pattern_regex.search(command):
            return pattern_description
    return None


def _append_destructive_gate_log_entry(brief_label: str, full_reason: str) -> None:
    destructive_gate_log_path = Path.home() / ".claude" / "logs" / "destructive-gate.log"
    try:
        destructive_gate_log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp_iso = datetime.datetime.now().isoformat()
        log_entry = f"{timestamp_iso}\t{brief_label}\t{full_reason}\n"
        with destructive_gate_log_path.open("a", encoding="utf-8") as log_handle:
            log_handle.write(log_entry)
    except OSError:
        pass


def _build_silent_gh_deny_response(matched_description: str) -> dict:
    gh_gate_user_facing_prefix = "[gh-gate]"
    brief_label = f"blocked redirected {matched_description}"
    full_reason = (
        f"GH-REDIRECT GATE: {matched_description} already executed by "
        "gh-wsl-to-windows-redirect.py via PowerShell. Denying the original "
        "Bash call prevents duplicate execution."
    )
    _append_destructive_gate_log_entry(brief_label, full_reason)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": full_reason,
        },
        "suppressOutput": True,
        "systemMessage": f"{gh_gate_user_facing_prefix} {brief_label}",
    }


def _path_is_bare_ephemeral_root(resolved_path: str) -> bool:
    leading_repeated_slash_pattern = re.compile(r"^/{2,}")
    forward_slash_normalized_path = leading_repeated_slash_pattern.sub(
        "/",
        resolved_path.replace("\\", "/").lower().rstrip("/"),
    )
    system_temporary_root = leading_repeated_slash_pattern.sub(
        "/",
        os.path.normpath(tempfile.gettempdir()).replace("\\", "/").lower().rstrip("/"),
    )
    forbidden_bare_ephemeral_roots = {"/tmp", "/temp", "/worktrees", "/worktree", system_temporary_root}
    return forward_slash_normalized_path in forbidden_bare_ephemeral_roots


def _path_is_bare_named_worktrees_container(resolved_path: str) -> bool:
    return Path(resolved_path).name.lower() in ("worktrees", "worktree")


def _path_basename_is_shell_glob_wildcard(resolved_path: str) -> bool:
    bracket_class_empty_length = len("[]")
    basename = Path(resolved_path).name
    if not basename:
        return False
    if basename in ("*", "?"):
        return True
    if basename.startswith("[") and basename.endswith("]") and len(basename) > bracket_class_empty_length:
        return True
    if "*" in basename or "?" in basename:
        return True
    return False


def _command_contains_windows_style_path(command: str) -> bool:
    windows_drive_path_pattern = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:\\")
    windows_unc_path_pattern = re.compile(r"(?<!\S)\\\\[^\s\\]+\\[^\s\\]+")
    return bool(
        windows_drive_path_pattern.search(command)
        or windows_unc_path_pattern.search(command)
    )


def _split_command_preserving_windows_backslashes(command: str) -> list[str]:
    """Tokenize a command, normalizing Windows backslashes while preserving the find terminator.

    Plain POSIX ``shlex.split`` unescapes a ``\\;`` find action terminator to a
    standalone ``;`` token. When the command carries Windows backslashes, the global
    backslash-to-forward-slash normalization would otherwise rewrite that ``\\;`` to
    ``/;`` and bury the terminator inside a data token. The find action terminator is
    restored to a standalone ``;`` token before the normalization so action slicing and
    target collection see the same terminator on both platforms.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        The shlex tokens of the command.
    """
    if "\\" in command and (
        os.name == "nt" or _command_contains_windows_style_path(command)
    ):
        find_terminator_preserved_command = re.sub(r"\\;", " ; ", command)
        forward_slash_normalized_command = find_terminator_preserved_command.replace("\\", "/")
        return shlex.split(forward_slash_normalized_command)
    return shlex.split(command)


def _rm_flags_before_double_dash_are_unsafe(tokens_after_rm: list[str]) -> bool:
    safe_long_options = frozenset({
        "--recursive",
        "--force",
        "--verbose",
        "--interactive",
        "--dir",
    })
    for each_token in tokens_after_rm:
        if each_token == "--":
            return False
        if not each_token.startswith("-"):
            continue
        if "=" in each_token:
            return True
        if each_token.startswith("--"):
            if each_token not in safe_long_options:
                return True
            continue
        short_rest = each_token[1:]
        if not short_rest or not all(c in "rfRvidI" for c in short_rest):
            return True
    return False


def _collect_rm_target_tokens(tokens_after_rm: list[str]) -> list[str]:
    targets: list[str] = []
    has_seen_end_of_options = False
    for each_token in tokens_after_rm:
        if not has_seen_end_of_options and each_token == "--":
            has_seen_end_of_options = True
            continue
        if not has_seen_end_of_options and each_token.startswith("-"):
            continue
        targets.append(each_token)
    return targets


def rm_targets_only_ephemeral_paths(command: str) -> bool:
    """Return True when command is a single rm invocation whose every target is inside an ephemeral directory.

    Refuses compound commands so operators like && / || / ; / | / backticks /
    $(...) cannot piggy-back non-rm work on the ephemeral auto-allow. Refuses an
    output redirection (``rm -rf /tmp/x>/etc/passwd`` truncates ``/etc/passwd``
    even though the deletion targets an ephemeral path; shlex keeps the ``>`` glued
    to the target token when no whitespace separates them). Rejects bare ephemeral
    roots (/tmp, system temp dir) and bare directories named worktrees/worktree so
    we never auto-approve wiping those roots. Only allows common short flags and a
    small set of long options before ``--``; tokens with ``=`` or unknown long
    options disable auto-allow.
    """
    compound_shell_operator_pattern = re.compile(r'(?:&&|\|\||;|\||`|\$\()')
    if compound_shell_operator_pattern.search(command):
        return False
    try:
        all_command_tokens = _split_command_preserving_windows_backslashes(command)
    except ValueError:
        return False
    if _segment_redirects_output_to_a_file(all_command_tokens):
        return False
    if len(all_command_tokens) < 2 or all_command_tokens[0] != "rm":
        return False
    tokens_after_rm = all_command_tokens[1:]
    if _rm_flags_before_double_dash_are_unsafe(tokens_after_rm):
        return False
    all_target_tokens = _collect_rm_target_tokens(tokens_after_rm)
    if not all_target_tokens:
        return False
    for each_target_token in all_target_tokens:
        each_resolved_path = os.path.normpath(os.path.expanduser(each_target_token))
        if _path_basename_is_shell_glob_wildcard(each_resolved_path):
            return False
        if _path_is_bare_ephemeral_root(each_resolved_path):
            return False
        if _path_is_bare_named_worktrees_container(each_resolved_path):
            return False
        if not directory_is_ephemeral(each_resolved_path):
            return False
    return True


def _destructive_match_is_rm_family(matched_description: str) -> bool:
    """Return True when the matched destructive pattern is one of the rm-family deletes.

    The rm-family descriptions all begin with the same prefix; the compound
    ephemeral auto-allow and the quoted-mention guard act only on these, never on
    git, database, or device patterns.

    Args:
        matched_description: A description from DESTRUCTIVE_BASH_PATTERNS.

    Returns:
        True when the description names an rm deletion.
    """
    rm_family_description_prefix = "rm "
    return matched_description.startswith(rm_family_description_prefix)


def _command_contains_shell_expansion(command: str) -> bool:
    """Return True when the command contains shell parameter or command expansion.

    Any ``$`` (variable reference or ``$(...)`` command substitution) or backtick
    subshell means a token could expand at runtime to ``rm`` or to an arbitrary
    destructive command that the hook cannot resolve statically. The quoted-mention
    guard and the compound ephemeral auto-allow both fail closed on this so they
    never grant on a command whose effective program list is unknown until the
    shell runs.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when the command contains a ``$`` or backtick expansion character.
    """
    return "$" in command or "`" in command


def _split_tokens_into_shell_segments(all_command_tokens: list[str]) -> list[list[str]]:
    """Split a shlex token list into simple-command segments on control operators.

    Segments are delimited by ``&&``, ``||``, ``;``, ``|&``, ``|`` and ``&`` tokens,
    so each returned segment is one simple command. Operators that are not whitespace
    separated stay inside one shlex token and therefore inside one segment; that
    segment fails the absolute-ephemeral target check and the command falls through
    to the prompt.

    Args:
        all_command_tokens: Tokens produced by shlex tokenization.

    Returns:
        A list of segments, each a list of tokens with operators removed.
    """
    all_segments: list[list[str]] = []
    current_segment: list[str] = []
    for each_token in all_command_tokens:
        if each_token in ALL_SHELL_CONTROL_OPERATOR_TOKENS:
            all_segments.append(current_segment)
            current_segment = []
            continue
        current_segment.append(each_token)
    all_segments.append(current_segment)
    return all_segments


def _leading_command_token(all_command_tokens: list[str]) -> str | None:
    """Return the program token that leads the command, skipping VAR=value prefixes.

    A shell command may begin with one or more ``NAME=value`` environment
    assignments (``FOO=bar rm -rf x``); the first token that is not such an
    assignment is the program the shell executes. Returns None when every token is
    an assignment or the list is empty.

    Args:
        all_command_tokens: Tokens produced by shlex tokenization.

    Returns:
        The leading program token, or None when there is no program token.
    """
    leading_assignment_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
    for each_token in all_command_tokens:
        if leading_assignment_pattern.match(each_token):
            continue
        return each_token
    return None


def _strip_leading_launcher_wrapper(all_command_tokens: list[str]) -> list[str] | None:
    """Return the tokens after a leading command-launcher wrapper, or None when absent.

    A pure launcher wrapper (``timeout``, ``nohup``, ``nice``, ``ionice``,
    ``stdbuf``, ``time``, ``setsid``, ``chrt``, ``taskset``) forwards a trailing
    command line to another program without itself executing a quoted string. To
    find that real program, the launcher token and its own option tokens are
    dropped: leading ``VAR=value`` assignments are skipped, the launcher token is
    consumed, then option tokens are consumed until the first token that names a
    program. A launcher option that takes a SEPARATE argument value
    (``timeout -s SIGNAL`` / ``--signal SIGNAL``, ``timeout -k DURATION`` /
    ``--kill-after DURATION``, ``nice -n PRIORITY``) consumes both the flag and the
    following value token, so a signal name such as ``KILL`` is never mistaken for
    the wrapped program. Every dash-prefixed flag is consumed as well.

    The first positional token after the launcher and its flags is its required
    value for the launchers that take one (``timeout`` duration, ``chrt`` priority,
    ``taskset`` CPU mask or CPU range) and is consumed before the wrapped program. A
    value matching the known shapes (decimal with optional unit suffix, hexadecimal
    mask, CPU range/list) is consumed for any launcher. A launcher in
    ALL_LAUNCHERS_REQUIRING_A_POSITIONAL_VALUE consumes its first positional even when
    that value's shape is unrecognized (``timeout inf``, ``timeout 100ms``), so an
    unrecognized duration never masks the wrapped program by being returned as the
    program itself. A launcher that takes no positional value (``nohup``, ``time``,
    ``setsid``, ``ionice``, ``nice``, ``stdbuf``) returns its first positional as the
    wrapped program. Returns None when the leading program is not a launcher wrapper.

    A leading subshell or brace grouping character glued to the launcher token is
    stripped before the launcher is identified, so ``(timeout N bash -c '...')``
    resolves to its wrapped program.

    Args:
        all_command_tokens: Tokens of one shell segment.

    Returns:
        The tokens beginning at the wrapped program, an empty list when no program
        follows the launcher value, or None when no launcher leads.
    """
    leading_assignment_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
    launcher_positional_value_pattern = re.compile(LAUNCHER_POSITIONAL_VALUE_SHAPE_PATTERN)
    first_program_index = next(
        (
            index
            for index, token in enumerate(all_command_tokens)
            if not leading_assignment_pattern.match(token)
        ),
        None,
    )
    if first_program_index is None:
        return None
    leading_command_basename = Path(_strip_leading_subshell_grouping_characters(all_command_tokens[first_program_index])).name.lower()
    if leading_command_basename not in ALL_COMMAND_LAUNCHER_WRAPPER_COMMANDS:
        return None
    launcher_requires_a_positional_value = (
        leading_command_basename in ALL_LAUNCHERS_REQUIRING_A_POSITIONAL_VALUE
    )
    each_index = first_program_index + 1
    has_consumed_required_positional_value = False
    skip_next_token_as_option_value = False
    while each_index < len(all_command_tokens):
        each_token = all_command_tokens[each_index]
        if skip_next_token_as_option_value:
            skip_next_token_as_option_value = False
            each_index += 1
            continue
        if each_token in ALL_LAUNCHER_OPTIONS_TAKING_SEPARATE_VALUE:
            skip_next_token_as_option_value = True
            each_index += 1
            continue
        if each_token.startswith("-"):
            each_index += 1
            continue
        each_basename = Path(each_token).name.lower()
        if launcher_positional_value_pattern.match(each_basename):
            has_consumed_required_positional_value = True
            each_index += 1
            continue
        if launcher_requires_a_positional_value and not has_consumed_required_positional_value:
            has_consumed_required_positional_value = True
            each_index += 1
            continue
        return all_command_tokens[each_index:]
    return []


def _find_exec_action_program_token_lists(all_segment_tokens: list[str]) -> list[list[str]]:
    """Return the program-token list of each ``find`` ``-exec``/``-execdir`` action.

    A ``find ... -exec <program> <args...> ;`` (or ``-execdir``, or a ``+``
    terminator) action runs ``<program> <args...>`` against the matched files, so the
    program tokens are every token after the action flag up to the next ``;`` or ``+``
    terminator. One ``find`` may carry several such actions, so every action's program
    tokens are collected. An action flag with no following program tokens before its
    terminator (or before the token list ends) contributes nothing.

    Args:
        all_segment_tokens: The tokens of a single shell segment.

    Returns:
        One program-token list per ``-exec``/``-execdir`` action that has program
        tokens, in the order the actions appear.
    """
    all_action_program_token_lists: list[list[str]] = []
    each_token_index = 0
    while each_token_index < len(all_segment_tokens):
        if all_segment_tokens[each_token_index] not in ALL_FIND_EXEC_ACTION_FLAGS:
            each_token_index += 1
            continue
        each_program_token_index = each_token_index + 1
        current_action_program_tokens: list[str] = []
        while (
            each_program_token_index < len(all_segment_tokens)
            and all_segment_tokens[each_program_token_index] not in ALL_FIND_EXEC_ACTION_TERMINATORS
        ):
            current_action_program_tokens.append(all_segment_tokens[each_program_token_index])
            each_program_token_index += 1
        if current_action_program_tokens:
            all_action_program_token_lists.append(current_action_program_tokens)
        each_token_index = each_program_token_index + 1
    return all_action_program_token_lists


def _command_executes_a_string_argument(all_command_tokens: list[str]) -> bool:
    """Return True when the command's leading program runs a string argument as code.

    Shell interpreters and wrappers (``bash``, ``sh``, ``eval``, ``sudo``,
    ``xargs`` and the rest of ALL_INTERPRETER_AND_WRAPPER_COMMANDS) and remote
    runners such as ``ssh`` execute a following quoted token as a command line, so
    ``bash -c 'rm -rf /etc'`` and ``ssh host 'rm -rf /etc'`` run ``rm`` even though
    no token's basename is ``rm``. Language interpreters (``python``, ``perl``,
    ``ruby``, ``node`` and the rest of ALL_REMOTE_AND_PROGRAM_STRING_EXECUTORS) run
    a string only with a ``-c`` or ``-e`` flag, so those qualify only when such a
    flag is present.

    A pure command-launcher wrapper (``timeout``, ``nohup``, ``nice`` and the rest
    of ALL_COMMAND_LAUNCHER_WRAPPER_COMMANDS) does not run a quoted string itself but
    forwards argv to a following program, so a ``timeout`` in front of
    ``bash -c 'rm -rf /etc'`` runs ``rm`` through the wrapped ``bash``. The wrapper
    and its own flags are stripped and the wrapped program is re-evaluated,
    recursively through stacked wrappers, so a launcher in front of an interpreter is
    caught while a launcher in front of a plain program (a ``timeout`` in front of
    ``rm -rf /tmp/scratch``) still reports False and reaches the legitimate-mention
    path.

    A leading subshell ``(`` or brace ``{`` grouping character glued to the program
    token is stripped before the program is identified, so ``(bash -c 'rm -rf /etc')``
    and ``(timeout N bash -c 'rm -rf /etc')`` are caught.

    A leading ``find`` runs each ``-exec``/``-execdir`` action's program against the
    matched files, so each action's program tokens are re-evaluated through this same
    detection: ``find . -exec bash -c 'rm -rf /etc' ;`` and
    ``find . -exec python -c '...' ;`` are caught because the action runs an
    interpreter on a quoted string, while ``find . -exec rm -rf {} +`` reports False
    because the action's program ``rm`` executes no quoted string.

    Args:
        all_command_tokens: Tokens produced by shlex tokenization.

    Returns:
        True when the leading program executes a quoted string argument as code.
    """
    leading_command_token = _leading_command_token(all_command_tokens)
    if leading_command_token is None:
        return False
    leading_command_basename = Path(_strip_leading_subshell_grouping_characters(leading_command_token)).name.lower()
    if leading_command_basename in ALL_INTERPRETER_AND_WRAPPER_COMMANDS:
        return True
    if leading_command_basename in ALL_COMMAND_LAUNCHER_WRAPPER_COMMANDS:
        wrapped_program_tokens = _strip_leading_launcher_wrapper(all_command_tokens)
        if not wrapped_program_tokens:
            return False
        return _command_executes_a_string_argument(wrapped_program_tokens)
    if leading_command_basename == FIND_PROGRAM_NAME:
        return any(
            _command_executes_a_string_argument(each_action_program_tokens)
            for each_action_program_tokens in _find_exec_action_program_token_lists(all_command_tokens)
        )
    if leading_command_basename not in ALL_REMOTE_AND_PROGRAM_STRING_EXECUTORS:
        return False
    if leading_command_basename == "ssh":
        return True
    return any(
        each_token in ALL_STRING_ARGUMENT_EXECUTION_FLAGS for each_token in all_command_tokens
    )


def _explode_glued_shell_control_operators(all_command_tokens: list[str]) -> list[str]:
    """Split control operators off shlex tokens that glue them to a program name.

    shlex keeps a control operator joined to an adjacent program when no whitespace
    separates them, so ``true; eval 'x'`` tokenizes to ``['true;', 'eval', 'x']``
    with the ``;`` hidden inside ``true;``. This re-splits each token on the
    unquoted control operators ``&&`` / ``||`` / ``;`` / ``|&`` / ``|`` / ``&`` and
    on the POSIX command terminators newline and carriage return, so the operator
    becomes its own token and segment boundaries are visible. The ``|&`` pipe (stdout
    and stderr both into the next command) is matched before the single ``|`` so a
    glued ``cat foo|&tee x`` splits on ``|&`` rather than leaving ``&tee`` joined. The
    lone background ``&`` is split only when it neighbors no ``>`` redirection
    character, so a file-descriptor duplication such as a stderr-to-stdout redirect
    stays one token and is left for the redirection guard rather than torn into a
    dangling redirect fragment that would misread as a hidden segment boundary. shlex
    has already removed quoting, so any operator character still present in a token
    came from unquoted shell source and is a real boundary.

    Args:
        all_command_tokens: Tokens produced by shlex tokenization.

    Returns:
        Tokens with glued control operators separated into standalone tokens.
    """
    control_operator_split_pattern = re.compile(r"(&&|\|\||;|\|&|\||(?<!>)&(?!>)|\n|\r)")
    all_exploded_tokens: list[str] = []
    for each_token in all_command_tokens:
        for each_fragment in control_operator_split_pattern.split(each_token):
            if each_fragment:
                all_exploded_tokens.append(each_fragment)
    return all_exploded_tokens


def _strip_leading_subshell_grouping_characters(token: str) -> str:
    """Return a token with leading subshell-grouping characters removed.

    shlex keeps a subshell ``(`` or brace-group ``{`` joined to an adjacent program
    when no whitespace separates them, so ``(rm -rf /etc)`` tokenizes to
    ``['(rm', '-rf', '/etc)']`` with the ``(`` hidden inside ``(rm``. Stripping the
    leading grouping characters exposes the real program name (``rm``) so the
    rm-detection check sees it. shlex has already removed quoting, so any grouping
    character still present came from unquoted shell source.

    Args:
        token: One token produced by shlex tokenization.

    Returns:
        The token with leading ``(`` and ``{`` characters removed.
    """
    return token.lstrip(ALL_SUBSHELL_GROUPING_CHARACTERS)


def _any_shell_segment_executes_a_string_argument(all_command_tokens: list[str]) -> bool:
    """Return True when any shell segment's leading program runs a string as code.

    A ``find`` ``\\;`` action terminator tokenizes to a bare ``;``, which the
    segment splitter treats as a command separator, so a second
    ``-exec <interpreter> -c '...'`` action becomes its own segment whose leader is
    ``-exec`` — a leader no detector recognizes. Each ``find`` ``-exec``/``-execdir``
    action's program tokens are therefore scanned first on the full pre-split token
    list (where the ``;``/``+`` terminators are still standalone), so a buried
    ``find . -exec touch {} ; -exec bash -c 'rm -rf /etc' ;`` action is caught before
    the per-segment loop runs.

    Splits the command into simple-command segments on ``&&`` / ``||`` / ``;`` /
    ``|`` / ``&`` and applies the leading-program string-execution check to each.
    A benign program leading the whole command (``echo hi && bash -c 'rm -rf /etc'``,
    ``true; eval 'rm -rf /etc'``) must not mask an interpreter that runs the
    destructive ``rm`` inside a later segment, so every segment is inspected rather
    than only the command's first program. Control operators glued to a program by
    missing whitespace are separated first so those segment boundaries are seen.

    Args:
        all_command_tokens: Tokens produced by shlex tokenization.

    Returns:
        True when at least one segment's leading program executes a quoted string
        argument as code.
    """
    if any(
        _command_executes_a_string_argument(each_action_program_tokens)
        for each_action_program_tokens in _find_exec_action_program_token_lists(all_command_tokens)
    ):
        return True
    all_exploded_tokens = _explode_glued_shell_control_operators(all_command_tokens)
    for each_segment in _split_tokens_into_shell_segments(all_exploded_tokens):
        if each_segment and _command_executes_a_string_argument(each_segment):
            return True
    return False


def _command_executes_a_string_in_any_segment(command: str) -> bool:
    """Return True when any segment of any physical line runs a quoted string as code.

    Splits the command on the POSIX newline and carriage-return terminators,
    tokenizes each line preserving Windows paths, and reports whether any shell
    segment's leading program executes a quoted string argument as code
    (``bash -c '...'``, ``eval '...'``, ``ssh host '...'``, ``python -c '...'``, or a
    launcher wrapping any of these). The broad ephemeral-cwd auto-allow declines such
    a command because the executed string can delete a path outside the ephemeral
    working directory that no plain token names. Fails closed (returns True) when a
    line cannot be tokenized.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when at least one segment executes a quoted string argument as code.
    """
    for each_command_line in re.split(r"[\n\r]+", command):
        try:
            all_command_tokens = _split_command_preserving_windows_backslashes(each_command_line)
        except ValueError:
            return True
        if _any_shell_segment_executes_a_string_argument(all_command_tokens):
            return True
    return False


def command_has_no_real_rm_invocation(command: str) -> bool:
    """Return True when no shell token in the command actually invokes ``rm``.

    Distinguishes a destructive-pattern match that lands inside a quoted string
    argument (``grep 'rm -rf foo' log``, ``echo "rm -rf x"``,
    ``git commit -m "rm -rf cleanup"``) from a command that runs ``rm``. A quoted
    mention tokenizes to a single token whose path basename is not ``rm``, so it is
    reported as having no real invocation and the spurious ``rm`` prompt is
    suppressed.

    Fails closed (returns False, meaning "treat as a real invocation, keep
    prompting") when the command contains shell expansion (``$`` or backtick),
    where a token such as ``$RM`` could expand to ``rm``; when tokenization fails on
    unbalanced quotes; or when any shell segment's leading program executes a quoted
    string argument as code (``bash -c 'rm -rf /etc'``, ``eval 'rm -rf /etc'``,
    ``ssh host 'rm -rf /etc'``, ``awk 'BEGIN{system("rm -rf /etc")}'``,
    ``echo hi && bash -c 'rm -rf /etc'``, ``timeout bash -c 'rm -rf /etc'``), where
    the destructive ``rm`` rides inside an executed string rather than a passive
    mention. The command is split on the POSIX newline and carriage-return command
    terminators before tokenizing, because shlex treats those as whitespace and would
    otherwise merge a later-line interpreter (``echo safe`` newline
    ``bash -c 'rm -rf /etc'``) into the benign leading segment. The per-segment check
    means a benign leader on a line does not mask an interpreter later on that line.
    ``/bin/rm``, ``sudo rm`` and ``\\rm`` each tokenize to a token whose basename is
    ``rm`` and are correctly reported as real. Before the rm-detection scan, each
    token is split on glued control operators and stripped of leading subshell- and
    brace-grouping characters, so ``(rm -rf /etc)``, ``;rm -rf /etc`` and
    ``echo|rm -rf /etc`` expose ``rm`` as a real invocation rather than a passive
    mention.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when the command contains no real ``rm`` invocation.
    """
    if _command_contains_shell_expansion(command):
        return False
    all_physical_command_lines = re.split(r"[\n\r]+", command)
    for each_command_line in all_physical_command_lines:
        try:
            all_command_tokens = _split_command_preserving_windows_backslashes(each_command_line)
        except ValueError:
            return False
        if _any_shell_segment_executes_a_string_argument(all_command_tokens):
            return False
        all_operator_split_tokens = _explode_glued_shell_control_operators(all_command_tokens)
        for each_token in all_operator_split_tokens:
            each_program_token = _strip_leading_subshell_grouping_characters(each_token)
            if Path(each_program_token).name == "rm":
                return False
    return True


def _find_non_rm_destructive_pattern(command: str) -> str | None:
    """Return the first non-rm-family destructive pattern description, or None.

    Applied after the quoted-mention guard finds a matched rm-family pattern to be
    a false positive: the command is rescanned for any other destructive pattern
    (force push, git clean, mkfs, dd, DROP/TRUNCATE, signing bypass) so a real
    non-rm hazard riding alongside the quoted mention
    (``grep 'rm -rf' f && git push --force origin main``) still prompts.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        The description of the first matching non-rm-family pattern, or None.
    """
    for each_pattern_regex, each_pattern_description in DESTRUCTIVE_BASH_PATTERNS:
        if _destructive_match_is_rm_family(each_pattern_description):
            continue
        if each_pattern_regex.search(command):
            return each_pattern_description
    return None


def _find_non_force_push_destructive_hazard(command: str) -> str | None:
    """Return a destructive hazard riding alongside a convergence force-push, or None.

    Applied when a force-push to a convergence branch is being auto-allowed: the
    command is rescanned for any destructive pattern other than the force-push itself
    so a real co-resident hazard (``git push --force origin claude/x && git reset
    --hard``) still prompts. The force-push patterns are skipped because they are the
    very thing the convergence exemption grants. An rm-family pattern is skipped when
    it is only a quoted mention (``echo "rm -rf foo" && git push --force origin
    claude/x``), so a passive ``rm`` string does not re-block a legitimate push.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        The description of the first co-resident destructive hazard, or None.
    """
    for each_pattern_regex, each_pattern_description in DESTRUCTIVE_BASH_PATTERNS:
        if "git push" in each_pattern_description and (
            "force" in each_pattern_description or "-f" in each_pattern_description
        ):
            continue
        if not each_pattern_regex.search(command):
            continue
        if _destructive_match_is_rm_family(
            each_pattern_description
        ) and command_has_no_real_rm_invocation(command):
            continue
        return each_pattern_description
    return None


def _command_contains_non_rm_family_destructive_pattern(command: str) -> bool:
    """Return True when any destructive pattern in the command is not rm-family.

    The compound ephemeral auto-allow grants only when every destructive pattern
    present is an rm deletion. A git reset --hard, force push, git clean, mkfs, dd,
    or DROP/TRUNCATE riding inside the chain is not bounded by the ephemeral rm
    targets, so its presence declines the whole auto-allow.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when at least one matching destructive pattern is not rm-family.
    """
    for each_pattern_regex, each_pattern_description in DESTRUCTIVE_BASH_PATTERNS:
        if each_pattern_regex.search(command) and not _destructive_match_is_rm_family(
            each_pattern_description
        ):
            return True
    return False


def _rm_segment_targets_only_absolute_ephemeral_paths(all_rm_segment_tokens: list[str]) -> bool:
    """Return True when an ``rm`` segment's every target is an absolute ephemeral path.

    ``all_rm_segment_tokens`` is one shell segment beginning at its ``rm`` command
    token. Rejects the segment (returns False) when the segment carries an output
    redirection (``rm -rf /tmp/x>/etc/passwd`` truncates ``/etc/passwd`` even though
    the deletion targets an ephemeral path; shlex keeps the ``>`` glued to the target
    token when no whitespace separates them), when an unsafe flag precedes ``--``,
    when there are no targets, when a target is relative (the compound auto-allow
    refuses to resolve relative targets without a trusted working directory), when
    a target basename is a glob wildcard, when a target is a bare ephemeral root or
    a bare worktrees container, or when a target is not inside an ephemeral
    directory.

    Args:
        all_rm_segment_tokens: Shlex tokens of a single ``rm`` segment, the first
            token being the ``rm`` command.

    Returns:
        True when every target is an absolute ephemeral path safe to auto-allow.
    """
    if _segment_redirects_output_to_a_file(all_rm_segment_tokens):
        return False
    tokens_after_rm = all_rm_segment_tokens[1:]
    if _rm_flags_before_double_dash_are_unsafe(tokens_after_rm):
        return False
    all_target_tokens = _collect_rm_target_tokens(tokens_after_rm)
    if not all_target_tokens:
        return False
    for each_target_token in all_target_tokens:
        each_expanded_target = os.path.expanduser(each_target_token)
        each_is_absolute = (
            os.path.isabs(each_expanded_target)
            or each_expanded_target.replace("\\", "/").startswith("/")
        )
        if not each_is_absolute:
            return False
        each_resolved_target = os.path.normpath(each_expanded_target)
        if _path_basename_is_shell_glob_wildcard(each_resolved_target):
            return False
        if _path_is_bare_ephemeral_root(each_resolved_target):
            return False
        if _path_is_bare_named_worktrees_container(each_resolved_target):
            return False
        if not directory_is_ephemeral(each_resolved_target):
            return False
    return True


def _path_is_the_null_device(path_token: str) -> bool:
    """Return True when a path token names the null device (``/dev/null`` or ``nul``).

    Args:
        path_token: A redirect-target path token.

    Returns:
        True when the token names the null device.
    """
    return path_token.replace("\\", "/").rstrip("/").lower() in ("/dev/null", "nul")


def _segment_redirects_output_to_a_file(all_segment_tokens: list[str]) -> bool:
    """Return True when a segment writes its output to a file via shell redirection.

    An output redirection (a plain, appending, clobbering, or combined operator, with
    or without a leading file-descriptor number) truncates or rewrites the redirect
    target, so ``cat /dev/null > /etc/important.conf`` destroys the target file even
    though ``cat`` itself is read-only. A redirect whose target is the null device
    (``/dev/null`` or ``nul``) writes nothing and stays read-only, so it does not count;
    a redirect to any other file counts. A file-descriptor duplication that names another
    descriptor as its target writes no file and stays read-only. shlex keeps a
    redirect operator glued to an adjacent program or target token when no whitespace
    separates them (``echo pwned>/etc/passwd``, ``cat secret>/etc/x``), so each token is
    scanned for a redirect operator anywhere within it rather than tested for exact
    equality; the target is read from the same token after the operator, or from the next
    token when the operator ends its own token. The benign-segment check declines any
    segment carrying a redirect to a non-null file so a benign program that overwrites a
    non-ephemeral file does not ride the ephemeral ``rm`` auto-allow.

    Args:
        all_segment_tokens: Shlex tokens of one shell segment.

    Returns:
        True when any token contains a redirect to a file other than the null device.
    """
    output_redirection_pattern = re.compile(OUTPUT_REDIRECTION_OPERATOR_PATTERN)
    for each_index, each_token in enumerate(all_segment_tokens):
        operator_match = output_redirection_pattern.search(each_token)
        if operator_match is None:
            continue
        glued_redirect_target = each_token[operator_match.end():]
        if glued_redirect_target:
            redirect_target = glued_redirect_target
        elif each_index + 1 < len(all_segment_tokens):
            redirect_target = all_segment_tokens[each_index + 1]
        else:
            return True
        if _path_is_the_null_device(redirect_target):
            continue
        return True
    return False


def _all_positional_tokens_after_leader(all_segment_tokens: list[str]) -> list[str]:
    """Return the non-flag tokens that follow a segment's leading program.

    Skips leading ``VAR=value`` assignments, the program token itself, every
    dash-prefixed flag, and any ``key=value`` flag value, leaving the positional
    words that name a subcommand chain (``repo``, ``delete`` in ``gh repo delete``;
    ``stash``, ``drop`` in ``git stash drop``).

    Args:
        all_segment_tokens: Shlex tokens of one shell segment.

    Returns:
        The positional tokens after the leading program, in order.
    """
    leading_assignment_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
    first_program_index = next(
        (
            index
            for index, token in enumerate(all_segment_tokens)
            if not leading_assignment_pattern.match(token)
        ),
        None,
    )
    if first_program_index is None:
        return []
    return [
        each_token
        for each_token in all_segment_tokens[first_program_index + 1:]
        if not each_token.startswith("-") and "=" not in each_token
    ]


def _gh_segment_names_an_explicit_method(
    all_segment_tokens: list[str], target_method: str
) -> bool:
    """Return True when a ``gh`` segment explicitly names ``target_method``.

    Recognizes both ``gh`` flag spellings: the space-separated form where the flag
    (``-X``/``--method``) is its own token and the next token names the method
    (``-X GET``), and the glued forms where the method is inside the flag token
    (``-XGET``, ``--method=GET``). The match is case-insensitive against the
    already-uppercased ``target_method``.

    Args:
        all_segment_tokens: Shlex tokens of one shell segment.
        target_method: The HTTP method name to match, uppercased.

    Returns:
        True when an ``-X``/``--method`` flag names ``target_method``.
    """
    for each_index, each_token in enumerate(all_segment_tokens):
        if each_token.startswith(GH_SHORT_METHOD_FLAG_PREFIX):
            inline_method = each_token[len(GH_SHORT_METHOD_FLAG_PREFIX) :]
        elif each_token.startswith(GH_LONG_METHOD_FLAG_EQUALS_PREFIX):
            inline_method = each_token[len(GH_LONG_METHOD_FLAG_EQUALS_PREFIX) :]
        else:
            inline_method = ""
        if inline_method.upper() == target_method:
            return True
        if each_token not in ALL_GH_HTTP_WRITE_METHOD_FLAGS:
            continue
        each_next_index = each_index + 1
        if each_next_index < len(all_segment_tokens) and (
            all_segment_tokens[each_next_index].upper() == target_method
        ):
            return True
    return False


def _gh_segment_carries_a_request_body_field(all_segment_tokens: list[str]) -> bool:
    """Return True when a ``gh api`` segment adds a request-body field.

    ``gh api`` adds a parameter to the request body through ``-f``/``--raw-field``,
    ``-F``/``--field``, or ``--input``, each accepted as its own token (``-f title=x``,
    ``--field a=b``) or glued to its value (``-ftitle=x``, ``--field=a=b``,
    ``--input=body.json``).

    Args:
        all_segment_tokens: Shlex tokens of one shell segment.

    Returns:
        True when any token is a request-body field flag.
    """
    for each_token in all_segment_tokens:
        if each_token in ALL_GH_API_REQUEST_BODY_FIELD_FLAGS:
            return True
        if each_token.startswith(ALL_GH_API_GLUED_REQUEST_BODY_FIELD_FLAG_PREFIXES):
            return True
    return False


def _gh_segment_runs_an_http_write_method(all_segment_tokens: list[str]) -> bool:
    """Return True when a ``gh`` segment performs an HTTP write through ``gh api``.

    ``gh api`` reaches the GitHub API with whatever HTTP method an ``-X``/``--method``
    flag names. A GET is read-only, but POST, PUT, PATCH and DELETE mutate server
    state (``gh api repos/foo -X DELETE``). Both flag spellings are recognized: the
    space-separated form where the method is its own token (``-X DELETE``) and the
    glued forms where the method is inside the flag token (``-XDELETE``,
    ``--method=DELETE``). The method flag is dash-prefixed and so is dropped from the
    positional-token list the read-only check inspects, so the raw segment tokens are
    scanned here: when a write-method flag names a write method, the segment is
    reported as a write rather than a read.

    ``gh api`` also defaults the method to POST when any request-body field flag
    (``-f``/``--raw-field``, ``-F``/``--field``, ``--input``) is present and no explicit
    method is given, so a field-carrying segment that does not explicitly name GET
    (``gh api repos/foo -f title=x``) is an implicit-POST write. An explicit ``-X
    GET``/``--method GET`` keeps such a segment read-only.

    Args:
        all_segment_tokens: Shlex tokens of one shell segment.

    Returns:
        True when the segment names an HTTP write method via ``gh api``.
    """
    if any(
        _gh_segment_names_an_explicit_method(all_segment_tokens, each_write_method)
        for each_write_method in ALL_GH_HTTP_WRITE_METHODS
    ):
        return True
    if _gh_segment_carries_a_request_body_field(all_segment_tokens):
        return not _gh_segment_names_an_explicit_method(
            all_segment_tokens, GH_HTTP_READ_ONLY_METHOD
        )
    return False


def _git_fetch_segment_forces_a_local_ref_update(
    all_positional_tokens: list[str], all_segment_tokens: list[str]
) -> bool:
    """Return True when a ``git fetch`` segment force-updates a local ref.

    ``git fetch`` is read-only in normal use, but two spellings force-update the local
    destination ref even when the update is not a fast-forward, overwriting a local
    branch and discarding local commits. A ``+``-prefixed refspec forces only the refs
    it names: ``git fetch origin +refs/heads/main:refs/heads/main`` is detected from a
    positional refspec that begins with ``+`` or names a ``+refs/`` source. The ``-f``/
    ``--force`` flag forces every named refspec at once: ``git fetch --force origin
    refs/heads/main:refs/heads/main`` discards local ``main`` commits with no ``+`` in
    sight. The force flag is dash-prefixed and so is dropped from the positional-token
    list, so the raw segment tokens are scanned for it, mirroring how the ``gh api``
    write-method check scans raw tokens for ``-X``.

    Args:
        all_positional_tokens: The non-flag tokens after the leading ``git`` program.
        all_segment_tokens: Shlex tokens of the whole ``git`` segment.

    Returns:
        True when any positional refspec or a force flag force-updates a local ref.
    """
    if any(each_token in ALL_GIT_FETCH_FORCE_FLAGS for each_token in all_segment_tokens):
        return True
    return any(
        each_token.startswith("+") or "+refs/" in each_token
        for each_token in all_positional_tokens
    )


def _git_config_segment_runs_a_read_only_mode(all_segment_tokens: list[str]) -> bool:
    """Return True only when a ``git config`` segment carries a read-only mode flag.

    ``git config`` parses a read-only mode flag (``--get``/``--list``/``-l`` and the
    rest of ALL_GIT_CONFIG_READ_ONLY_FLAGS) only while it sits before the first
    positional key. Once a key positional appears (``git config core.editor ...``),
    every following dash-prefixed token is the value being set, so ``git config
    core.editor --get`` stores the literal string ``--get`` rather than querying.
    Reading the mode from the flags that precede the first key positional, rather
    than scanning the whole segment, keeps a value that happens to equal a read-only
    flag string from masking the write.

    Args:
        all_segment_tokens: Shlex tokens of the whole ``git config`` segment.

    Returns:
        True when a read-only flag precedes the first ``config`` key positional.
    """
    config_token_index = next(
        (
            each_index
            for each_index, each_token in enumerate(all_segment_tokens)
            if each_token.lower() == "config"
        ),
        None,
    )
    if config_token_index is None:
        return False
    for each_token in all_segment_tokens[config_token_index + 1:]:
        if not each_token.startswith("-"):
            return False
        if each_token in ALL_GIT_CONFIG_READ_ONLY_FLAGS:
            return True
    return False


def _git_segment_runs_a_mutating_mode(all_positional_tokens: list[str], all_segment_tokens: list[str]) -> bool:
    """Return True when a ``git config``, ``git remote`` or ``git fetch`` segment mutates state.

    ``config``, ``remote`` and ``fetch`` appear in the git read-only allowlist for their
    query modes (``git config --list``, ``git remote -v``, plain ``git fetch``) but each
    carries a write mode: ``git config key value`` and ``git config --global key value``
    set a value, ``git remote add|remove|rm|set-url`` change the remote table, and
    ``git fetch origin +refs/heads/main:refs/heads/main`` force-updates a local ref. A
    ``config`` segment mutates unless a read-only flag (``--get``/``--list`` and the rest
    of ALL_GIT_CONFIG_READ_ONLY_FLAGS) precedes the first positional key; a ``remote``
    segment mutates unless the first positional verb after ``remote`` is a read-only one
    (``show``, ``get-url``); a ``fetch`` segment mutates when it carries a ``+``-prefixed
    force refspec or a ``-f``/``--force`` flag. Both the config mode and the remote verb
    are read positionally rather
    than by scanning the whole segment for any read-only token, because a value that
    follows the key positional (``git config core.editor --get`` stores ``--get``) and a
    global ``-v``/``--verbose`` before a write verb (``git remote -v add evil url``) would
    otherwise let a read-only token anywhere mask the write.

    Args:
        all_positional_tokens: The non-flag tokens after the leading ``git`` program.
        all_segment_tokens: Shlex tokens of the whole ``git`` segment.

    Returns:
        True when the segment runs a mutating ``config``, ``remote`` or ``fetch`` mode.
    """
    all_lowercased_positional_tokens = [each_token.lower() for each_token in all_positional_tokens]
    if "config" in all_lowercased_positional_tokens:
        return not _git_config_segment_runs_a_read_only_mode(all_segment_tokens)
    if "remote" in all_lowercased_positional_tokens:
        remote_verb_index = all_lowercased_positional_tokens.index("remote") + 1
        all_remote_verbs = all_lowercased_positional_tokens[remote_verb_index:]
        if not all_remote_verbs:
            return False
        return all_remote_verbs[0] not in ALL_GIT_REMOTE_READ_ONLY_VERBS
    if "fetch" in all_lowercased_positional_tokens:
        return _git_fetch_segment_forces_a_local_ref_update(
            all_positional_tokens, all_segment_tokens
        )
    return False


def _subcommand_dispatching_segment_is_read_only(
    leading_program_basename: str,
    all_read_only_subcommands: frozenset[str],
    all_segment_tokens: list[str],
) -> bool:
    """Return True only when a subcommand-dispatching segment runs a read-only verb.

    ``git`` and ``gh`` dispatch destructive operations through subcommands the
    DESTRUCTIVE_BASH_PATTERNS table does not separately enumerate (``gh repo delete``,
    ``git checkout -- .``, ``git stash drop``, ``git branch -D``), so a chained
    destructive subcommand would otherwise ride the ephemeral ``rm`` auto-allow. The
    check fails closed: a segment is benign only when a read-only subcommand verb sits
    in the program's leading subcommand window and the segment runs no known mutating
    mode. The window spans the first positional for ``git`` (``git status``) and the
    first two positionals for ``gh`` (``gh api``, ``gh pr view``), matching how each
    program names its subcommand. Bounding the search to that window keeps a read-only
    verb used as a deeper argument to a destructive subcommand (``gh repo delete
    status``, ``git push origin log``, ``git branch -D log``) from satisfying the check.
    ``git config`` and ``git remote`` sit in the read-only allowlist for their query
    modes yet carry write modes (``git config --global key value``, ``git remote add
    evil url``), and ``gh api`` performs an HTTP write when an ``-X``/``--method`` flag
    names POST, PUT, PATCH or DELETE; each such mutating mode declines the segment.

    Args:
        leading_program_basename: The dispatching program (``git`` or ``gh``).
        all_read_only_subcommands: The read-only subcommand verbs for the dispatching
            program.
        all_segment_tokens: Shlex tokens of one shell segment.

    Returns:
        True when the segment's subcommand is on the read-only allowlist and the
        segment runs no mutating mode.
    """
    all_positional_tokens = _all_positional_tokens_after_leader(all_segment_tokens)
    subcommand_window_depth = (
        ALL_READ_ONLY_SUBCOMMAND_POSITION_DEPTHS_BY_DISPATCHING_PROGRAM[
            leading_program_basename
        ]
    )
    all_leading_subcommand_tokens = all_positional_tokens[:subcommand_window_depth]
    runs_a_read_only_subcommand = any(
        each_token.lower() in all_read_only_subcommands
        for each_token in all_leading_subcommand_tokens
    )
    if not runs_a_read_only_subcommand:
        return False
    if leading_program_basename == "git" and _git_segment_runs_a_mutating_mode(
        all_positional_tokens, all_segment_tokens
    ):
        return False
    if leading_program_basename == "gh" and _gh_segment_runs_an_http_write_method(
        all_segment_tokens
    ):
        return False
    return True


def _benign_program_writes_a_file_via_output_flag(
    leading_program_basename: str, all_segment_tokens: list[str]
) -> bool:
    """Return True when a benign program writes a file through its own output flag.

    Some allowlisted reporting commands overwrite an arbitrary file without a shell
    redirection: ``sort -o FILE`` truncates and rewrites ``FILE`` the same way
    ``cat ... > FILE`` does, so ``sort -o /etc/important.conf /etc/passwd`` destroys a
    non-ephemeral file even though ``sort`` is read-only by default. A segment whose
    leading program is in ALL_FILE_WRITING_OUTPUT_FLAGS_BY_BENIGN_PROGRAM and carries
    one of that program's file-writing output flags is reported as a write so it
    declines the ephemeral ``rm`` auto-allow.

    Args:
        leading_program_basename: The segment's leading program basename, lowercased.
        all_segment_tokens: Shlex tokens of one shell segment.

    Returns:
        True when the segment writes a file through the program's output flag.
    """
    all_file_writing_output_flags = ALL_FILE_WRITING_OUTPUT_FLAGS_BY_BENIGN_PROGRAM.get(
        leading_program_basename
    )
    if all_file_writing_output_flags is None:
        return False
    return any(
        each_token in all_file_writing_output_flags
        or each_token.split("=", 1)[0] in all_file_writing_output_flags
        for each_token in all_segment_tokens
    )


def _segment_leading_program_is_benign(all_segment_tokens: list[str]) -> bool:
    """Return True when a non-rm segment's leading program is a benign reporting command.

    A compound chain auto-allow requires every segment that is not an ``rm`` deletion
    to be a recognized read-only or reporting command (``echo``, ``gh``, ``head``,
    ``cat``, ``grep`` and the rest of ALL_BENIGN_COMPOUND_SEGMENT_COMMANDS). A segment
    leading with any other program — ``shred``, ``truncate``, ``find ... -delete``,
    ``chmod -R``, ``mv`` and every other destructive command absent from the
    DESTRUCTIVE_BASH_PATTERNS table — is treated as non-benign so the chain falls
    through to the prompt rather than riding the ephemeral ``rm`` auto-allow.

    Three further constraints fail the segment closed even when its leading program is
    allowlisted: an output redirection (``cat /dev/null > /etc/important.conf``)
    truncates the redirect target; a benign program that writes a file through its own
    output flag (``sort -o /etc/important.conf``) overwrites the named file without a
    shell redirection; and a ``git`` or ``gh`` segment must run a read-only subcommand
    in a read-only mode (``git status``, ``gh pr view``, ``git config --list``) rather
    than a destructive subcommand (``gh repo delete``, ``git checkout -- .``,
    ``git stash drop``) or a mutating mode of an otherwise-read-only subcommand
    (``git config --global key value``, ``git remote add evil url``, ``gh api -X
    DELETE``).

    Args:
        all_segment_tokens: Shlex tokens of one shell segment, possibly led by
            ``VAR=value`` assignments before the program token.

    Returns:
        True when the segment's leading program is in the benign allowlist.
    """
    leading_command_token = _leading_command_token(all_segment_tokens)
    if leading_command_token is None:
        return False
    leading_program_basename = Path(leading_command_token).name.lower()
    if leading_program_basename not in ALL_BENIGN_COMPOUND_SEGMENT_COMMANDS:
        return False
    if _segment_redirects_output_to_a_file(all_segment_tokens):
        return False
    if _benign_program_writes_a_file_via_output_flag(leading_program_basename, all_segment_tokens):
        return False
    all_read_only_subcommands = ALL_READ_ONLY_SUBCOMMANDS_BY_DISPATCHING_PROGRAM.get(
        leading_program_basename
    )
    if all_read_only_subcommands is not None:
        return _subcommand_dispatching_segment_is_read_only(
            leading_program_basename, all_read_only_subcommands, all_segment_tokens
        )
    return True


class CompoundSegmentVerdict(enum.Enum):
    """Auto-allow classification of one segment in a compound ``rm`` chain."""

    DECLINES_AUTO_ALLOW = enum.auto()
    IS_EPHEMERAL_RM = enum.auto()
    IS_BENIGN = enum.auto()


def _compound_segment_auto_allow_verdict(
    all_segment_tokens: list[str],
) -> CompoundSegmentVerdict:
    """Classify one compound-chain segment for the ephemeral ``rm`` auto-allow.

    Returns DECLINES_AUTO_ALLOW when the segment's leading program executes a quoted
    string argument as code, when an ``rm`` segment targets a non-ephemeral path, or
    when a non-``rm`` segment is not a benign reporting command. Returns
    IS_EPHEMERAL_RM when the segment is an ``rm`` deletion whose every target is an
    absolute ephemeral path. Returns IS_BENIGN for an empty segment or a benign
    non-``rm`` segment.

    Args:
        all_segment_tokens: Shlex tokens of one shell segment with control operators
            removed.

    Returns:
        The CompoundSegmentVerdict for the segment.
    """
    if not all_segment_tokens:
        return CompoundSegmentVerdict.IS_BENIGN
    if _command_executes_a_string_argument(all_segment_tokens):
        return CompoundSegmentVerdict.DECLINES_AUTO_ALLOW
    each_rm_token_index = next(
        (
            index
            for index, token in enumerate(all_segment_tokens)
            if Path(_strip_leading_subshell_grouping_characters(token)).name == "rm"
        ),
        None,
    )
    if each_rm_token_index is None:
        if _segment_leading_program_is_benign(all_segment_tokens):
            return CompoundSegmentVerdict.IS_BENIGN
        return CompoundSegmentVerdict.DECLINES_AUTO_ALLOW
    if _rm_segment_targets_only_absolute_ephemeral_paths(
        all_segment_tokens[each_rm_token_index:]
    ):
        return CompoundSegmentVerdict.IS_EPHEMERAL_RM
    return CompoundSegmentVerdict.DECLINES_AUTO_ALLOW


def rm_compound_targets_only_absolute_ephemeral_paths(command: str) -> bool:
    """Return True when a compound command's every ``rm`` segment is safe to auto-allow.

    Handles destructive cleanup chains that declare no ephemeral working directory,
    such as ``rm -rf /tmp/pr136 /tmp/difftest && echo 'cleaned'``. Splits the
    command into shell segments and requires all of: at least one segment runs
    ``rm``; every ``rm`` segment targets only absolute ephemeral paths; every
    non-``rm`` segment leads with a benign reporting command from
    ALL_BENIGN_COMPOUND_SEGMENT_COMMANDS, so a ``shred``, ``truncate``,
    ``find ... -delete``, ``chmod -R`` or ``mv`` segment that destroys
    non-ephemeral data declines the auto-allow; no segment's leading program
    executes a quoted string argument as code — a shell interpreter, ``eval``,
    ``exec``, ``source``, a privilege or argument wrapper (``sudo``, ``su``,
    ``env``, ``xargs``), or a command-launcher wrapper that forwards argv to such a
    program (``timeout bash -c '...'``); no segment matches a destructive pattern
    that is not rm-family (force push, git clean, git reset --hard, mkfs, dd,
    DROP/TRUNCATE, signing bypass); and the command contains no shell expansion.

    Fails closed (returns False) on shell expansion (``$`` or backtick), on a
    tokenization error, and whenever any ``rm`` segment fails the absolute-ephemeral
    target check, so the compound auto-allow grants only on chains it can fully
    bound.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when every ``rm`` segment targets only absolute ephemeral paths and no
        other hazard is present.
    """
    if _command_contains_shell_expansion(command):
        return False
    if _command_contains_non_rm_family_destructive_pattern(command):
        return False
    has_seen_rm_segment = False
    for each_command_line in re.split(r"[\n\r]+", command):
        try:
            all_command_tokens = _split_command_preserving_windows_backslashes(each_command_line)
        except ValueError:
            return False
        all_operator_split_tokens = _explode_glued_shell_control_operators(all_command_tokens)
        for each_segment in _split_tokens_into_shell_segments(all_operator_split_tokens):
            each_verdict = _compound_segment_auto_allow_verdict(each_segment)
            if each_verdict == CompoundSegmentVerdict.DECLINES_AUTO_ALLOW:
                return False
            if each_verdict == CompoundSegmentVerdict.IS_EPHEMERAL_RM:
                has_seen_rm_segment = True
    return has_seen_rm_segment


def targets_only_claude_directory(command: str) -> bool:
    """Check if rm command targets only paths under ~/.claude/."""
    all_rm_target_paths = re.findall(
        r'(?:rm\s+(?:-\w+\s+)*)("[^"]+"|\'[^\']+\'|\S+)',
        command,
    )
    if not all_rm_target_paths:
        return False

    for each_raw_path in all_rm_target_paths:
        each_stripped_path = each_raw_path.strip("\"'")
        each_cleaned_path = re.split(r'[;&|]', each_stripped_path)[0]
        if each_cleaned_path != each_stripped_path:
            return False
        each_resolved_path = os.path.normpath(os.path.expanduser(each_cleaned_path))
        if not each_resolved_path.startswith(CLAUDE_DIRECTORY_PATH):
            return False

    return True


def _ephemeral_recursive_rm_auto_allow_granted(command: str, matched_description: str) -> bool:
    return matched_description.startswith(("rm -rf", "rm --recursive")) and rm_targets_only_ephemeral_paths(command)


def _extract_leading_cd_target(command: str) -> str | None:
    """Return the target of a ``cd`` that starts the command, or None if absent.

    Uses ``shlex.split`` with POSIX rules to tokenize the command so adjacent
    quoted string concatenation (``"/tmp/a""/../../etc"``) resolves to the
    same path the shell would cd to (``/tmp/a/../../etc``). A regex-based
    extractor cannot see past the first quoted segment and would
    misclassify the cd target as ephemeral while the shell ends up
    somewhere else entirely.

    Returns None when the command does not start with ``cd``, when tokenization
    fails (unbalanced quotes), when the cd target is missing, or when the
    target contains any shell-expansion character (``$`` for variable /
    command substitution, `` ` `` for backtick subshell) that the shell
    would resolve *before* cd runs. Hook authors cannot safely know what
    ``$(rm -rf ~)`` expands to, so the conservative answer is "don't
    auto-allow".
    """
    shell_expansion_characters_that_execute_code = ("$", "`")
    try:
        all_command_tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    if len(all_command_tokens) < 2 or all_command_tokens[0] != "cd":
        return None
    cd_target_token = all_command_tokens[1]
    for each_shell_expansion_character in shell_expansion_characters_that_execute_code:
        if each_shell_expansion_character in cd_target_token:
            return None
    return cd_target_token


def _resolve_declared_effective_working_directory(command: str, tool_input: dict) -> str | None:
    """Return the declared cwd for the command, or None when none is declared.

    Precedence: leading ``cd "X"`` in the command, then the
    ``tool_input['cwd']`` field passed in by the Bash tool call. Returns
    None when neither source is present so the broad auto-allow gate never
    depends on the hook process's own ``os.getcwd()`` (which can itself be
    ephemeral when Claude Code runs inside a worktree, and would otherwise
    auto-allow every destructive command). Paths are user-expanded and
    normalized so downstream ``directory_is_ephemeral`` comparisons see a
    canonical form on both POSIX and Windows.
    """
    leading_cd_target = _extract_leading_cd_target(command)
    if leading_cd_target is not None:
        return os.path.normpath(os.path.expanduser(leading_cd_target))
    tool_input_cwd_value = tool_input.get("cwd") if isinstance(tool_input, dict) else None
    if isinstance(tool_input_cwd_value, str) and tool_input_cwd_value.strip():
        return os.path.normpath(os.path.expanduser(tool_input_cwd_value))
    return None


def _effective_working_directory_is_ephemeral(command: str, tool_input: dict) -> bool:
    """Return True when the command's declared effective cwd is a specific ephemeral directory.

    Auto-allow trust model: if the destructive command declares (via leading
    ``cd`` or ``tool_input['cwd']``) that it will execute inside a concrete
    ephemeral directory (a temp-dir subfolder, a git worktrees directory, or
    a subfolder of the OS temp root), treat that directory as a disposable
    trust boundary and skip the destructive-action prompt. Rejects bare
    ephemeral roots (``/tmp``, ``/temp``, the OS temp root, ``/worktrees``,
    ``/worktree``) so auto-allow only triggers inside a named scratch area,
    not at the root of a shared scratch namespace. Returns False when no
    cwd is declared; the narrower target-based auto-allow still applies in
    that case.
    """
    declared_effective_cwd = _resolve_declared_effective_working_directory(command, tool_input)
    if declared_effective_cwd is None:
        return False
    if _path_is_bare_ephemeral_root(declared_effective_cwd):
        return False
    return directory_is_ephemeral(declared_effective_cwd)


CWD_SCOPED_DESTRUCTIVE_DESCRIPTIONS_ELIGIBLE_FOR_BROAD_EPHEMERAL_AUTO_ALLOW = (
    "rm -rf",
    "rm --recursive",
    "git reset --hard",
)


def _destructive_match_is_cwd_scoped(matched_description: str) -> bool:
    """Return True when the matched destructive pattern's blast radius is bounded by cwd.

    ``rm -rf``, ``rm --recursive``, and ``git reset --hard`` only affect
    files inside the working directory (or paths resolved relative to it
    when the rm target is relative). Patterns whose blast radius is NOT
    bounded by cwd — ``git push --force`` / ``git push -f`` (remote
    history rewrite), ``git clean`` variants (untracked deletion outside
    what the user can audit at the current prompt), ``mkfs`` / ``dd``
    (raw device), ``DROP TABLE`` / ``DROP DATABASE`` / ``TRUNCATE TABLE``
    (database) — must still prompt even when the command runs from an
    ephemeral worktree. Being in a scratch directory is not a trust zone
    for remote or out-of-band effects.
    """
    return matched_description.startswith(
        CWD_SCOPED_DESTRUCTIVE_DESCRIPTIONS_ELIGIBLE_FOR_BROAD_EPHEMERAL_AUTO_ALLOW
    )


def _command_contains_any_non_cwd_scoped_destructive_pattern(command: str) -> bool:
    """Return True when the command matches any destructive pattern outside the cwd-scoped whitelist.

    ``find_destructive_pattern`` returns the *first* match in the
    ``DESTRUCTIVE_BASH_PATTERNS`` table, where ``rm -rf`` sits at the
    very front. That means a compound like ``cd /tmp/scratch && rm -rf
    cache && git push --force`` reports ``rm -rf`` to the main gate,
    passes the cwd-scoped whitelist, and ends up auto-allowing the
    remote force-push even though the whitelist docstring says
    non-cwd-scoped patterns must still prompt. This helper scans *every*
    destructive pattern and returns True the moment it finds one that
    is not in the cwd-scoped whitelist, so the broad auto-allow can
    decline the whole command rather than trust the first-match report.
    """
    for each_pattern_regex, each_pattern_description in DESTRUCTIVE_BASH_PATTERNS:
        if each_pattern_regex.search(command) and not each_pattern_description.startswith(
            CWD_SCOPED_DESTRUCTIVE_DESCRIPTIONS_ELIGIBLE_FOR_BROAD_EPHEMERAL_AUTO_ALLOW
        ):
            return True
    return False


def _rm_target_resolves_outside_ephemeral_namespace(target_token: str, declared_effective_cwd: str | None) -> bool:
    """Return True when an ``rm`` target token resolves outside the ephemeral namespace.

    A token carrying command substitution (``$(...)``) or a backtick subshell is
    unsafe because the shell resolves it before ``rm`` runs and the hook cannot
    statically bound the deletion target. A token carrying a brace group with a
    comma list or ``..`` range is unsafe because the shell expands it into multiple
    targets the hook cannot bound; a bare ``{}`` placeholder (no comma, no range)
    does not match and stays bounded. A token referencing an environment variable
    other than a known temporary one (``TEMP``, ``TMP``, ``TMPDIR``,
    ``CLAUDE_JOB_DIR``) is unsafe; a known temporary variable spliced after an
    absolute (or ``/``-rooted) literal prefix is unsafe because the literal prefix,
    not the variable, roots the path. A token referencing only known temporary
    variables with an empty or ``~`` literal prefix resolves with each reference
    rewritten to the system temporary root. A ``~``-prefixed or absolute token
    resolves as written; a relative token resolves against ``declared_effective_cwd``
    (``None`` is unsafe because the target cannot be bounded). The resolved path is
    unsafe when its basename is a glob wildcard, when it is a bare ephemeral root,
    when it is a bare named-worktrees container, or when it is not ephemeral.

    Args:
        target_token: A single ``rm`` target token from the segment.
        declared_effective_cwd: The declared effective working directory, or ``None``
            when the command declares none.

    Returns:
        True when the target resolves outside the ephemeral namespace.
    """
    if "$(" in target_token or "`" in target_token:
        return True
    if re.search(r"\{[^{}]*(?:,|\.\.)[^{}]*\}", target_token):
        return True
    known_temporary_environment_variable_names = ALL_KNOWN_TEMPORARY_ENVIRONMENT_VARIABLE_NAMES
    environment_variable_reference_pattern = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?|%([A-Za-z_][A-Za-z0-9_]*)%")
    all_referenced_variable_names = [
        next(each_group for each_group in each_match.groups() if each_group is not None)
        for each_match in environment_variable_reference_pattern.finditer(target_token)
    ]
    resolved_token = target_token
    if all_referenced_variable_names:
        for each_variable_name in all_referenced_variable_names:
            if each_variable_name not in known_temporary_environment_variable_names:
                return True
        first_variable_reference = environment_variable_reference_pattern.search(target_token)
        assert first_variable_reference is not None
        literal_prefix_before_first_variable = target_token[: first_variable_reference.start()]
        if literal_prefix_before_first_variable not in ("", "~") and (
            os.path.isabs(literal_prefix_before_first_variable)
            or literal_prefix_before_first_variable.replace("\\", "/").startswith("/")
        ):
            return True
        system_temporary_root = os.path.normpath(tempfile.gettempdir()).replace("\\", "/")
        resolved_token = environment_variable_reference_pattern.sub(lambda each_match: system_temporary_root, target_token)
    each_expanded_target = os.path.expanduser(resolved_token)
    each_is_absolute = (
        os.path.isabs(each_expanded_target)
        or each_expanded_target.replace("\\", "/").startswith("/")
    )
    if each_is_absolute:
        each_resolved_target = os.path.normpath(each_expanded_target)
    elif declared_effective_cwd is None:
        return True
    else:
        each_resolved_target = os.path.normpath(os.path.join(declared_effective_cwd, each_expanded_target))
    if _path_basename_is_shell_glob_wildcard(each_resolved_target):
        return True
    if _path_is_bare_ephemeral_root(each_resolved_target):
        return True
    if _path_is_bare_named_worktrees_container(each_resolved_target):
        return True
    return not directory_is_ephemeral(each_resolved_target)


def _rm_segment_targets_escape_ephemeral_cwd(all_rm_segment_tokens: list[str], declared_effective_cwd: str | None) -> bool:
    """Return True when an ``rm`` segment's redirect, flags, or targets escape the ephemeral cwd.

    The segment tokens begin at the ``rm`` program token. An output redirection
    escapes (``rm -rf /tmp/x>/etc/passwd`` truncates ``/etc/passwd`` even when the
    deletion target is ephemeral; shlex keeps the ``>`` glued to the target token when
    no whitespace separates them). Unsafe ``rm`` flags before ``--`` (as enforced by
    ``_rm_flags_before_double_dash_are_unsafe``) escape; otherwise any collected target
    token that resolves outside the ephemeral namespace escapes.

    Args:
        all_rm_segment_tokens: The segment tokens starting at the ``rm`` token.
        declared_effective_cwd: The declared effective working directory, or ``None``
            when the command declares none.

    Returns:
        True when the segment's redirect, flags, or any target escape the ephemeral cwd.
    """
    if _segment_redirects_output_to_a_file(all_rm_segment_tokens):
        return True
    tokens_after_rm = all_rm_segment_tokens[1:]
    if _rm_flags_before_double_dash_are_unsafe(tokens_after_rm):
        return True
    return any(
        _rm_target_resolves_outside_ephemeral_namespace(each_target_token, declared_effective_cwd)
        for each_target_token in _collect_rm_target_tokens(tokens_after_rm)
    )


def _collect_find_search_root_tokens(all_tokens_after_find: list[str]) -> list[str]:
    """Return the path-operand search roots that follow ``find``, skipping global options.

    GNU ``find`` accepts global options before the path operands: the flag-only
    options ``-H``/``-L``/``-P`` (each its own token, possibly in sequence), the
    value-taking option ``-D`` (which consumes the following debug-options token), and
    an optimization-level option ``-O<level>`` whose level is glued to the flag
    (``-O3``), so the ``-O``-prefixed token is skipped as a single token and a
    following path operand is collected as a search root rather than swallowed as a
    level. The leading run of such global options
    is skipped first, then the path operands are collected: every non-dash token up to
    the first ``-``-prefixed expression primary (``-name``, ``-type``, ``-exec``). A
    ``find`` whose first post-option token is already an expression primary declares no
    path operand and returns an empty list, so it defaults to the ephemeral cwd.

    Args:
        all_tokens_after_find: The segment tokens that follow the ``find`` program token.

    Returns:
        The path-operand search-root tokens, in order; empty when ``find`` declares none.
    """
    each_token_index = 0
    while each_token_index < len(all_tokens_after_find):
        each_token = all_tokens_after_find[each_token_index]
        if each_token in ALL_FIND_GLOBAL_OPTION_FLAGS_WITHOUT_VALUE:
            each_token_index += 1
            continue
        if each_token in ALL_FIND_GLOBAL_OPTION_FLAGS_TAKING_A_VALUE:
            each_token_index += 1
            if each_token_index < len(all_tokens_after_find):
                each_token_index += 1
            continue
        if each_token.startswith(FIND_OPTIMIZATION_LEVEL_OPTION_PREFIX):
            each_token_index += 1
            continue
        break
    all_search_root_tokens: list[str] = []
    for each_token in all_tokens_after_find[each_token_index:]:
        if each_token.startswith("-"):
            break
        all_search_root_tokens.append(each_token)
    return all_search_root_tokens


def _find_exec_rm_search_root_escapes_ephemeral_cwd(
    all_segment_tokens: list[str], declared_effective_cwd: str | None
) -> bool:
    """Return True when a ``find ... -exec rm`` segment's search root escapes the ephemeral namespace.

    A ``find <roots...> ... -exec rm ...`` (or ``-execdir``) segment deletes whatever
    ``find`` matches under its leading search-root arguments; the ``rm``'s own ``{}``
    and ``+`` placeholders name no deletion target, ``find``'s roots do. The leading run
    of ``find`` global options (``-H``/``-L``/``-P``, ``-D debugopts``, ``-Olevel``) is
    skipped before the path operands are read, so a global option before the roots does
    not hide them. The segment is unsafe when any path-operand search root resolves
    outside the ephemeral namespace. Returns False when the segment contains no ``find``
    token, when it has no ``-exec`` or ``-execdir`` action after ``find``, or when
    ``find`` declares no path operand (``find`` then defaults to the ephemeral cwd).

    Args:
        all_segment_tokens: The tokens of a single shell segment.
        declared_effective_cwd: The declared effective working directory, or ``None``
            when the command declares none.

    Returns:
        True when any of ``find``'s search roots escapes the ephemeral namespace.
    """
    find_token_index = next(
        (
            index
            for index, token in enumerate(all_segment_tokens)
            if Path(_strip_leading_subshell_grouping_characters(token)).name == FIND_PROGRAM_NAME
        ),
        None,
    )
    if find_token_index is None:
        return False
    if not any(each_token in ALL_FIND_EXEC_ACTION_FLAGS for each_token in all_segment_tokens[find_token_index:]):
        return False
    all_search_root_tokens = _collect_find_search_root_tokens(all_segment_tokens[find_token_index + 1 :])
    return any(
        _rm_target_resolves_outside_ephemeral_namespace(each_search_root_token, declared_effective_cwd)
        for each_search_root_token in all_search_root_tokens
    )


def _command_changes_directory_beyond_leading_cd(command: str) -> bool:
    """Return True when a directory change beyond a single leading ``cd`` runs.

    The broad ephemeral auto-allow resolves a relative ``rm`` target against the
    declared effective working directory, which is established only by the
    command's single leading ``cd``. Any further directory change moves the base a
    later relative target resolves against, so the declared cwd no longer bounds
    the deletion: a second top-level ``cd`` (``cd /tmp/x && cd / && rm -rf etc``),
    a ``cd`` inside a subshell group (``(cd /; rm -rf etc)``), or a ``pushd`` /
    ``popd`` anywhere. The caller nulls the declared cwd when this returns True, so
    every relative target fails closed while absolute targets — which no directory
    change can redirect — still resolve.

    A leading ``cd`` is the first simple-command segment of the first physical line
    whose leading program, after leading ``VAR=value`` assignments and
    subshell-grouping characters are stripped, is ``cd``. Counts every segment whose
    leading program is ``cd``, ``pushd`` or ``popd`` and returns True when more such
    segments exist than the single leading ``cd``. Fails closed (returns True) when a
    physical line cannot be tokenized.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when a directory change beyond a single leading ``cd`` is present.
    """
    all_directory_changing_program_names = ("cd", "pushd", "popd")
    leading_cd_segment_count = 0
    directory_changing_segment_count = 0
    for each_line_index, each_command_line in enumerate(re.split(r"[\n\r]+", command)):
        try:
            all_command_tokens = _split_command_preserving_windows_backslashes(each_command_line)
        except ValueError:
            return True
        all_operator_split_tokens = _explode_glued_shell_control_operators(all_command_tokens)
        for each_segment_index, each_segment in enumerate(_split_tokens_into_shell_segments(all_operator_split_tokens)):
            leading_program_token = _leading_command_token(each_segment)
            if leading_program_token is None:
                continue
            is_subshell_wrapped = leading_program_token[:1] in ALL_SUBSHELL_GROUPING_CHARACTERS
            stripped_program_name = Path(_strip_leading_subshell_grouping_characters(leading_program_token)).name
            if stripped_program_name not in all_directory_changing_program_names:
                continue
            directory_changing_segment_count += 1
            if (
                stripped_program_name == "cd"
                and each_line_index == 0
                and each_segment_index == 0
                and not is_subshell_wrapped
            ):
                leading_cd_segment_count += 1
    return directory_changing_segment_count > leading_cd_segment_count


def _command_rm_targets_include_unsafe_path(command: str, tool_input: dict) -> bool:
    """Return True when an ``rm`` in any segment targets a path outside the ephemeral cwd.

    Tokenizes each physical line, explodes glued shell control operators, and splits
    into shell segments. A ``find ... -exec rm`` segment escapes when any of ``find``'s
    leading search roots resolves outside the ephemeral namespace, because those roots,
    not the ``rm``'s ``{}``/``+`` placeholders, name what gets deleted; that segment is
    then also checked as an ordinary ``rm`` segment, where the placeholder ``{}``/``+``
    targets resolve under the ephemeral cwd and a trailing redirect to the null device is
    benign while a redirect to any other file escapes. Within each segment, the first
    token whose basename is ``rm`` begins an ``rm`` invocation;
    its flags and targets are checked in isolation, so a sibling segment's flags
    (``mkdir -p``) or absolute paths (a ``python`` interpreter path) never count as this
    ``rm``'s targets. A segment escapes when an unsafe flag precedes ``--`` or a target
    resolves outside the ephemeral namespace: an absolute non-ephemeral path, a relative
    path that resolves outside (or with no declared cwd to resolve against), a reference
    to a non-temporary environment variable, a bare ephemeral root, a bare
    named-worktrees container, or a glob wildcard basename.

    A relative target fails closed when the command changes directory beyond a single
    leading ``cd`` (a second top-level ``cd``, a ``cd`` inside a subshell group, or a
    ``pushd`` / ``popd``): the declared cwd is nulled so the leading ``cd`` no longer
    bounds the deletion, while absolute targets — which no directory change can
    redirect — still resolve.

    Fails closed: returns True on parse failure (``ValueError`` from unbalanced quotes).
    The broad auto-allow must decline rather than grant on input the hook cannot
    conclusively bound.

    Args:
        command: The raw Bash command string from the tool input.
        tool_input: The Bash tool input mapping, used to resolve the declared effective
            working directory.

    Returns:
        True when any ``rm`` segment's flags or targets escape the ephemeral cwd.
    """
    declared_effective_cwd = _resolve_declared_effective_working_directory(command, tool_input)
    if _command_changes_directory_beyond_leading_cd(command):
        declared_effective_cwd = None
    for each_command_line in re.split(r"[\n\r]+", command):
        try:
            all_command_tokens = _split_command_preserving_windows_backslashes(each_command_line)
        except ValueError:
            return True
        all_operator_split_tokens = _explode_glued_shell_control_operators(all_command_tokens)
        for each_segment in _split_tokens_into_shell_segments(all_operator_split_tokens):
            if _find_exec_rm_search_root_escapes_ephemeral_cwd(each_segment, declared_effective_cwd):
                return True
            each_rm_token_index = next(
                (
                    index
                    for index, token in enumerate(each_segment)
                    if Path(_strip_leading_subshell_grouping_characters(token)).name == "rm"
                ),
                None,
            )
            if each_rm_token_index is None:
                continue
            if _rm_segment_targets_escape_ephemeral_cwd(each_segment[each_rm_token_index:], declared_effective_cwd):
                return True
    return False


def _git_reset_hard_allowed_for_command(command: str, current_working_directory: str) -> bool:
    if directory_is_ephemeral(current_working_directory):
        return True
    current_working_directory_lowercased = os.path.normpath(current_working_directory).lower()
    for allowed_project in load_allow_git_reset_hard_projects():
        allowed_project_lowercased = os.path.normpath(allowed_project).lower()
        if current_working_directory_lowercased.startswith(allowed_project_lowercased):
            return True
        for path_match in re.findall(r'cd\s+"([^"]+)"', command):
            if os.path.normpath(path_match).lower().startswith(allowed_project_lowercased):
                return True
    return False


def _is_convergence_branch(branch: str) -> bool:
    all_convergence_branch_prefixes = ALL_CONVERGENCE_BRANCH_PREFIXES
    for each_prefix in all_convergence_branch_prefixes:
        if branch.startswith(each_prefix):
            return True
    return bool(re.match(CONVERGENCE_BRANCH_SUFFIX_PATTERN, branch))


def _all_refspecs_are_convergence_branches(post_remote_text: str) -> bool:
    if not post_remote_text.strip():
        return False
    is_any_refspec_checked = False
    for each_token in post_remote_text.split():
        if each_token.startswith("-"):
            continue
        is_any_refspec_checked = True
        destination_branch = each_token.split(":")[-1]
        if not _is_convergence_branch(destination_branch):
            return False
    return is_any_refspec_checked


def _force_push_targets_convergence_branch(command: str) -> bool:
    convergence_force_push_detection_pattern = (
        CONVERGENCE_FORCE_PUSH_DETECTION_PATTERN
    )
    is_force_push_found = False
    for each_match in re.finditer(
        convergence_force_push_detection_pattern, command, re.IGNORECASE
    ):
        is_force_push_found = True
        post_push_text = each_match.group(1).strip()
        all_tokens = post_push_text.split()
        remote_index = 1 if all_tokens and all_tokens[0] in ("--force", "-f") else 0
        all_refspec_tokens = [
            token for token in all_tokens[remote_index + 1 :]
            if token not in ("--force", "-f")
        ]
        post_remote_text = " ".join(all_refspec_tokens)
        if not post_remote_text:
            return False
        if not _all_refspecs_are_convergence_branches(post_remote_text):
            return False
    return is_force_push_found


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "")

    if gh_redirect_is_active():
        redirected_gh_description = find_redirected_gh_pattern(command)
        if redirected_gh_description is not None:
            print(json.dumps(_build_silent_gh_deny_response(redirected_gh_description)))
            sys.exit(0)

    matched_description = find_destructive_pattern(command)

    if (
        matched_description is not None
        and _destructive_match_is_rm_family(matched_description)
        and command_has_no_real_rm_invocation(command)
    ):
        matched_description = _find_non_rm_destructive_pattern(command)

    if matched_description is not None and targets_only_claude_directory(command):
        sys.exit(0)

    if (
        matched_description is not None
        and _destructive_match_is_cwd_scoped(matched_description)
        and _effective_working_directory_is_ephemeral(command, tool_input)
        and not _command_executes_a_string_in_any_segment(command)
        and not _command_rm_targets_include_unsafe_path(command, tool_input)
        and not _command_contains_any_non_cwd_scoped_destructive_pattern(command)
    ):
        sys.exit(0)

    if matched_description is not None and _ephemeral_recursive_rm_auto_allow_granted(command, matched_description):
        sys.exit(0)

    if (
        matched_description is not None
        and _destructive_match_is_rm_family(matched_description)
        and rm_compound_targets_only_absolute_ephemeral_paths(command)
    ):
        sys.exit(0)

    if matched_description is not None and "git reset --hard" in matched_description:
        if _git_reset_hard_allowed_for_command(command, os.getcwd()):
            sys.exit(0)

    if (
        matched_description is not None
        and "git push" in matched_description
        and ("force" in matched_description or "-f" in matched_description)
        and _force_push_targets_convergence_branch(command)
    ):
        co_resident_hazard_description = _find_non_force_push_destructive_hazard(command)
        if co_resident_hazard_description is None:
            sys.exit(0)
        matched_description = co_resident_hazard_description

    if matched_description is not None:
        ask_response = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"DESTRUCTIVE: {matched_description}. Requires explicit user approval."
            }
        }
        print(json.dumps(ask_response))

    sys.exit(0)


if __name__ == "__main__":
    main()
