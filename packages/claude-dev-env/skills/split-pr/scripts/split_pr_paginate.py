"""Paginated PR changed-file intake at an exact source commit identity.

Uses ``gh api --paginate --slurp`` so every page of the pulls files list is
collected before filtering (cross-page sorts stay correct).
"""

from __future__ import annotations

import json
import subprocess

from config.plan_constants import (
    EXIT_CODE_SUCCESS,
    FILE_KEY_ADDITIONS,
    FILE_KEY_DELETIONS,
    FILE_KEY_PATH,
    FILE_KEY_SHA,
    GH_API,
    GH_COMMAND,
    GH_PAGINATE_FLAG,
    GH_PULLS_FILES_PATH_TEMPLATE,
    GH_SLURP_FLAG,
    UTF8_ENCODING,
)

JsonObject = dict[str, object]


def fetch_all_pr_changed_files(
    owner: str,
    repo: str,
    pr_number: int,
) -> list[JsonObject]:
    """Fetch every changed file across all pages for a pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.

    Returns:
        List of path/additions/deletions/sha maps.

    Raises:
        RuntimeError: When the gh API call fails.
        json.JSONDecodeError: When the response is not JSON.
    """
    api_path = GH_PULLS_FILES_PATH_TEMPLATE.format(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
    )
    all_command = [
        GH_COMMAND,
        GH_API,
        api_path,
        GH_PAGINATE_FLAG,
        GH_SLURP_FLAG,
    ]
    completed = subprocess.run(
        all_command,
        capture_output=True,
        text=True,
        check=False,
        encoding=UTF8_ENCODING,
    )
    if completed.returncode != EXIT_CODE_SUCCESS:
        raise RuntimeError(completed.stderr.strip() or "gh api pulls files failed")
    return parse_paginated_files_payload(completed.stdout)


def parse_paginated_files_payload(raw_json: str) -> list[JsonObject]:
    """Flatten a --slurp JSON array-of-pages into file records.

    Args:
        raw_json: stdout from ``gh api --paginate --slurp``.

    Returns:
        Deduplicated file records in first-seen order.

    Raises:
        ValueError: When the JSON root is not an array of pages or files.
        json.JSONDecodeError: When raw_json is not valid JSON.
    """
    loaded = json.loads(raw_json)
    all_pages: list[object]
    if isinstance(loaded, list) and loaded and isinstance(loaded[0], list):
        all_pages = loaded
    elif isinstance(loaded, list):
        all_pages = [loaded]
    else:
        raise ValueError("paginated payload must be a JSON array")
    all_file_records: list[JsonObject] = []
    all_seen_paths: set[str] = set()
    for each_page in all_pages:
        if not isinstance(each_page, list):
            continue
        for each_file in each_page:
            if not isinstance(each_file, dict):
                continue
            path = each_file.get(FILE_KEY_PATH)
            if not path:
                continue
            path_text = str(path)
            if path_text in all_seen_paths:
                continue
            all_seen_paths.add(path_text)
            all_file_records.append(
                {
                    FILE_KEY_PATH: path_text,
                    FILE_KEY_ADDITIONS: int(each_file.get(FILE_KEY_ADDITIONS, 0) or 0),
                    FILE_KEY_DELETIONS: int(each_file.get(FILE_KEY_DELETIONS, 0) or 0),
                    FILE_KEY_SHA: str(each_file.get(FILE_KEY_SHA, "") or ""),
                }
            )
    return all_file_records
