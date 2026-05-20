"""Constants for the doc-gist auto-publish PostToolUse hook.

PUBLISH_SENTINEL: HTML comment marker. Claude includes it in HTML it intends to share;
absent in HTML that is part of code, tests, or fixtures. Hook is a no-op without it.

HTML_FILE_EXTENSION: only files ending in this extension are candidates for the hook;
Markdown, source files, etc. are skipped.

ALL_TARGET_TOOL_NAMES: tool names the hook fires after. The hook is a PostToolUse
listener; only Write and Edit produce a writable file path that the marker check
can be applied to.
"""

PUBLISH_SENTINEL = "<!-- @publish-as-gist -->"
HTML_FILE_EXTENSION = ".html"
ALL_TARGET_TOOL_NAMES = ("Write", "Edit")
HOOK_SUBPROCESS_TIMEOUT_SECONDS = 50
UPLOAD_SCRIPT_RELATIVE_PATH = "skills/doc-gist/scripts/gist_upload.py"
