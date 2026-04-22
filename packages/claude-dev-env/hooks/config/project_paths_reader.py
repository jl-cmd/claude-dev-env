"""Load the per-user project-path registry from ~/.claude/project-paths.json."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from config.dynamic_stderr_handler import DynamicStderrHandler
from config.setup_project_paths_constants import META_KEY, UTF8_ENCODING


_logger = logging.getLogger("project_paths_reader")
if not _logger.handlers:
    _stderr_handler = DynamicStderrHandler()
    _stderr_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    _logger.addHandler(_stderr_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def registry_file_path() -> Path:
    """Return the canonical path to ~/.claude/project-paths.json."""
    return Path.home() / ".claude" / "project-paths.json"


def _default_config_path() -> Path:
    return registry_file_path()


def _normalize_path_separators(raw_path: str) -> str:
    forward_slash_form = raw_path.replace("\\", "/")
    return os.path.normcase(os.path.normpath(forward_slash_form)).replace("\\", "/")


def load_registry(config_path: Path | None = None) -> dict[str, str]:
    """Return the name-to-absolute-path mapping with the _meta key stripped.

    Returns an empty dict when the file is missing, unreadable, malformed,
    or otherwise invalid. Logs one line to stderr when the file cannot be
    read or contains malformed JSON.
    """
    resolved_path = config_path if config_path is not None else _default_config_path()
    if not resolved_path.is_file():
        return {}
    try:
        raw_text = resolved_path.read_text(encoding=UTF8_ENCODING)
    except OSError as e:
        _logger.error("cannot read %s: %s", resolved_path, e)
        return {}
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        _logger.error("malformed JSON in %s: %s", resolved_path, e)
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        each_key: each_value
        for each_key, each_value in parsed.items()
        if each_key != META_KEY
        and isinstance(each_key, str)
        and isinstance(each_value, str)
    }


def registry_contains_path(known_registry: dict[str, str], path_to_find: str) -> bool:
    """Return True when the given path appears as any registry value.

    Normalizes both sides before comparing so Windows and POSIX separator
    forms of the same path compare equal.
    """
    normalized_target = _normalize_path_separators(path_to_find)
    for each_registered_path in known_registry.values():
        if _normalize_path_separators(each_registered_path) == normalized_target:
            return True
    return False
