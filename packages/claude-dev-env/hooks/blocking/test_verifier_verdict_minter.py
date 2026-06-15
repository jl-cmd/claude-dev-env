"""Tests for the agent-type gate in verifier_verdict_minter.

The minter mints a verdict only for a code-verifier stop event. The live
SubagentStop payload names the stopping subagent by ``agent_id`` and carries
no flat agent-type key, so the minter recovers the spawning agent type from
the parent transcript: it walks the parent transcript for the completion
record whose ``agentId`` matches the payload and reads that record's sibling
``agentType``. These tests build a faithful parent transcript and assert the
minter gates on the resolved type and on the shared MINTING_AGENT_TYPE
constant, so a rename in config propagates to the minter without a second
edit. One test proves that only a structured ``agentType`` key resolves: a
text block that merely quotes the identity keys mints nothing. A further test
holds the shipped settings.json to the minter docstring's anti-forgery claim:
the main session is denied writes to the verdict directory, so only this hook
can mint a passing verdict.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

_SETTINGS_PATH = _HOOK_DIR.parent.parent / "settings.json"

minter_spec = importlib.util.spec_from_file_location(
    "verifier_verdict_minter",
    _HOOK_DIR / "verifier_verdict_minter.py",
)
assert minter_spec is not None
assert minter_spec.loader is not None
minter_module = importlib.util.module_from_spec(minter_spec)
minter_spec.loader.exec_module(minter_module)
mint_for_payload = minter_module.mint_for_payload
resolved_subagent_type = minter_module.resolved_subagent_type

constants_spec = importlib.util.spec_from_file_location(
    "verified_commit_constants",
    _HOOK_DIR / "config" / "verified_commit_constants.py",
)
assert constants_spec is not None
assert constants_spec.loader is not None
constants_module = importlib.util.module_from_spec(constants_spec)
constants_spec.loader.exec_module(constants_module)
MINTING_AGENT_TYPE = constants_module.MINTING_AGENT_TYPE


def _write_parent_transcript(transcript_file: pathlib.Path, agent_id: str, agent_type: str) -> None:
    spawn_record = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Task",
                    "input": {"subagent_type": agent_type, "description": "Verify"},
                    "agentId": agent_id,
                    "agentType": agent_type,
                    "content": [{"type": "text", "text": "verification complete"}],
                }
            ]
        },
    }
    transcript_file.write_text(json.dumps(spawn_record) + "\n", encoding="utf-8")


def test_resolves_subagent_type_from_parent_transcript(tmp_path: pathlib.Path) -> None:
    transcript_file = tmp_path / "parent.jsonl"
    _write_parent_transcript(transcript_file, "agent-7", MINTING_AGENT_TYPE)
    payload = {"agent_id": "agent-7", "transcript_path": str(transcript_file)}
    assert resolved_subagent_type(payload) == MINTING_AGENT_TYPE


def test_resolves_none_when_agent_id_absent_from_transcript(
    tmp_path: pathlib.Path,
) -> None:
    transcript_file = tmp_path / "parent.jsonl"
    _write_parent_transcript(transcript_file, "agent-7", MINTING_AGENT_TYPE)
    payload = {"agent_id": "different-agent", "transcript_path": str(transcript_file)}
    assert resolved_subagent_type(payload) is None


def test_resolves_type_when_record_arrives_after_first_read(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript_file = tmp_path / "parent.jsonl"
    transcript_file.write_text("", encoding="utf-8")

    def write_record_on_first_sleep(_seconds: float) -> None:
        if transcript_file.read_text(encoding="utf-8"):
            return
        _write_parent_transcript(transcript_file, "agent-7", MINTING_AGENT_TYPE)

    monkeypatch.setattr(minter_module.time, "sleep", write_record_on_first_sleep)
    payload = {"agent_id": "agent-7", "transcript_path": str(transcript_file)}
    assert resolved_subagent_type(payload) == MINTING_AGENT_TYPE


def test_quoted_agent_type_in_text_block_does_not_resolve(
    tmp_path: pathlib.Path,
) -> None:
    transcript_file = tmp_path / "parent.jsonl"
    forged_entry = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"agentId": "agent-7", "agentType": MINTING_AGENT_TYPE}),
                }
            ]
        },
    }
    transcript_file.write_text(json.dumps(forged_entry) + "\n", encoding="utf-8")
    payload = {"agent_id": "agent-7", "transcript_path": str(transcript_file)}
    assert resolved_subagent_type(payload) is None


def test_non_verifier_agent_type_mints_nothing(tmp_path: pathlib.Path) -> None:
    transcript_file = tmp_path / "parent.jsonl"
    _write_parent_transcript(transcript_file, "agent-7", "general-purpose")
    payload = {
        "agent_id": "agent-7",
        "transcript_path": str(transcript_file),
        "agent_transcript_path": "",
        "cwd": ".",
    }
    assert mint_for_payload(payload) is None


def test_minting_agent_type_passes_the_agent_type_gate(
    tmp_path: pathlib.Path,
) -> None:
    transcript_file = tmp_path / "parent.jsonl"
    _write_parent_transcript(transcript_file, "agent-7", MINTING_AGENT_TYPE)
    payload = {
        "agent_id": "agent-7",
        "transcript_path": str(transcript_file),
        "agent_transcript_path": "",
        "cwd": ".",
    }
    assert mint_for_payload(payload) is None


def _init_repo_with_upstream_and_edit(repo_root: pathlib.Path) -> None:
    subprocess.run(["git", "-C", str(repo_root), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.email", "verifier@test"], check=True
    )
    subprocess.run(["git", "-C", str(repo_root), "config", "user.name", "verifier"], check=True)
    (repo_root / "module.py").write_text("answer = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-qm", "init"], check=True)
    subprocess.run(["git", "-C", str(repo_root), "branch", "-f", "origin/main", "HEAD"], check=True)
    (repo_root / "module.py").write_text("answer = 2\n", encoding="utf-8")


def test_clean_verifier_verdict_mints_a_verdict_file(tmp_path: pathlib.Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo_with_upstream_and_edit(repo_root)
    transcript_file = tmp_path / "parent.jsonl"
    _write_parent_transcript(transcript_file, "agent-7", MINTING_AGENT_TYPE)
    agent_transcript = tmp_path / "agent.jsonl"
    agent_transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": 'ok\n```verdict\n{"all_pass": true, "findings": []}\n```\n',
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    payload = {
        "agent_id": "agent-7",
        "transcript_path": str(transcript_file),
        "agent_transcript_path": str(agent_transcript),
        "cwd": str(repo_root),
    }
    verdict_path = mint_for_payload(payload)
    try:
        assert verdict_path is not None
        verdict_record = json.loads(verdict_path.read_text(encoding="utf-8"))
        assert verdict_record["all_pass"] is True
    finally:
        if verdict_path is not None and verdict_path.exists():
            verdict_path.unlink()


def _deny_rules() -> list[str]:
    settings_record = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    return settings_record["permissions"]["deny"]


def test_settings_deny_verdict_directory_write() -> None:
    assert "Write($HOME/.claude/verification/**)" in _deny_rules()


def test_settings_deny_verdict_directory_edit() -> None:
    assert "Edit($HOME/.claude/verification/**)" in _deny_rules()
