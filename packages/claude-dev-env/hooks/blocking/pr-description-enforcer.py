import json
import os
import re
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PR_GUIDE_PATH = os.path.join(PLUGIN_ROOT, "docs", "PR_DESCRIPTION_GUIDE.md")

REQUIRED_PR_SECTION_HEADERS = [
    "description",
    "why",
    "how",
]

MINIMUM_PR_BODY_LENGTH = 50

VAGUE_LANGUAGE_PATTERN = re.compile(
    r'\b(fix(?:ed)? (?:bug|issue|it)|update(?:d)? code|minor changes|various (?:fixes|updates|improvements))\b',
    re.IGNORECASE,
)


def extract_body_from_command(command: str) -> str:
    heredoc_match = re.search(r'--body\s+"\$\(cat <<', command)
    if heredoc_match:
        return command[heredoc_match.start():]

    body_match = re.search(r'--body\s+"([^"]*)"', command) or re.search(r"--body\s+'([^']*)'", command)
    if body_match:
        return body_match.group(1)

    short_flag_match = re.search(r'-b\s+"([^"]*)"', command) or re.search(r"-b\s+'([^']*)'", command)
    if short_flag_match:
        return short_flag_match.group(1)

    return ""


def validate_pr_body(body: str) -> list[str]:
    violations = []
    body_lower = body.lower()

    missing_required_sections = [
        header for header in REQUIRED_PR_SECTION_HEADERS
        if f"## {header}" not in body_lower and f"**{header}" not in body_lower
    ]

    if missing_required_sections:
        formatted_sections = ", ".join(f"'{each_section.title()}'" for each_section in missing_required_sections)
        violations.append(f"Missing required section(s): {formatted_sections}")

    stripped_body = re.sub(r'#.*', '', body).strip()
    stripped_body = re.sub(r'\*\*.*?\*\*', '', stripped_body).strip()
    if len(stripped_body) < MINIMUM_PR_BODY_LENGTH:
        violations.append("PR body too short -- provide meaningful context for reviewers")

    vague_matches = VAGUE_LANGUAGE_PATTERN.findall(body)
    if vague_matches:
        violations.append(f"Vague language detected: {', '.join(vague_matches)} -- be specific about what changed and why")

    return violations


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    is_pr_create = "gh pr create" in command and ("--body" in command or "-b " in command)
    is_pr_edit = "gh pr edit" in command and "--body" in command

    if not (is_pr_create or is_pr_edit):
        sys.exit(0)

    body = extract_body_from_command(command)

    if not body:
        sys.exit(0)

    violations = validate_pr_body(body)

    if violations:
        violation_list = "; ".join(violations)
        pr_guide_reference = f" @{PR_GUIDE_PATH}" if os.path.exists(PR_GUIDE_PATH) else ""
        denial_reason = (
            f"BLOCKED: [PR_DESCRIPTION] {violation_list}. "
            f"Follow the PR description guide:{pr_guide_reference}"
        )
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": denial_reason,
            }
        }
        print(json.dumps(result))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()
