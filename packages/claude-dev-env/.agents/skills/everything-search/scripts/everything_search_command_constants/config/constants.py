"""Configuration constants for the Everything search command."""

CLAUDE_DIRECTORY_NAME = ".claude"
EXECUTABLE_NAME = "es.exe"
EXECUTION_ERROR_EXIT_CODE = 1
INFORMATIONAL_ARGUMENT = "-version"
INVALID_INPUT_EXIT_CODE = 2
IPC_CLIENT_DID_NOT_ANSWER_MESSAGE = (
    "Everything IPC client did not answer. Everything service state was not probed.\n"
)
IPC_WINDOW_NOT_FOUND_EXIT_CODE = 8
IPC_WINDOW_RETRY_COUNT = 2
IPC_WINDOW_RETRY_DELAY_SECONDS = 0.5
PROJECT_PATHS_FILE_NAME = "project-paths.json"
REGISTRY_META_KEY = "_meta"
SEARCH_SCOPE_REQUIRED_MESSAGE = "The first search argument must define a path, project, name, extension, date, or size scope.\n"
UTF8_ENCODING = "utf-8"
