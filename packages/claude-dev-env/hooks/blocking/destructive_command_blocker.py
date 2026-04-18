#!/usr/bin/env python3
import datetime
import json
import os
import re
import sys
from pathlib import Path

CLAUDE_DIRECTORY_PATH = os.path.normpath(os.path.expanduser("~/.claude"))
GH_REDIRECT_ACTIVE_ENV_VAR = "CLAUDE_GH_REDIRECT_ACTIVE"
GH_REDIRECT_ACTIVE_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


def gh_redirect_is_active() -> bool:
    env_var_value = os.environ.get(GH_REDIRECT_ACTIVE_ENV_VAR, "").strip().lower()
    return env_var_value in GH_REDIRECT_ACTIVE_TRUTHY_VALUES

# Projects where git reset --hard is explicitly allowed by the user.
# Add your own project paths here, e.g.:
# os.path.normpath("C:/Users/you/your-project"),
ALLOW_GIT_RESET_HARD_PROJECTS: list[str] = []

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

    # Allow git reset --hard in explicitly approved projects (case-insensitive for Windows drive letters)
    if matched_description is not None and "git reset --hard" in matched_description:
        cwd = os.path.normpath(os.getcwd()).lower()
        command_lower = command.lower()
        for allowed_project in ALLOW_GIT_RESET_HARD_PROJECTS:
            allowed_lower = allowed_project.lower()
            if cwd.startswith(allowed_lower):
                sys.exit(0)
            # Also check the cd target in the command itself
            for path_match in re.findall(r'cd\s+"([^"]+)"', command):
                if os.path.normpath(path_match).lower().startswith(allowed_lower):
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
