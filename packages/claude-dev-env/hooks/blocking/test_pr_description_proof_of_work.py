"""Behavior tests for the proof-of-work comment audit and gh pr ready gate.

Each test drives the public audit surface of pr_description_proof_of_work
with real comment bodies. The single gh subprocess boundary is patched with
a fake runner, so parsing, part detection, and gate decisions all run the
production code paths.
"""

import json
import pathlib
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_ROOT = _HOOK_DIR.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from blocking import pr_description_proof_of_work as proof_module  # noqa: E402
from blocking.pr_description_proof_of_work import (  # noqa: E402
    audit_proof_comment_body,
    evaluate_pr_ready_gate,
    is_pr_ready_command,
    is_proof_shaped_body,
)

PASSING_PROOF_COMMENT_BODY = (
    "## Summary\n\n"
    "Recolored the launcher icons and checked every produced asset by hand "
    "against the palette the plan names.\n\n"
    "## Verification\n\n"
    "```\n"
    "C:\\Python313\\python.exe scripts/recolor.py --input themes/dawn\n"
    "```\n\n"
    "| Artifact | Measured |\n"
    "| --- | --- |\n"
    "| icons.zip | 48 files, 412,993 bytes |\n\n"
    "This advances phase 2 of issue #12.\n\n"
    "Known gap: the offline proof cannot show the on-device rendering; the "
    "store preview covers that.\n"
)

VISUAL_PROOF_COMMENT_BODY = (
    PASSING_PROOF_COMMENT_BODY + "\n![](https://placehold.co/20x20/AABBCC/AABBCC.png)\n"
)

BARE_PROOF_COMMENT_BODY = "## Verification\n\nLooks good overall to me.\n"

ORDINARY_COMMENT_BODY = (
    "The retry logic here mirrors what the uploader does for chunked "
    "transfers, so the two stay in step."
)


def _install_fake_gh(monkeypatch, all_comment_bodies, all_diff_names, diff_text):
    all_comment_records = [{"body": each_body} for each_body in all_comment_bodies]

    def _fake_run_gh_command(all_gh_arguments):
        if all_gh_arguments and all_gh_arguments[0] == "api":
            return json.dumps([all_comment_records])
        if list(all_gh_arguments[:2]) == ["pr", "view"]:
            return json.dumps({"number": 77})
        if "--name-only" in all_gh_arguments:
            return "\n".join(all_diff_names)
        if list(all_gh_arguments[:2]) == ["pr", "diff"]:
            return diff_text
        return None

    monkeypatch.setattr(proof_module, "_run_gh_command", _fake_run_gh_command)


def test_is_proof_shaped_body_detects_verification_heading() -> None:
    assert is_proof_shaped_body(PASSING_PROOF_COMMENT_BODY)


def test_is_proof_shaped_body_skips_ordinary_comment() -> None:
    assert not is_proof_shaped_body(ORDINARY_COMMENT_BODY)


def test_is_pr_ready_command_matches_ready() -> None:
    assert is_pr_ready_command("gh pr ready 123")


def test_is_pr_ready_command_skips_undo() -> None:
    assert not is_pr_ready_command("gh pr ready 123 --undo")


def test_audit_passes_complete_proof_on_non_visual_change(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_gh(monkeypatch, [], ["src/parser.py"], "+ plain code line")
    assert audit_proof_comment_body(PASSING_PROOF_COMMENT_BODY, 123) == []


def test_audit_flags_missing_visual_on_image_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_gh(monkeypatch, [], ["assets/icon.png"], "")
    all_missing_parts = audit_proof_comment_body(PASSING_PROOF_COMMENT_BODY, 123)
    assert any("visual" in each_part for each_part in all_missing_parts)


def test_audit_accepts_image_embed_on_image_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_gh(monkeypatch, [], ["assets/icon.png"], "")
    assert audit_proof_comment_body(VISUAL_PROOF_COMMENT_BODY, 123) == []


def test_audit_detects_visual_change_from_hex_colors(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_gh(monkeypatch, [], ["src/theme.py"], '+ accent = "#AABBCC"')
    all_missing_parts = audit_proof_comment_body(PASSING_PROOF_COMMENT_BODY, 123)
    assert any("visual" in each_part for each_part in all_missing_parts)


def test_audit_names_every_missing_part_of_bare_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_gh(monkeypatch, [], ["src/parser.py"], "")
    all_missing_parts = audit_proof_comment_body(BARE_PROOF_COMMENT_BODY, 123)
    assert len(all_missing_parts) == 4


def test_ready_gate_blocks_when_no_proof_comment_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_gh(monkeypatch, [ORDINARY_COMMENT_BODY], ["src/parser.py"], "")
    denial_reason = evaluate_pr_ready_gate("gh pr ready 123")
    assert denial_reason is not None
    assert "proof" in denial_reason.lower()


def test_ready_gate_allows_with_passing_proof_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_gh(monkeypatch, [PASSING_PROOF_COMMENT_BODY], ["src/parser.py"], "")
    assert evaluate_pr_ready_gate("gh pr ready 123") is None


def test_ready_gate_blocks_when_proof_comment_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_gh(monkeypatch, [BARE_PROOF_COMMENT_BODY], ["src/parser.py"], "")
    denial_reason = evaluate_pr_ready_gate("gh pr ready 123")
    assert denial_reason is not None
    assert "123" in denial_reason
    assert "proof" in denial_reason.lower()


def test_ready_gate_fails_open_when_gh_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proof_module, "_run_gh_command", lambda all_gh_arguments: None)
    assert evaluate_pr_ready_gate("gh pr ready 123") is None


def test_ready_gate_resolves_pr_number_from_current_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_gh(monkeypatch, [PASSING_PROOF_COMMENT_BODY], ["src/parser.py"], "")
    assert evaluate_pr_ready_gate("gh pr ready") is None
