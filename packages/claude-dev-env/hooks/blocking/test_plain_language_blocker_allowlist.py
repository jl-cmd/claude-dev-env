"""Tests for the per-project domain-vocabulary allowlist in plain_language_blocker."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

BLOCKER_PATH = Path(__file__).parent / "plain_language_blocker.py"
ALLOWLIST_RELATIVE_PATH = Path(".claude") / "plain-language-allow.json"
ALWAYS_HEAVY_WORD = "utilize"


def _load_blocker() -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        "plain_language_blocker_allowlist_under_test", BLOCKER_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


_BLOCKER = _load_blocker()


def _write_allowlist(project_root: Path, all_words: list[str]) -> None:
    allowlist_path = project_root / ALLOWLIST_RELATIVE_PATH
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist_path.write_text(json.dumps(all_words), encoding="utf-8")


def _write_raw_allowlist(project_root: Path, raw_text: str) -> None:
    allowlist_path = project_root / ALLOWLIST_RELATIVE_PATH
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist_path.write_text(raw_text, encoding="utf-8")


def _markdown_write_payload(project_root: Path, prose: str) -> dict[str, object]:
    document_path = project_root / "docs" / "notes.md"
    return {
        "tool_name": "Write",
        "cwd": str(project_root),
        "tool_input": {"file_path": str(document_path), "content": prose},
    }


def _ask_user_question_payload(project_root: Path, prose: str) -> dict[str, object]:
    return {
        "tool_name": "AskUserQuestion",
        "cwd": str(project_root),
        "tool_input": {"questions": [{"question": prose, "options": []}]},
    }


def test_allowlisted_word_passes_in_markdown_write(tmp_path: Path) -> None:
    prose = "Please submit the release notes."
    project_without_allowlist = tmp_path / "control"
    project_without_allowlist.mkdir()
    project_with_allowlist = tmp_path / "domain"
    project_with_allowlist.mkdir()
    _write_allowlist(project_with_allowlist, ["submit"])

    control_deny_reason = _BLOCKER.evaluate(
        _markdown_write_payload(project_without_allowlist, prose)
    )
    allowlisted_deny_reason = _BLOCKER.evaluate(
        _markdown_write_payload(project_with_allowlist, prose)
    )

    assert control_deny_reason is not None and "submit" in control_deny_reason
    assert allowlisted_deny_reason is None


def test_allowlisted_word_passes_in_ask_user_question(tmp_path: Path) -> None:
    prose = "Which theme should we identify first?"
    project_without_allowlist = tmp_path / "control"
    project_without_allowlist.mkdir()
    project_with_allowlist = tmp_path / "domain"
    project_with_allowlist.mkdir()
    _write_allowlist(project_with_allowlist, ["identify"])

    control_deny_reason = _BLOCKER.evaluate(
        _ask_user_question_payload(project_without_allowlist, prose)
    )
    allowlisted_deny_reason = _BLOCKER.evaluate(
        _ask_user_question_payload(project_with_allowlist, prose)
    )

    assert control_deny_reason is not None and "identify" in control_deny_reason
    assert allowlisted_deny_reason is None


def test_non_allowlisted_heavy_word_still_blocked(tmp_path: Path) -> None:
    _write_allowlist(tmp_path, ["submit"])

    deny_reason = _BLOCKER.evaluate(
        _markdown_write_payload(tmp_path, f"Please {ALWAYS_HEAVY_WORD} the cache now.")
    )

    assert deny_reason is not None and ALWAYS_HEAVY_WORD in deny_reason


def test_allowlist_match_is_case_insensitive(tmp_path: Path) -> None:
    prose = "Please SUBMIT the release notes."
    project_without_allowlist = tmp_path / "control"
    project_without_allowlist.mkdir()
    project_with_allowlist = tmp_path / "domain"
    project_with_allowlist.mkdir()
    _write_allowlist(project_with_allowlist, ["Submit"])

    control_deny_reason = _BLOCKER.evaluate(
        _markdown_write_payload(project_without_allowlist, prose)
    )
    allowlisted_deny_reason = _BLOCKER.evaluate(
        _markdown_write_payload(project_with_allowlist, prose)
    )

    assert control_deny_reason is not None and "submit" in control_deny_reason
    assert allowlisted_deny_reason is None


def test_malformed_allowlist_json_is_ignored(tmp_path: Path) -> None:
    _write_raw_allowlist(tmp_path, "{ this is not valid json ")

    deny_reason = _BLOCKER.evaluate(
        _markdown_write_payload(tmp_path, "Please submit the release notes.")
    )

    assert deny_reason is not None and "submit" in deny_reason


def test_allowlist_in_a_different_project_root_is_not_applied(tmp_path: Path) -> None:
    project_with_allowlist = tmp_path / "project_a"
    project_without_allowlist = tmp_path / "project_b"
    project_with_allowlist.mkdir()
    project_without_allowlist.mkdir()
    _write_allowlist(project_with_allowlist, ["submit"])

    deny_reason = _BLOCKER.evaluate(
        _markdown_write_payload(project_without_allowlist, "Please submit the notes.")
    )

    assert deny_reason is not None and "submit" in deny_reason


def test_find_banned_terms_skips_allowlisted_terms() -> None:
    matched_without_allowlist = _BLOCKER.find_banned_terms("Please submit the notes.")
    matched_with_allowlist = _BLOCKER.find_banned_terms(
        "Please submit the notes.", frozenset({"submit"})
    )

    assert any(each_term == "submit" for each_term, _ in matched_without_allowlist)
    assert all(each_term != "submit" for each_term, _ in matched_with_allowlist)
