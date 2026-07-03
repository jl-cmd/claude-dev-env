"""Constants for the collect_log_window script.

HOOK_BLOCKS_LOG_RELATIVE_PATH: home-relative path of the JSON-lines hook block log.
DEFAULT_WINDOW_HOURS: how many hours back a collection reads when no window is given.
BLOCK_LEVEL_LABEL: the level stamped on every record read from the hook block log.
LOG_TIMESTAMP_KEY: hook-block-log JSON key holding the ISO-8601 block time.
LOG_HOOK_KEY: hook-block-log JSON key holding the blocking hook's name.
LOG_REASON_KEY: hook-block-log JSON key holding the human-readable block reason.
RECORD_TIMESTAMP_KEY: output-record key holding the ISO-8601 block time.
RECORD_SOURCE_KEY: output-record key holding the blocking hook's name.
RECORD_LEVEL_KEY: output-record key holding the severity label.
RECORD_MESSAGE_KEY: output-record key holding the block reason.
"""

HOOK_BLOCKS_LOG_RELATIVE_PATH = ".claude/logs/hook-blocks.log"
DEFAULT_WINDOW_HOURS = 24
BLOCK_LEVEL_LABEL = "block"
LOG_TIMESTAMP_KEY = "timestamp"
LOG_HOOK_KEY = "hook"
LOG_REASON_KEY = "reason"
RECORD_TIMESTAMP_KEY = "timestamp"
RECORD_SOURCE_KEY = "source"
RECORD_LEVEL_KEY = "level"
RECORD_MESSAGE_KEY = "message"