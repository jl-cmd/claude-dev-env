"""Constants for resolving the Claude Code harness session scratchpad directory.

The harness gives each session a throwaway scratch directory it announces in
the session's system prompt. The layout carries a harness user directory
(``claude`` on Windows, ``claude-<uid>`` on POSIX), a mangled working-directory
segment, the session id, and a ``scratchpad`` leaf:
``<tempdir>/<user-dir>/<mangled-cwd>/<session-id>/scratchpad``. These constants
name the fixed path components the code-rules, TDD, and doc-language gates match
to recognize that directory from the signals a hook process reads: the session id in the
PreToolUse payload or the ``CLAUDE_CODE_SESSION_ID`` environment variable, and
the temp-directory root.
"""

HARNESS_SCRATCHPAD_USER_DIRECTORY_NAME: str = "claude"
HARNESS_SCRATCHPAD_USER_DIRECTORY_PREFIX: str = "claude-"
HARNESS_SCRATCHPAD_LEAF_DIRECTORY_NAME: str = "scratchpad"
HOOK_PAYLOAD_SESSION_ID_KEY: str = "session_id"
CLAUDE_SESSION_ID_ENVIRONMENT_VARIABLE_NAME: str = "CLAUDE_CODE_SESSION_ID"
