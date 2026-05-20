#!/usr/bin/env python3
"""PostToolUse hook: auto-publish HTML files marked with the doc-gist sentinel.

When Claude writes an .html file containing the marker
`<!-- @publish-as-gist -->`, this hook invokes the doc-gist `gist_upload.py`
script against that file and prints the resulting gist + htmlpreview URLs
into the harness output so Claude can quote them back to the user.

The marker is the on-demand trigger: HTML files without it are ignored. This
keeps the hook silent for HTML that is part of code (React components, test
fixtures, scraped pages) and active only for HTML Claude intentionally
designed as a shareable artifact.

The hook does not modify the file, does not block the write, and exits 0
even on upload failure (failure is logged to stderr but does not break
Claude's flow).
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import IO


logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(message)s")

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.doc_gist_auto_publish_constants import (  # noqa: E402
    ALL_TARGET_TOOL_NAMES,
    HOOK_SUBPROCESS_TIMEOUT_SECONDS,
    HTML_FILE_EXTENSION,
    PUBLISH_SENTINEL,
    UPLOAD_SCRIPT_RELATIVE_PATH,
)


def _read_hook_payload() -> dict[str, object]:
    """Read the PostToolUse JSON payload from stdin. Empty/invalid payload exits clean."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as decode_error:
        logging.warning("doc_gist_auto_publish: invalid JSON payload: %s", decode_error)
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)
    return payload


def _resolve_target_path(payload: dict[str, object]) -> Path | None:
    """Extract a writable .html file path from the hook payload, or None to skip."""
    if payload.get("tool_name") not in ALL_TARGET_TOOL_NAMES:
        return None
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return None
    raw_path = tool_input.get("file_path", "")
    if not isinstance(raw_path, str) or not raw_path.lower().endswith(HTML_FILE_EXTENSION):
        return None
    candidate = Path(raw_path)
    if not candidate.is_file():
        return None
    return candidate


def _has_publish_sentinel(target_path: Path) -> bool:
    """Read the HTML and check for the publish marker."""
    try:
        contents = target_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logging.warning("doc_gist_auto_publish: cannot read %s", target_path)
        return False
    return PUBLISH_SENTINEL in contents


def _resolve_upload_script() -> Path:
    """Locate the gist_upload.py script bundled with the doc-gist skill."""
    plugin_root_argument = sys.argv[1] if len(sys.argv) > 1 else None
    if plugin_root_argument:
        return Path(plugin_root_argument) / UPLOAD_SCRIPT_RELATIVE_PATH
    plugin_root_directory = Path(__file__).resolve().parent.parent.parent
    return plugin_root_directory / UPLOAD_SCRIPT_RELATIVE_PATH


def _invoke_upload(
    script_path: Path,
    target_path: Path,
    out_stream: IO[str],
    err_stream: IO[str],
) -> None:
    """Run gist_upload.py against target_path and surface its URLs to the harness."""
    try:
        completed = subprocess.run(
            [sys.executable, str(script_path), "--input", str(target_path), "--no-open"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=HOOK_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        logging.warning("doc_gist_auto_publish: gist_upload script not found: %s", script_path)
        return
    except subprocess.TimeoutExpired:
        logging.warning("doc_gist_auto_publish: gist_upload timed out after %ds", HOOK_SUBPROCESS_TIMEOUT_SECONDS)
        return
    if completed.stderr:
        err_stream.write(completed.stderr)
    if completed.returncode != 0:
        logging.warning("doc_gist_auto_publish: gist_upload exited %d", completed.returncode)
        return
    if completed.stdout:
        out_stream.write(completed.stdout)


def main() -> None:
    """Entry point — process one PostToolUse event, exit 0 always.

    Returns:
        None — exits 0 on success or when no action is needed.
    """
    payload = _read_hook_payload()
    target_path = _resolve_target_path(payload)
    if target_path is None:
        sys.exit(0)
    if not _has_publish_sentinel(target_path):
        sys.exit(0)
    script_path = _resolve_upload_script()
    if not script_path.is_file():
        logging.warning("doc_gist_auto_publish: missing %s", script_path)
        sys.exit(0)
    _invoke_upload(script_path, target_path, sys.stdout, sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
