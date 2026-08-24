"""ntfy publish settings the notify_ntfy script reads.

::

    DEFAULT_SERVER_URL       "https://ntfy.sh"   server when NTFY_SERVER is unset
    DEFAULT_PRIORITY_NAME    "high"              level when no priority is given
    REQUEST_TIMEOUT_SECONDS  10                  the POST deadline in seconds

Header names, the priority-level map, and the environment-variable names round
out the set.
"""

TOPIC_ENVIRONMENT_VARIABLE_NAME = "NTFY_TOPIC"
SERVER_ENVIRONMENT_VARIABLE_NAME = "NTFY_SERVER"
DEFAULT_SERVER_URL = "https://ntfy.sh"
REQUEST_TIMEOUT_SECONDS = 10
URL_PATH_SEPARATOR = "/"
MESSAGE_ENCODING = "utf-8"
POST_METHOD_NAME = "POST"
TITLE_HEADER_NAME = "Title"
PRIORITY_HEADER_NAME = "Priority"
CLICK_HEADER_NAME = "Click"
CONTENT_TYPE_HEADER_NAME = "Content-Type"
PLAIN_TEXT_CONTENT_TYPE = "text/plain"
DEFAULT_PRIORITY_NAME = "high"
ALL_PRIORITY_LEVELS_BY_NAME: dict[str, str] = {
    "min": "1",
    "low": "2",
    "default": "3",
    "high": "4",
    "urgent": "5",
}
