"""Resolve Zoekt-indexed filesystem roots from environment or JSON file (no built-in roots in this package)."""

import json
import os
from functools import lru_cache
from pathlib import Path

from content_search_zoekt_indexed_paths import normalize_path


def _environment_variable_indexed_roots() -> str:
    return "ZOEKT_REDIRECT_INDEXED_ROOTS"


def _environment_variable_roots_file() -> str:
    return "ZOEKT_REDIRECT_INDEXED_ROOTS_FILE"


def _json_object_roots_key() -> str:
    return "roots"


def _default_config_relative_parts() -> tuple[str, str]:
    return (".claude", "zoekt-indexed-roots.json")


def _built_in_fallback_roots() -> tuple[str, ...]:
    return ()


def _parse_json_roots_list(raw: str) -> list[str] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    if not all(isinstance(item, str) for item in parsed):
        return None
    return list(parsed)


def _config_file_path() -> Path:
    override = os.environ.get(_environment_variable_roots_file())
    if override is not None and override.strip() != "":
        return Path(override).expanduser()
    relative_dot_claude, relative_file_name = _default_config_relative_parts()
    return Path.home() / relative_dot_claude / relative_file_name


def _roots_from_json_file() -> list[str] | None:
    path = _config_file_path()
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    roots_key = _json_object_roots_key()
    roots_value = data.get(roots_key)
    if roots_value is None:
        return None
    if not isinstance(roots_value, list):
        return None
    if not all(isinstance(item, str) for item in roots_value):
        return None
    return list(roots_value)


def _roots_from_environment_variable() -> list[str] | None:
    variable_name = _environment_variable_indexed_roots()
    if variable_name not in os.environ:
        return None
    raw = os.environ.get(variable_name, "")
    if raw.strip() == "":
        return []
    parsed = _parse_json_roots_list(raw)
    if parsed is None:
        return None
    return parsed


def _expand_root_to_prefix_variants(root: str) -> list[str]:
    trimmed = root.strip()
    if trimmed == "":
        return []
    norm = normalize_path(trimmed)
    if not norm.endswith("/"):
        norm = norm + "/"
    variants = [norm]
    if len(norm) >= 3 and norm[1] == ":" and norm[0].isalpha() and norm[2] == "/":
        drive_letter = norm[0]
        remainder = norm[2:]
        wsl_prefix = f"/mnt/{drive_letter}{remainder}"
        if wsl_prefix not in variants:
            variants.append(wsl_prefix)
    return variants


def _expand_all_roots(raw_roots: list[str]) -> tuple[str, ...]:
    prefixes: list[str] = []
    for root in raw_roots:
        prefixes.extend(_expand_root_to_prefix_variants(root))
    unique = frozenset(prefixes)
    return tuple(sorted(unique, key=len, reverse=True))


def _raw_roots_resolution_order() -> list[str]:
    from_env = _roots_from_environment_variable()
    if from_env is not None:
        return from_env
    from_file = _roots_from_json_file()
    if from_file is not None:
        return from_file
    return list(_built_in_fallback_roots())


@lru_cache(maxsize=1)
def indexed_root_prefixes() -> tuple[str, ...]:
    raw_roots = _raw_roots_resolution_order()
    return _expand_all_roots(raw_roots)


def clear_indexed_root_prefixes_cache() -> None:
    indexed_root_prefixes.cache_clear()
