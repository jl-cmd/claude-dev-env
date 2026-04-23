"""Discover every open pull request across a list of owner scopes.

Shells out to ``gh search prs --owner <owner> --state open --json ...`` once per
owner, parses the JSON output, and flattens each entry to a uniform dict shape.
The module is stateless, takes no filesystem side effects, and exposes a single
``discover_open_prs`` entry point consumed by the monitor-open-prs skill.
"""

from __future__ import annotations

import json
import subprocess


def build_gh_search_argv(owner: str) -> list[str]:
    gh_command_name = "gh"
    search_subcommand = ("search", "prs")
    owner_flag = "--owner"
    state_flag = "--state"
    state_open_value = "open"
    json_fields_flag = "--json"
    json_fields_value = "number,repository,url,headRefName,baseRefName"
    return [
        gh_command_name,
        *search_subcommand,
        owner_flag,
        owner,
        state_flag,
        state_open_value,
        json_fields_flag,
        json_fields_value,
    ]


def split_repository_name(name_with_owner: str) -> tuple[str, str]:
    repo_separator = "/"
    if repo_separator not in name_with_owner:
        return "", name_with_owner
    owner_segment, repository_segment = name_with_owner.split(repo_separator, 1)
    return owner_segment, repository_segment


def flatten_pr_entry(raw_pr_entry: dict) -> dict:
    name_with_owner = raw_pr_entry.get("repository", {}).get("nameWithOwner", "")
    owner_segment, repository_segment = split_repository_name(name_with_owner)
    return {
        "number": raw_pr_entry.get("number"),
        "owner": owner_segment,
        "repo": repository_segment,
        "head_ref": raw_pr_entry.get("headRefName", ""),
        "base_ref": raw_pr_entry.get("baseRefName", ""),
        "url": raw_pr_entry.get("url", ""),
    }


def fetch_open_prs_for_owner(owner: str) -> list[dict]:
    search_argv = build_gh_search_argv(owner)
    completed_process = subprocess.run(
        search_argv, check=True, capture_output=True, text=True
    )
    raw_pr_entries = json.loads(completed_process.stdout)
    return [flatten_pr_entry(each_entry) for each_entry in raw_pr_entries]


def discover_open_prs(all_owners: list[str]) -> list[dict]:
    all_discovered: list[dict] = []
    for each_owner in all_owners:
        all_discovered.extend(fetch_open_prs_for_owner(each_owner))
    return all_discovered
