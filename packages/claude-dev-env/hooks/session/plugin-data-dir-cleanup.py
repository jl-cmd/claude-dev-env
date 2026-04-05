#!/usr/bin/env python3
"""SessionStart hook — removes empty plugin data directories to prevent EEXIST.

Claude Code's infrastructure calls mkdirSync without {recursive: true} when
setting up plugin data directories for hook execution. If the directory already
exists from a previous session, the mkdir throws EEXIST and the hook fails.

This workaround removes known empty plugin data directories at session start
so the infrastructure's mkdir succeeds when the Stop hook fires later.

Tracking: https://github.com/anthropics/claude-code/issues — unfixed code path
separate from the EEXIST fixes in v2.1.70-v2.1.72.
"""

import os
import sys

PLUGINS_DATA_DIRECTORY = os.path.join(
    os.path.expanduser("~"), ".claude", "plugins", "data"
)

AFFECTED_PLUGIN_DIRECTORIES = [
    "ralph-loop-claude-plugins-official",
]


def main() -> None:
    for plugin_directory_name in AFFECTED_PLUGIN_DIRECTORIES:
        target_path = os.path.join(PLUGINS_DATA_DIRECTORY, plugin_directory_name)
        if not os.path.isdir(target_path):
            continue
        try:
            os.rmdir(target_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
