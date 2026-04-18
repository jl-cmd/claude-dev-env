#!/usr/bin/env python3

import json
import os
import platform
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notification_utils import (
    notify_ntfy,
    notify_discord,
    is_wsl,
    notify_windows,
    notify_wsl,
    sound_wsl,
    sound_windows,
    get_project_name,
)

ATTENTION_WEBHOOK_SECRET_ID = os.environ.get("BWS_DISCORD_ATTENTION_SECRET_ID", "")


def send_desktop_and_push_notification(
    project_name: str,
    notification_message: str,
    ntfy_priority: str,
) -> None:
    notify_ntfy(title=project_name, message=notification_message, priority=ntfy_priority)
    notify_discord(
        title=project_name,
        message=notification_message,
        webhook_secret_id=ATTENTION_WEBHOOK_SECRET_ID,
    )
    system = platform.system()
    if system == "Windows":
        sound_windows()
        notify_windows(project_name, notification_message)
    elif is_wsl():
        sound_wsl()
        notify_wsl(project_name, notification_message)


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    notification_type = hook_input.get("notification_type", "")
    notification_message = hook_input.get("message", "Claude needs attention")
    project_name = get_project_name()

    if notification_type == "idle_prompt":
        send_desktop_and_push_notification(project_name, notification_message, ntfy_priority="default")
    elif notification_type == "permission_prompt":
        permission_message = f"[PERMISSION] {notification_message}"
        send_desktop_and_push_notification(project_name, permission_message, ntfy_priority="high")
    elif notification_type == "auth_success":
        print(f"auth_success: {notification_message}", file=sys.stderr)
    elif notification_type == "elicitation_dialog":
        print(f"elicitation_dialog: {notification_message}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
