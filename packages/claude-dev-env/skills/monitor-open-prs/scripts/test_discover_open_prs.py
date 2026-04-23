"""Tests for discover_open_prs.py — merges gh-search output across owners."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest


def _load_discovery_module():
    scripts_directory = pathlib.Path(__file__).parent
    sys.path.insert(0, str(scripts_directory))
    module_path = scripts_directory / "discover_open_prs.py"
    module_spec = importlib.util.spec_from_file_location(
        "discover_open_prs", module_path
    )
    loaded_module = importlib.util.module_from_spec(module_spec)
    sys.modules["discover_open_prs"] = loaded_module
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


discover_open_prs = _load_discovery_module()


def _make_fake_gh(responses_by_owner: dict):
    """Return a callable whose behavior mocks subprocess.run for gh search."""

    class FakeCompletedProcess:
        def __init__(self, stdout_text: str):
            self.stdout = stdout_text
            self.returncode = 0

    def fake_run(command_argv, check, capture_output, text):
        owner = _extract_owner_argument(command_argv)
        stdout_text = json.dumps(responses_by_owner.get(owner, []))
        return FakeCompletedProcess(stdout_text)

    return fake_run


def _extract_owner_argument(command_argv) -> str:
    for each_index, each_token in enumerate(command_argv):
        if each_token == "--owner":
            return command_argv[each_index + 1]
    return ""


class TestDiscoverOpenPrsBothOwnersReturnResults:
    def test_merges_prs_across_both_owners(self, monkeypatch):
        first_owner_prs = [
            {
                "number": 1,
                "repository": {"nameWithOwner": "jl-cmd/alpha"},
                "url": "https://github.com/jl-cmd/alpha/pull/1",
                "headRefName": "feat-one",
                "baseRefName": "main",
            }
        ]
        second_owner_prs = [
            {
                "number": 2,
                "repository": {"nameWithOwner": "JonEcho/beta"},
                "url": "https://github.com/JonEcho/beta/pull/2",
                "headRefName": "feat-two",
                "baseRefName": "main",
            }
        ]
        fake_run = _make_fake_gh(
            {"jl-cmd": first_owner_prs, "JonEcho": second_owner_prs}
        )
        monkeypatch.setattr(discover_open_prs.subprocess, "run", fake_run)

        all_discovered = discover_open_prs.discover_open_prs(
            all_owners=["jl-cmd", "JonEcho"]
        )

        assert len(all_discovered) == 2
        discovered_numbers = sorted(each["number"] for each in all_discovered)
        assert discovered_numbers == [1, 2]


class TestDiscoverOpenPrsOneOwnerEmpty:
    def test_handles_single_owner_returning_empty_list(self, monkeypatch):
        first_owner_prs = [
            {
                "number": 5,
                "repository": {"nameWithOwner": "jl-cmd/gamma"},
                "url": "https://github.com/jl-cmd/gamma/pull/5",
                "headRefName": "feat-five",
                "baseRefName": "main",
            }
        ]
        fake_run = _make_fake_gh({"jl-cmd": first_owner_prs, "JonEcho": []})
        monkeypatch.setattr(discover_open_prs.subprocess, "run", fake_run)

        all_discovered = discover_open_prs.discover_open_prs(
            all_owners=["jl-cmd", "JonEcho"]
        )

        assert len(all_discovered) == 1
        assert all_discovered[0]["number"] == 5


class TestDiscoverOpenPrsBothEmpty:
    def test_returns_empty_list_when_no_owner_has_open_prs(self, monkeypatch):
        fake_run = _make_fake_gh({"jl-cmd": [], "JonEcho": []})
        monkeypatch.setattr(discover_open_prs.subprocess, "run", fake_run)

        all_discovered = discover_open_prs.discover_open_prs(
            all_owners=["jl-cmd", "JonEcho"]
        )

        assert all_discovered == []


class TestDiscoverOpenPrsEntryShape:
    def test_each_entry_exposes_number_owner_repo_refs_and_url(self, monkeypatch):
        fake_run = _make_fake_gh(
            {
                "jl-cmd": [
                    {
                        "number": 42,
                        "repository": {"nameWithOwner": "jl-cmd/demo"},
                        "url": "https://github.com/jl-cmd/demo/pull/42",
                        "headRefName": "feat-demo",
                        "baseRefName": "main",
                    }
                ],
                "JonEcho": [],
            }
        )
        monkeypatch.setattr(discover_open_prs.subprocess, "run", fake_run)

        all_discovered = discover_open_prs.discover_open_prs(
            all_owners=["jl-cmd", "JonEcho"]
        )

        assert len(all_discovered) == 1
        only_entry = all_discovered[0]
        assert only_entry["number"] == 42
        assert only_entry["owner"] == "jl-cmd"
        assert only_entry["repo"] == "demo"
        assert only_entry["head_ref"] == "feat-demo"
        assert only_entry["base_ref"] == "main"
        assert only_entry["url"].endswith("/pull/42")
