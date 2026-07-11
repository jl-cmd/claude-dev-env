"""Publish one ntfy notification for the Copilot gate.

::

    run:  notify_ntfy.py --title "PR 743" --message "..." --click-url "https://r"
    ok:   topic set   -> POST to {server}/{topic}, exit 0
    flag: topic unset -> readable error on stderr, exit 1

The topic and the optional server override both read from the environment. A
code-concern gate runs this to page the user, then holds the run until the
deadline.

Usage:
    notify_ntfy.py --title "PR 743" --message "..." --click-url "https://..."
    notify_ntfy.py --title "PR 743" --message "..." --click-url "..." --priority urgent
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping

from copilot_finding_triage_constants.config.notify_ntfy_constants import (
    ALL_PRIORITY_LEVELS_BY_NAME,
    CLICK_HEADER_NAME,
    CONTENT_TYPE_HEADER_NAME,
    DEFAULT_PRIORITY_NAME,
    DEFAULT_SERVER_URL,
    MESSAGE_ENCODING,
    PLAIN_TEXT_CONTENT_TYPE,
    POST_METHOD_NAME,
    PRIORITY_HEADER_NAME,
    REQUEST_TIMEOUT_SECONDS,
    SERVER_ENVIRONMENT_VARIABLE_NAME,
    TITLE_HEADER_NAME,
    TOPIC_ENVIRONMENT_VARIABLE_NAME,
    URL_PATH_SEPARATOR,
)

def parse_arguments(all_arguments: list[str]) -> argparse.Namespace:
    """Parse the notify_ntfy command-line arguments.

    Args:
        all_arguments: The argument strings following the script name.

    Returns:
        The parsed namespace carrying title, message, click_url, and priority.
    """
    parser = argparse.ArgumentParser(description="Publish one ntfy notification.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--click-url", required=True, dest="click_url")
    parser.add_argument(
        "--priority",
        default=DEFAULT_PRIORITY_NAME,
        choices=sorted(ALL_PRIORITY_LEVELS_BY_NAME),
    )
    return parser.parse_args(all_arguments)

def resolve_topic(all_environment_variables: Mapping[str, str]) -> str:
    """Return the ntfy topic from the environment, empty when unset.

    Args:
        all_environment_variables: The environment mapping to read the topic from.

    Returns:
        The topic string, or an empty string when the variable is unset.
    """
    return all_environment_variables.get(TOPIC_ENVIRONMENT_VARIABLE_NAME, "").strip()

def resolve_server(all_environment_variables: Mapping[str, str]) -> str:
    """Return the ntfy server URL from the environment.

    Args:
        all_environment_variables: The environment mapping to read the override from.

    Returns:
        The override server URL when set, otherwise the default server URL.
    """
    configured_server = all_environment_variables.get(
        SERVER_ENVIRONMENT_VARIABLE_NAME, ""
    ).strip()
    return configured_server or DEFAULT_SERVER_URL

def _build_headers(title: str, click_url: str, priority_name: str) -> dict[str, str]:
    """Build the ntfy publish headers for one notification.

    Args:
        title: The notification title header.
        click_url: The URL opened when the notification is tapped.
        priority_name: The accepted priority name selecting the level header.

    Returns:
        The header mapping ntfy reads to render and route the notification.
    """
    return {
        TITLE_HEADER_NAME: title,
        PRIORITY_HEADER_NAME: ALL_PRIORITY_LEVELS_BY_NAME[priority_name],
        CLICK_HEADER_NAME: click_url,
        CONTENT_TYPE_HEADER_NAME: PLAIN_TEXT_CONTENT_TYPE,
    }

def build_request(
    title: str,
    message: str,
    click_url: str,
    priority_name: str,
    topic: str,
    server: str,
) -> urllib.request.Request:
    """Build the ntfy publish request for one notification.

    Args:
        title: The notification title header.
        message: The notification body text.
        click_url: The URL opened when the notification is tapped.
        priority_name: The accepted priority name selecting the level header.
        topic: The ntfy topic to publish to.
        server: The ntfy server base URL.

    Returns:
        A POST request carrying the encoded body and the ntfy headers.
    """
    endpoint_url = f"{server}{URL_PATH_SEPARATOR}{topic}"
    return urllib.request.Request(
        endpoint_url,
        data=message.encode(MESSAGE_ENCODING),
        headers=_build_headers(title, click_url, priority_name),
        method=POST_METHOD_NAME,
    )

def _send_notification(request: urllib.request.Request, timeout_seconds: int) -> None:
    """Send the ntfy request, raising on any transport failure.

    Args:
        request: The publish request to send.
        timeout_seconds: Seconds to wait before the POST times out.
    """
    with urllib.request.urlopen(request, timeout=timeout_seconds):
        return None

def _emit_error(message_text: str) -> None:
    """Write one error line to standard error."""
    sys.stderr.write(message_text + "\n")

def _publish(
    parsed_arguments: argparse.Namespace,
    all_environment_variables: Mapping[str, str],
) -> int:
    """Publish the parsed notification, returning the process exit code."""
    topic = resolve_topic(all_environment_variables)
    if not topic:
        _emit_error(
            f"{TOPIC_ENVIRONMENT_VARIABLE_NAME} is unset; set it to the ntfy topic."
        )
        return 1
    request = build_request(
        parsed_arguments.title,
        parsed_arguments.message,
        parsed_arguments.click_url,
        parsed_arguments.priority,
        topic,
        resolve_server(all_environment_variables),
    )
    try:
        _send_notification(request, REQUEST_TIMEOUT_SECONDS)
    except (urllib.error.URLError, OSError) as send_error:
        _emit_error(f"ntfy publish failed: {send_error}")
        return 1
    return 0

def main(
    all_arguments: list[str],
    all_environment_variables: Mapping[str, str],
) -> int:
    """Publish one ntfy notification from the command line.

    Args:
        all_arguments: The argument strings following the script name.
        all_environment_variables: The environment mapping carrying topic and server.

    Returns:
        Zero on a delivered notification; one on a missing topic or failed send.
    """
    return _publish(parse_arguments(all_arguments), all_environment_variables)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], os.environ))
