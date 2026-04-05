#!/usr/bin/env python3
import json
import os
import re
import sys

CLAUDE_DIRECTORY_PATH = os.path.normpath(os.path.expanduser("~/.claude"))

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
    (re.compile(r'\bgh\s+api\b.*/(comments|reviews)\b.*-X\s+POST', re.IGNORECASE), "gh api comment/review POST (visible to others)"),
    (re.compile(r'\bgh\s+pr\s+comment\b', re.IGNORECASE), "gh pr comment (visible to others)"),
    (re.compile(r'\bgh\s+pr\s+review\b', re.IGNORECASE), "gh pr review (visible to others)"),
    (re.compile(r'\bgh\s+issue\s+comment\b', re.IGNORECASE), "gh issue comment (visible to others)"),
]

def find_destructive_pattern(command: str) -> str | None:
    for pattern_regex, pattern_description in DESTRUCTIVE_BASH_PATTERNS:
        if pattern_regex.search(command):
            return pattern_description
    return None


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
