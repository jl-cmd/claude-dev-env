"""Entry-flow tests for the proof-of-work gates in pr_description_enforcer.

Each test drives hook main() with a real Bash PreToolUse payload on stdin,
mirroring test_pr_description_enforcer.py. The single gh subprocess boundary
in pr_description_proof_of_work is patched with a fake runner, so command
recognition, body extraction, and the proof audit run the production paths.
"""

import contextlib
import importlib.util
import io
import json
import pathlib
import sys
from unittest.mock import patch

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_ROOT = _HOOK_DIR.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

from blocking import pr_description_proof_of_work as proof_module  # noqa: E402
from blocking import pr_description_readability as readability_module  # noqa: E402

hook_spec = importlib.util.spec_from_file_location(
    "pr_description_enforcer_proof_gate",
    _HOOK_DIR / "pr_description_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)


@pytest.fixture(autouse=True)
def _isolate_readability_state(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect the three readability state files to per-test temp paths.

    The enabled file is written with enabled=False so readability scoring
    stays out of these entry-flow tests and the live state directory is
    never touched.
    """
    per_test_state_dir = tmp_path_factory.mktemp("proof_gate_readability_state")
    monkeypatch.setattr(
        readability_module, "READABILITY_STATE_FILE", per_test_state_dir / "strikes.json"
    )
    monkeypatch.setattr(
        readability_module,
        "READABILITY_THRESHOLD_OVERRIDE_FILE",
        per_test_state_dir / "overrides.json",
    )
    enabled_path = per_test_state_dir / "enabled.json"
    enabled_path.write_text(json.dumps({"enabled": False}))
    monkeypatch.setattr(readability_module, "READABILITY_ENABLED_STATE_FILE", enabled_path)


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

ORDINARY_COMMENT_BODY = (
    "The retry logic here mirrors what the uploader does for chunked "
    "transfers, so the two stay in step."
)


def _run_hook_main_with_command(command: str) -> str:
    hook_input_json = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    captured_stdout = io.StringIO()
    with (
        patch("sys.stdin", io.StringIO(hook_input_json)),
        patch("sys.stdout", captured_stdout),
        contextlib.suppress(SystemExit),
    ):
        hook_module.main()
    return captured_stdout.getvalue()


def _install_fake_gh_responses(monkeypatch, all_comment_bodies, all_diff_names):
    all_comment_records = [{"body": each_body} for each_body in all_comment_bodies]

    def _fake_run_gh_command(all_gh_arguments):
        if all_gh_arguments and all_gh_arguments[0] == "api":
            return json.dumps([all_comment_records])
        if "--name-only" in all_gh_arguments:
            return "\n".join(all_diff_names)
        if list(all_gh_arguments[:2]) == ["pr", "view"]:
            return json.dumps({"number": 123})
        if list(all_gh_arguments[:2]) == ["pr", "diff"]:
            return ""
        return None

    monkeypatch.setattr(proof_module, "_run_gh_command", _fake_run_gh_command)


def test_main_blocks_gh_pr_ready_without_proof_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_gh_responses(monkeypatch, [], ["src/parser.py"])
    decision_output = _run_hook_main_with_command("gh pr ready 123")
    assert "deny" in decision_output
    assert "proof" in decision_output.lower()


def test_main_allows_gh_pr_ready_with_passing_proof_comment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_gh_responses(monkeypatch, [PASSING_PROOF_COMMENT_BODY], ["src/parser.py"])
    decision_output = _run_hook_main_with_command("gh pr ready 123")
    assert "deny" not in decision_output


def test_main_allows_complete_proof_comment_post(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_gh_responses(monkeypatch, [], ["src/parser.py"])
    body_file = tmp_path / "proof.md"
    body_file.write_text(PASSING_PROOF_COMMENT_BODY)
    decision_output = _run_hook_main_with_command(f"gh pr comment 123 --body-file {body_file}")
    assert "deny" not in decision_output


def test_main_blocks_proof_comment_missing_visual_on_visual_change(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_gh_responses(monkeypatch, [], ["assets/icon.png"])
    body_file = tmp_path / "proof.md"
    body_file.write_text(PASSING_PROOF_COMMENT_BODY)
    decision_output = _run_hook_main_with_command(f"gh pr comment 123 --body-file {body_file}")
    assert "deny" in decision_output
    assert "visual" in decision_output


def test_main_leaves_ordinary_comment_untouched(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_recorded_calls: list[list[str]] = []

    def _recording_run_gh_command(all_gh_arguments):
        all_recorded_calls.append(list(all_gh_arguments))

    monkeypatch.setattr(proof_module, "_run_gh_command", _recording_run_gh_command)
    body_file = tmp_path / "comment.md"
    body_file.write_text(ORDINARY_COMMENT_BODY)
    decision_output = _run_hook_main_with_command(f"gh pr comment 123 --body-file {body_file}")
    assert "deny" not in decision_output
    assert all_recorded_calls == []


def test_main_allows_gh_pr_ready_undo_without_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    all_recorded_calls: list[list[str]] = []

    def _recording_run_gh_command(all_gh_arguments):
        all_recorded_calls.append(list(all_gh_arguments))

    monkeypatch.setattr(proof_module, "_run_gh_command", _recording_run_gh_command)
    decision_output = _run_hook_main_with_command("gh pr ready 123 --undo")
    assert "deny" not in decision_output
    assert all_recorded_calls == []
