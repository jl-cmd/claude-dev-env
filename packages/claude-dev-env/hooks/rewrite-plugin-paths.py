#!/usr/bin/env python3
"""Rewrite plugin config paths to match the current platform.

Solves the cross-platform path problem for shared ~/.claude directories.
On WSL/Docker, rewrites Windows paths to Linux paths.
On Windows, rewrites Linux paths back to Windows paths (heals WSL damage).

Uses json.load/json.dump to avoid all backslash escaping issues.
Called from Docker entrypoint.sh and can be called from session hooks.
"""

import json
import os
import sys
from typing import Union


PLUGIN_CONFIG_FILENAMES = [
    "known_marketplaces.json",
    "installed_plugins.json",
]

WINDOWS_PATH_PREFIX = os.path.join("C:\\Users", os.environ.get("USERNAME", "unknown"), ".claude")
LINUX_HOME_PATH_PREFIX = os.path.join(os.path.expanduser("~"), ".claude") if os.name != "nt" else ""

JsonValue = Union[str, int, float, bool, None, list, dict]


def detect_local_claude_directory() -> str:
    return os.path.join(os.path.expanduser("~"), ".claude")


def rewrite_paths_in_value(
    value: JsonValue,
    from_prefix: str,
    to_prefix: str,
) -> JsonValue:
    if isinstance(value, str):
        return value.replace(from_prefix, to_prefix)
    if isinstance(value, dict):
        return {
            each_key: rewrite_paths_in_value(each_value, from_prefix, to_prefix)
            for each_key, each_value in value.items()
        }
    if isinstance(value, list):
        return [
            rewrite_paths_in_value(each_element, from_prefix, to_prefix)
            for each_element in value
        ]
    return value


def rewrite_plugin_config_file(
    file_path: str,
    from_prefix: str,
    to_prefix: str,
) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8") as source_file:
            parsed_config = json.load(source_file)
    except FileNotFoundError:
        return False
    except json.JSONDecodeError as e:
        print(
            f"[rewrite-paths] ERROR: Invalid JSON in {file_path}: {e}",
            file=sys.stderr,
        )
        return False

    rewritten_config = rewrite_paths_in_value(
        parsed_config,
        from_prefix,
        to_prefix,
    )

    if rewritten_config == parsed_config:
        return False

    with open(file_path, "w", encoding="utf-8") as destination_file:
        json.dump(rewritten_config, destination_file, indent=2)
        destination_file.write("\n")

    return True


def main() -> None:
    is_windows = os.name == "nt"
    local_claude_directory = detect_local_claude_directory()

    if is_windows:
        from_prefix = LINUX_HOME_PATH_PREFIX
        to_prefix = WINDOWS_PATH_PREFIX
    else:
        from_prefix = WINDOWS_PATH_PREFIX
        to_prefix = local_claude_directory

    plugins_directory = os.path.join(local_claude_directory, "plugins")

    rewritten_count = 0
    for each_filename in PLUGIN_CONFIG_FILENAMES:
        each_file_path = os.path.join(plugins_directory, each_filename)
        was_rewritten = rewrite_plugin_config_file(
            each_file_path,
            from_prefix,
            to_prefix,
        )
        if was_rewritten:
            rewritten_count += 1
            print(
                f"[rewrite-paths] Rewrote paths in {each_filename}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
