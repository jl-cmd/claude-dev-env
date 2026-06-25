"""Tests for the agent-type gate in verifier_verdict_minter.

The minter mints a verdict only for a code-verifier stop event. The
SubagentStop payload names the stopping subagent's own transcript
(``agent_transcript_path``), which sits beside a harness-written
``agent-<id>.meta.json`` sidecar naming the spawning ``agentType``. These
tests build that sidecar and assert the minter gates on the resolved type and
on the shared MINTING_AGENT_TYPE constant, so a rename in config propagates to
the minter without a second edit. A malformed or non-string sidecar resolves
nothing, and an absent sidecar mints nothing even when the transcript carries a
verdict fence — the main session controls the prompt of any Agent-tool subagent
it spawns, so a verdict fence in the transcript proves nothing about the agent
type, and only the harness-written sidecar attests a code-verifier. A further
test holds the shipped settings.json to the minter docstring's anti-forgery
claim: the main session is denied writes to the verdict directory, so only this
hook can mint a passing verdict.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys

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

store_spec = importlib.util.spec_from_file_location(
    "verification_verdict_store",
    _HOOK_DIR / "verification_verdict_store.py",
)
assert store_spec is not None
assert store_spec.loader is not None
store_module = importlib.util.module_from_spec(store_spec)
store_spec.loader.exec_module(store_module)
empty_surface_hash = store_module.empty_surface_hash

constants_spec = importlib.util.spec_from_file_location(
    "verified_commit_constants",
    _HOOK_DIR / "config" / "verified_commit_constants.py",
)
assert constants_spec is not None
assert constants_spec.loader is not None
constants_module = importlib.util.module_from_spec(constants_spec)
constants_spec.loader.exec_module(constants_module)
MINTING_AGENT_TYPE = constants_module.MINTING_AGENT_TYPE


def _write_sidecar(agent_transcript_file: pathlib.Path, agent_type: str) -> None:
    sidecar_file = agent_transcript_file.with_name(f"{agent_transcript_file.stem}.meta.json")
    sidecar_file.write_text(
        json.dumps({"agentType": agent_type, "description": "Verify"}) + "\n",
        encoding="utf-8",
    )


def test_resolves_subagent_type_from_sidecar(tmp_path: pathlib.Path) -> None:
    agent_transcript = tmp_path / "agent-7.jsonl"
    agent_transcript.write_text("", encoding="utf-8")
    _write_sidecar(agent_transcript, MINTING_AGENT_TYPE)
    payload = {"agent_transcript_path": str(agent_transcript)}
    assert resolved_subagent_type(payload) == MINTING_AGENT_TYPE


def test_resolves_none_when_sidecar_absent(tmp_path: pathlib.Path) -> None:
    agent_transcript = tmp_path / "agent-7.jsonl"
    agent_transcript.write_text("", encoding="utf-8")
    payload = {"agent_transcript_path": str(agent_transcript)}
    assert resolved_subagent_type(payload) is None


def test_resolves_none_when_agent_transcript_path_empty() -> None:
    assert resolved_subagent_type({"agent_transcript_path": ""}) is None
    assert resolved_subagent_type({}) is None


def test_resolves_none_when_sidecar_names_no_string_type(tmp_path: pathlib.Path) -> None:
    agent_transcript = tmp_path / "agent-7.jsonl"
    agent_transcript.write_text("", encoding="utf-8")
    sidecar_file = agent_transcript.with_name("agent-7.meta.json")
    sidecar_file.write_text(json.dumps({"agentType": 123}), encoding="utf-8")
    payload = {"agent_transcript_path": str(agent_transcript)}
    assert resolved_subagent_type(payload) is None


def test_unparseable_sidecar_resolves_nothing(tmp_path: pathlib.Path) -> None:
    agent_transcript = tmp_path / "agent-7.jsonl"
    agent_transcript.write_text("", encoding="utf-8")
    sidecar_file = agent_transcript.with_name("agent-7.meta.json")
    sidecar_file.write_text("{not valid json", encoding="utf-8")
    payload = {"agent_transcript_path": str(agent_transcript)}
    assert resolved_subagent_type(payload) is None


def test_invalid_utf8_sidecar_resolves_nothing(tmp_path: pathlib.Path) -> None:
    agent_transcript = tmp_path / "agent-7.jsonl"
    agent_transcript.write_text("", encoding="utf-8")
    sidecar_file = agent_transcript.with_name("agent-7.meta.json")
    sidecar_file.write_bytes(b'{"agentType": "\xff\xfe bad"}')
    payload = {"agent_transcript_path": str(agent_transcript)}
    assert resolved_subagent_type(payload) is None


def test_non_object_json_sidecar_resolves_nothing(tmp_path: pathlib.Path) -> None:
    agent_transcript = tmp_path / "agent-7.jsonl"
    agent_transcript.write_text("", encoding="utf-8")
    sidecar_file = agent_transcript.with_name("agent-7.meta.json")
    sidecar_file.write_text(json.dumps(["agentType", "code-verifier"]), encoding="utf-8")
    payload = {"agent_transcript_path": str(agent_transcript)}
    assert resolved_subagent_type(payload) is None


def test_non_verifier_agent_type_mints_nothing(tmp_path: pathlib.Path) -> None:
    agent_transcript = tmp_path / "agent-7.jsonl"
    agent_transcript.write_text("", encoding="utf-8")
    _write_sidecar(agent_transcript, "general-purpose")
    payload = {"agent_transcript_path": str(agent_transcript)}
    assert mint_for_payload(payload) is None


def test_verifier_type_without_a_verdict_mints_nothing(tmp_path: pathlib.Path) -> None:
    agent_transcript = tmp_path / "agent-7.jsonl"
    agent_transcript.write_text("", encoding="utf-8")
    _write_sidecar(agent_transcript, MINTING_AGENT_TYPE)
    payload = {"agent_transcript_path": str(agent_transcript)}
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
    agent_transcript = tmp_path / "agent-7.jsonl"
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
    _write_sidecar(agent_transcript, MINTING_AGENT_TYPE)
    payload = {
        "agent_transcript_path": str(agent_transcript),
        "cwd": str(repo_root),
        "agent_id": "a02b9583eedc74093",
    }
    verdict_path = mint_for_payload(payload)
    try:
        assert verdict_path is not None
        verdict_record = json.loads(verdict_path.read_text(encoding="utf-8"))
        assert verdict_record["all_pass"] is True
        assert verdict_record["minted_from_agent_id"] == "a02b9583eedc74093"
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


def test_minter_refuses_when_attested_hash_equals_empty_surface_hash(
    tmp_path: pathlib.Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo_with_upstream_and_edit(repo_root)
    attested_empty = empty_surface_hash()
    verdict_fence = json.dumps(
        {"all_pass": True, "findings": [], "manifest_sha256": attested_empty}
    )
    agent_transcript = tmp_path / "agent-7.jsonl"
    agent_transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"ok\n```verdict\n{verdict_fence}\n```\n",
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_sidecar(agent_transcript, MINTING_AGENT_TYPE)
    payload = {
        "agent_transcript_path": str(agent_transcript),
        "cwd": str(repo_root),
        "agent_id": "empty-surface-1",
    }
    assert mint_for_payload(payload) is None


def test_minter_refuses_when_recomputed_surface_is_empty(
    tmp_path: pathlib.Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "-C", str(repo_root), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.email", "verifier@test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.name", "verifier"],
        check=True,
    )
    (repo_root / "module.py").write_text("answer = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-qm", "init"], check=True
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "branch", "-f", "origin/main", "HEAD"],
        check=True,
    )
    agent_transcript = tmp_path / "agent-7.jsonl"
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
    _write_sidecar(agent_transcript, MINTING_AGENT_TYPE)
    payload = {
        "agent_transcript_path": str(agent_transcript),
        "cwd": str(repo_root),
        "agent_id": "empty-recompute-1",
    }
    assert mint_for_payload(payload) is None


def test_resolves_none_when_sidecar_absent_even_with_verdict_fence(
    tmp_path: pathlib.Path,
) -> None:
    agent_transcript = tmp_path / "agent-7.jsonl"
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
    payload = {"agent_transcript_path": str(agent_transcript)}
    assert resolved_subagent_type(payload) is None


def test_does_not_mint_when_sidecar_absent_but_transcript_has_verdict(
    tmp_path: pathlib.Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo_with_upstream_and_edit(repo_root)
    agent_transcript = tmp_path / "agent-7.jsonl"
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
        "agent_transcript_path": str(agent_transcript),
        "cwd": str(repo_root),
        "agent_id": "no-sidecar-1",
    }
    assert mint_for_payload(payload) is None


def test_attested_manifest_hash_binds_over_cwd_surface(tmp_path: pathlib.Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo_with_upstream_and_edit(repo_root)
    attested_hash = "c" * 64
    agent_transcript = tmp_path / "agent-7.jsonl"
    verdict_fence = json.dumps(
        {"all_pass": True, "findings": [], "manifest_sha256": attested_hash}
    )
    agent_transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"ok\n```verdict\n{verdict_fence}\n```\n",
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_sidecar(agent_transcript, MINTING_AGENT_TYPE)
    payload = {
        "agent_transcript_path": str(agent_transcript),
        "cwd": str(repo_root),
        "agent_id": "attest-1",
    }
    verdict_path = mint_for_payload(payload)
    try:
        assert verdict_path is not None
        verdict_record = json.loads(verdict_path.read_text(encoding="utf-8"))
        assert verdict_record["manifest_sha256"] == attested_hash
    finally:
        if verdict_path is not None and verdict_path.exists():
            verdict_path.unlink()
