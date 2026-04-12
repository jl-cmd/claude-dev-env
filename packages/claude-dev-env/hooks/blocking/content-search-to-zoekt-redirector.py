#!/usr/bin/env python3
"""PreToolUse hook: deny Grep, Search, and shell search in indexed trees; steer to Zoekt MCP."""

import json
import os
import sys

from content_search_zoekt_bash_block_reason import block_reason_for_bash_command
from content_search_zoekt_block_payload import build_block_payload
from content_search_zoekt_indexed_paths import is_in_indexed_repo, is_specific_file
from content_search_zoekt_redirect_guidance import get_zoekt_redirect_message


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    content_search_tools = frozenset({"Grep", "Search"})
    block_reason = None

    if tool_name in content_search_tools:
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", "")

        if not path:
            path = os.getcwd()

        if is_specific_file(path):
            sys.exit(0)

        if is_in_indexed_repo(path):
            block_reason = f"{tool_name}(pattern: \"{pattern}\", path: \"{path}\")"

    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        block_reason = block_reason_for_bash_command(command)

    if block_reason is None:
        sys.exit(0)
    short_label = f"blocked {block_reason}; use Zoekt MCP"
    payload = build_block_payload(
        brief_label=short_label,
        permission_decision_reason=get_zoekt_redirect_message(),
    )
    print(json.dumps(payload))
    sys.exit(0)


if __name__ == "__main__":
    main()
