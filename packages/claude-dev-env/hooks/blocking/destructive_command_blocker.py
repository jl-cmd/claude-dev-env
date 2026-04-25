#!/usr/bin/env python3
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

CLAUDE_DIRECTORY_PATH = os.path.normpath(os.path.expanduser("~/.claude"))
GH_REDIRECT_ACTIVE_ENV_VAR = "CLAUDE_GH_REDIRECT_ACTIVE"
GH_REDIRECT_ACTIVE_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


def gh_redirect_is_active() -> bool:
    env_var_value = os.environ.get(GH_REDIRECT_ACTIVE_ENV_VAR, "").strip().lower()
    return env_var_value in GH_REDIRECT_ACTIVE_TRUTHY_VALUES

def directory_is_ephemeral(directory_path: str) -> bool:
    ephemeral_auto_allow_disabled_env_var = "CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW"
    truthy_string_values = frozenset({"1", "true", "yes", "on"})
    if os.environ.get(ephemeral_auto_allow_disabled_env_var, "").strip().lower() in truthy_string_values:
        return False
    forward_slash_normalized_directory_path = os.path.normpath(directory_path).replace("\\", "/").lower()
    all_ephemeral_path_segments = ("/worktrees/", "/worktree/", "/tmp/", "/temp/")
    for each_segment in all_ephemeral_path_segments:
        if each_segment in forward_slash_normalized_directory_path + "/":
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
    if "\\" in command and (
        os.name == "nt" or _command_contains_windows_style_path(command)
    ):
        forward_slash_normalized_command = command.replace("\\", "/")
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
    $(...) cannot piggy-back non-rm work on the ephemeral auto-allow. Rejects
    bare ephemeral roots (/tmp, system temp dir) and bare directories named
    worktrees/worktree so we never auto-approve wiping those roots. Only
    allows common short flags and a small set of long options before ``--``;
    tokens with ``=`` or unknown long options disable auto-allow.
    """
    compound_shell_operator_pattern = re.compile(r'(?:&&|\|\||;|\||`|\$\()')
    if compound_shell_operator_pattern.search(command):
        return False
    try:
        all_command_tokens = _split_command_preserving_windows_backslashes(command)
    except ValueError:
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


def _command_rm_targets_include_unsafe_path(command: str, tool_input: dict) -> bool:
    """Return True when the command contains an ``rm`` whose targets are unsafe.

    Unsafe means any of: bare ephemeral root (``/tmp``, ``/temp``, the OS
    temp root, ``/worktrees``, ``/worktree``), bare named worktrees
    container, absolute path outside the ephemeral namespace, relative
    path that resolves (against the declared effective cwd) outside the
    ephemeral namespace, wildcard glob metacharacter in the target
    basename, or unsafe ``rm`` flag before ``--`` (``--files0-from=...``,
    unknown long option, non-whitelisted short flag) as enforced by
    ``_rm_flags_before_double_dash_are_unsafe``.

    Fails closed: returns True on parse failure (``ValueError`` from
    unbalanced quotes) or when a relative target is encountered without
    a declared effective cwd to resolve it against. The broad auto-allow
    must decline rather than grant on input the hook cannot conclusively
    bound.
    """
    try:
        all_command_tokens = _split_command_preserving_windows_backslashes(command)
    except ValueError:
        return True
    declared_effective_cwd = _resolve_declared_effective_working_directory(command, tool_input)
    for each_token_index in range(len(all_command_tokens)):
        if all_command_tokens[each_token_index] != "rm":
            continue
        tokens_after_rm = all_command_tokens[each_token_index + 1:]
        if _rm_flags_before_double_dash_are_unsafe(tokens_after_rm):
            return True
        all_target_tokens = _collect_rm_target_tokens(tokens_after_rm)
        for each_target_token in all_target_tokens:
            each_expanded_target = os.path.expanduser(each_target_token)
            each_is_absolute = (
                os.path.isabs(each_expanded_target)
                or each_expanded_target.replace("\\", "/").startswith("/")
            )
            if each_is_absolute:
                each_resolved_target = os.path.normpath(each_expanded_target)
            else:
                if declared_effective_cwd is None:
                    return True
                each_resolved_target = os.path.normpath(
                    os.path.join(declared_effective_cwd, each_expanded_target)
                )
            if _path_basename_is_shell_glob_wildcard(each_resolved_target):
                return True
            if _path_is_bare_ephemeral_root(each_resolved_target):
                return True
            if _path_is_bare_named_worktrees_container(each_resolved_target):
                return True
            if not directory_is_ephemeral(each_resolved_target):
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

    if matched_description is not None and targets_only_claude_directory(command):
        sys.exit(0)

    if (
        matched_description is not None
        and _destructive_match_is_cwd_scoped(matched_description)
        and _effective_working_directory_is_ephemeral(command, tool_input)
        and not _command_rm_targets_include_unsafe_path(command, tool_input)
        and not _command_contains_any_non_cwd_scoped_destructive_pattern(command)
    ):
        sys.exit(0)

    if matched_description is not None and _ephemeral_recursive_rm_auto_allow_granted(command, matched_description):
        sys.exit(0)

    if matched_description is not None and "git reset --hard" in matched_description:
        if _git_reset_hard_allowed_for_command(command, os.getcwd()):
            sys.exit(0)

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
