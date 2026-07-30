"""Tests for the per-project domain-vocabulary allowlist in plain_language_blocker."""

import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

BLOCKER_PATH = Path(__file__).parent / "plain_language_blocker.py"
ALLOWLIST_RELATIVE_PATH = Path(".claude") / "plain-language-allow.json"
ALWAYS_HEAVY_WORD = "utilize"
_PROSE_STYLE_ENFORCEMENT_ENVIRONMENT = {
    "CLAUDE_PROSE_STYLE_ENFORCEMENT": "1",
}


def _load_blocker() -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        "plain_language_blocker_allowlist_under_test", BLOCKER_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


_BLOCKER = _load_blocker()


def _evaluate_advisory(
    payload_by_key: dict[str, object],
) -> tuple[str | None, str | None]:
    """Return (deny_reason, advisory_message) with prose enforcement on.

    Heavy words never deny (OP-07D); allowlist coverage asserts on the advisory
    message and on ``find_banned_terms`` so the scanner still sees domain terms.
    """
    with patch.dict(os.environ, _PROSE_STYLE_ENFORCEMENT_ENVIRONMENT):
        return _BLOCKER.evaluate_with_advisory(payload_by_key)


def _init_repo(root: Path) -> Path:
    (root / ".git").mkdir(parents=True, exist_ok=True)
    return root


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
    project_without_allowlist = _init_repo(tmp_path / "control")
    project_with_allowlist = _init_repo(tmp_path / "domain")
    _write_allowlist(project_with_allowlist, ["submit"])

    control_deny, control_advisory = _evaluate_advisory(
        _markdown_write_payload(project_without_allowlist, prose)
    )
    allowlisted_deny, allowlisted_advisory = _evaluate_advisory(
        _markdown_write_payload(project_with_allowlist, prose)
    )

    assert control_deny is None
    assert control_advisory is not None and "submit" in control_advisory
    assert allowlisted_deny is None
    assert allowlisted_advisory is None


def test_allowlisted_word_passes_in_ask_user_question(tmp_path: Path) -> None:
    prose = "Which theme should we identify first?"
    project_without_allowlist = _init_repo(tmp_path / "control")
    project_with_allowlist = _init_repo(tmp_path / "domain")
    _write_allowlist(project_with_allowlist, ["identify"])

    control_deny, control_advisory = _evaluate_advisory(
        _ask_user_question_payload(project_without_allowlist, prose)
    )
    allowlisted_deny, allowlisted_advisory = _evaluate_advisory(
        _ask_user_question_payload(project_with_allowlist, prose)
    )

    assert control_deny is None
    assert control_advisory is not None and "identify" in control_advisory
    assert allowlisted_deny is None
    assert allowlisted_advisory is None


def test_non_allowlisted_heavy_word_still_flagged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_allowlist(tmp_path, ["submit"])

    deny_reason, advisory_message = _evaluate_advisory(
        _markdown_write_payload(tmp_path, f"Please {ALWAYS_HEAVY_WORD} the cache now.")
    )

    assert deny_reason is None
    assert advisory_message is not None and ALWAYS_HEAVY_WORD in advisory_message


def test_allowlist_match_is_case_insensitive(tmp_path: Path) -> None:
    prose = "Please SUBMIT the release notes."
    project_without_allowlist = _init_repo(tmp_path / "control")
    project_with_allowlist = _init_repo(tmp_path / "domain")
    _write_allowlist(project_with_allowlist, ["Submit"])

    control_deny, control_advisory = _evaluate_advisory(
        _markdown_write_payload(project_without_allowlist, prose)
    )
    allowlisted_deny, allowlisted_advisory = _evaluate_advisory(
        _markdown_write_payload(project_with_allowlist, prose)
    )

    assert control_deny is None
    assert control_advisory is not None and "submit" in control_advisory
    assert allowlisted_deny is None
    assert allowlisted_advisory is None


def test_malformed_allowlist_json_is_ignored(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_raw_allowlist(tmp_path, "{ this is not valid json ")

    deny_reason, advisory_message = _evaluate_advisory(
        _markdown_write_payload(tmp_path, "Please submit the release notes.")
    )

    assert deny_reason is None
    assert advisory_message is not None and "submit" in advisory_message


def test_allowlist_in_a_different_project_root_is_not_applied(tmp_path: Path) -> None:
    project_with_allowlist = _init_repo(tmp_path / "project_a")
    project_without_allowlist = _init_repo(tmp_path / "project_b")
    _write_allowlist(project_with_allowlist, ["submit"])

    deny_reason, advisory_message = _evaluate_advisory(
        _markdown_write_payload(project_without_allowlist, "Please submit the notes.")
    )

    assert deny_reason is None
    assert advisory_message is not None and "submit" in advisory_message


def test_allowlist_above_the_repo_root_is_not_applied(tmp_path: Path) -> None:
    _write_allowlist(tmp_path, ["submit"])
    repository_root = _init_repo(tmp_path / "repo")

    deny_reason, advisory_message = _evaluate_advisory(
        _markdown_write_payload(repository_root, "Please submit the notes.")
    )

    assert deny_reason is None
    assert advisory_message is not None and "submit" in advisory_message


def test_allowlist_at_the_repo_root_is_applied(tmp_path: Path) -> None:
    repository_root = _init_repo(tmp_path / "repo")
    _write_allowlist(repository_root, ["submit"])

    deny_reason, advisory_message = _evaluate_advisory(
        _markdown_write_payload(repository_root, "Please submit the notes.")
    )

    assert deny_reason is None
    assert advisory_message is None


def test_allowlist_without_a_repo_root_is_not_applied(tmp_path: Path) -> None:
    """An allowlist only applies when the walk finds a ``.git`` repository root.

    The upward walk can hit a personal home ``.git`` on some developer machines,
    so this case stubs the finder to the no-repository outcome rather than
    relying on the ambient filesystem.
    """
    _write_allowlist(tmp_path, ["submit"])

    with patch.object(_BLOCKER, "_find_project_allowlist_file", return_value=None):
        deny_reason, advisory_message = _evaluate_advisory(
            _markdown_write_payload(tmp_path, "Please submit the notes.")
        )

    assert deny_reason is None
    assert advisory_message is not None and "submit" in advisory_message


def test_find_banned_terms_skips_allowlisted_terms() -> None:
    matched_without_allowlist = _BLOCKER.find_banned_terms("Please submit the notes.")
    matched_with_allowlist = _BLOCKER.find_banned_terms(
        "Please submit the notes.", frozenset({"submit"})
    )

    assert any(each_term == "submit" for each_term, _ in matched_without_allowlist)
    assert all(each_term != "submit" for each_term, _ in matched_with_allowlist)
