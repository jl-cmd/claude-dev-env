#!/usr/bin/env python3
"""
Notification hook - cross-platform (Windows/Linux/WSL)
Plays chimes sound + shows desktop notification when Claude needs user input.
"""

import json
import os
import platform
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notification_utils import (
    _debug_log,
    notify_ntfy,
    is_wsl,
    notify_windows,
    notify_wsl,
    notify_linux,
    sound_windows,
    sound_wsl,
    sound_linux,
    get_project_name,
)

DEFAULT_MESSAGE = "Input needed"


def get_question_from_stdin() -> str:
    """Extract question text from hook input JSON."""
    try:
        hook_input = json.load(sys.stdin)
        tool_input = hook_input.get("tool_input", {})
        questions = tool_input.get("questions", [])
        if questions:
            return questions[0].get("question", DEFAULT_MESSAGE)
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return DEFAULT_MESSAGE


def main() -> None:
    system = platform.system()
    wsl_mode = is_wsl()

    project_name = get_project_name()
    question_text = get_question_from_stdin()
    # #region agent log
    _debug_log(
        run_id="pre-fix",
        hypothesis_id="H3",
        location="hooks/notification/attention-needed-notify.py:50",
        message="notification hook routing decision",
        data={
            "system": system,
            "is_wsl": wsl_mode,
            "question_length": len(question_text),
        },
    )
    # #endregion

    notify_ntfy(title=project_name, message=question_text)

    if system == "Windows":
        sound_windows()
        notify_windows(project_name, question_text)
    elif wsl_mode:
        sound_wsl()
        notify_wsl(project_name, question_text)
    elif system == "Linux":
        sound_linux()
        notify_linux()
    else:
        print("\a", end="", flush=True)


if __name__ == "__main__":
    main()
