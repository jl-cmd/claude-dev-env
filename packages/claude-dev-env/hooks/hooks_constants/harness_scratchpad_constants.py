"""Constants for resolving the Claude Code harness session scratchpad directory.

The harness gives each session a throwaway scratch directory it announces in
the session's system prompt, laid out as
``<tempdir>/claude-<uid>/<mangled-cwd>/<session-id>/scratchpad``. These constants
name the fixed path components the code-rules and TDD gates read to rebuild that
directory from the signals a hook process can see.

The exemption is POSIX-only: without ``os.getuid`` (Windows) it never fires,
so full enforcement stays in place there.
"""

HARNESS_SCRATCHPAD_USER_DIRECTORY_PREFIX: str = "claude-"
HARNESS_SCRATCHPAD_PATH_SEPARATOR_REPLACEMENT: str = "-"
HARNESS_SCRATCHPAD_LEAF_DIRECTORY_NAME: str = "scratchpad"
HOOK_PAYLOAD_SESSION_ID_KEY: str = "session_id"
HOOK_PAYLOAD_WORKING_DIRECTORY_KEY: str = "cwd"
