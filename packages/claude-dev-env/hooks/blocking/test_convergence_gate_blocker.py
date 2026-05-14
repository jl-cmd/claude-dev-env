"""Unit tests for convergence-gate-blocker PreToolUse hook."""

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

import re

_GH_PR_READY_PATTERN = re.compile(r"\bgh\s+pr\s+ready\b(?![^&|;\n]*--undo)")

hook_spec = importlib.util.spec_from_file_location(
    "convergence_gate_blocker",
    _HOOK_DIR / "convergence_gate_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
_resolve_pr_number = hook_module._resolve_pr_number


def test_matches_gh_pr_ready_with_number() -> None:
    assert _GH_PR_READY_PATTERN.search("gh pr ready 418")


def test_matches_gh_pr_ready_without_number() -> None:
    assert _GH_PR_READY_PATTERN.search("gh pr ready")


def test_matches_gh_pr_ready_with_flags() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr ready --undo")


def test_does_not_match_gh_pr_create() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr create --title T")


def test_does_not_match_gh_pr_view() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr view 418")


def test_does_not_match_gh_issue_close() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh issue close 42")


def test_extracts_pr_number_from_command() -> None:
    assert _resolve_pr_number("gh pr ready 418", None) == 418


def test_extracts_pr_number_with_flags() -> None:
    assert _resolve_pr_number("gh pr ready 99 --undo", None) == 99


def test_returns_none_when_no_number_and_no_repo() -> None:
    assert _resolve_pr_number("gh pr ready", "/nonexistent/path") is None


def test_matches_gh_pr_ready_in_compound_command() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr ready --undo && gh pr create")
