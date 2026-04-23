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
