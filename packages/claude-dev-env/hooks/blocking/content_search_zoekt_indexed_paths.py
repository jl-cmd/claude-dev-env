"""Normalize paths and test membership under Zoekt-indexed roots (from env, JSON file, or defaults)."""

import re


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").lower()


def is_specific_file(path: str) -> bool:
    file_extension_pattern = re.compile(r"\.\w{1,10}$")
    return bool(file_extension_pattern.search(path))


def is_in_indexed_repo(path: str) -> bool:
    from content_search_zoekt_indexed_roots_config import indexed_root_prefixes

    norm = normalize_path(path)
    if not norm.endswith("/"):
        norm += "/"
    for prefix in indexed_root_prefixes():
        if norm.startswith(prefix):
            return True
    return False
