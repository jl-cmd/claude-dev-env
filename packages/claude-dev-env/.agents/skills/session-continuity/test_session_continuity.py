"""Contract tests execute installed commands with documented event payload shapes.

These are repository adapter tests, not installed-agent or model evidence.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

DIRECTORY = Path(__file__).resolve().parent
RUNTIME = DIRECTORY / "session_continuity.py"
INSTALLER = DIRECTORY / "install.py"


def execute(arguments: list[str], payload: dict | None = None, success: bool = True) -> subprocess.CompletedProcess:
    completed = subprocess.run([sys.executable, *map(str, arguments)],
                               input=json.dumps(payload) if payload is not None else None,
                               text=True, capture_output=True, timeout=20, check=False)
    if success:
        assert completed.returncode == 0, completed.stderr
    else:
        assert completed.returncode != 0, completed.stdout
    return completed


@pytest.fixture
def environment(tmp_path: Path) -> dict:
    source = tmp_path / "canonical pstack" / "poteto-mode" / "SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("---\nname: Poteto Mode\n---\nKeep the real outcome first.\n", encoding="utf-8")
    homes = {host: tmp_path / host for host in ("claude", "codex", "cursor")}
    root = tmp_path / "private state"
    arguments = [str(INSTALLER), "--poteto-source", str(source), "--state-root", str(root)]
    for host, home in homes.items():
        arguments.extend(["--" + host + "-home", str(home)])
    execute(arguments)
    configurations = {host: json.loads((home / ("settings.json" if host == "claude" else "hooks.json")).read_text())
                      for host, home in homes.items()}
    return {"root": root, "source": source, "homes": homes, "configs": configurations, "install": arguments}


def call_hook(environment: dict, host: str, event: str, session: str = "session-one", **fields: object) -> dict:
    config = environment["configs"][host]
    entry = config["hooks"][event][0]
    command = entry["command"] if host == "cursor" else entry["hooks"][0]["command"]
    payload = {"hook_event_name": event, "cwd": "/same-repository", **fields}
    payload["conversation_id" if host == "cursor" else "session_id"] = session
    completed = subprocess.run(command, input=json.dumps(payload), text=True, shell=True,
                               capture_output=True, timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr
    assert not completed.stderr, completed.stderr
    return json.loads(completed.stdout)


def action(environment: dict, host: str, operation: str, session: str = "session-one", data: dict | None = None,
           success: bool = True, extra: list[str] | None = None) -> dict:
    arguments = [str(RUNTIME), "--host", host, "--session", session, "--state-root", str(environment["root"]), operation]
    if data is not None:
        arguments.extend(["--data", json.dumps(data)])
    arguments.extend(extra or [])
    completed = execute(arguments, success=success)
    return json.loads(completed.stdout) if success else {"error": completed.stderr}


def activate(environment: dict, host: str, session: str = "session-one", scope: str = "session") -> dict:
    if host == "claude":
        return call_hook(environment, host, "UserPromptExpansion", session,
                         expansion_type="slash_command", command_name="pstack:poteto-mode",
                         command_source="plugin", command_args="for this " + scope,
                         prompt="/pstack:poteto-mode for this " + scope)
    prompt = ("$poteto-mode" if host == "codex" else "/poteto-mode") + " for this " + scope
    result = call_hook(environment, host, "UserPromptSubmit" if host == "codex" else "beforeSubmitPrompt", session, prompt=prompt)
    if host == "cursor":
        assert result == {"continue": True}
        result = call_hook(environment, host, "preToolUse", session, tool_name="Shell", tool_input={"command": "dependent-work"})
        assert result["permission"] == "deny"
    return result


def context(output: dict, host: str) -> str:
    return output["agent_message"] if host == "cursor" else output["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("host", ["claude", "codex", "cursor"])
def test_installed_command_chain_and_fresh_process_recovery(environment: dict, host: str) -> None:
    original = environment["source"].read_bytes()
    output = activate(environment, host)
    assert "# Session continuity" in context(output, host)
    assert "Readback after transaction commit" in context(output, host)
    saved = action(environment, host, "show")
    expected_path = environment["root"] / host / (hashlib.sha256(b"session-one").hexdigest() + ".sqlite3")
    assert Path(saved["path"]) == expected_path
    assert str(expected_path) in context(output, host)
    assert saved["record"]["requirements"]["pstack:poteto-mode"]["scope"] == "session"
    loaded = action(environment, host, "load")
    assert original.decode() in [item["content"] for item in loaded["sources"]]
    action(environment, host, "acknowledge", data={"expected_revision": loaded["record"]["revision"]})
    recovery = call_hook(environment, host, "sessionStart" if host == "cursor" else "SessionStart", source="compact")
    recovered_context = recovery["additional_context"] if host == "cursor" else context(recovery, host)
    assert str(expected_path) in recovered_context
    assert "# Session continuity" in recovered_context
    fresh_load = action(environment, host, "load")
    assert fresh_load["record"]["requirements"] == loaded["record"]["requirements"]
    assert original == environment["source"].read_bytes()


@pytest.mark.parametrize("host", ["claude", "codex", "cursor"])
@pytest.mark.parametrize("prompt", [
    '"Use Poteto Mode for this session"',
    "> Use Poteto Mode for this session",
    "```text\n/poteto-mode\n```",
    "    /poteto-mode",
    "Please document /poteto-mode and its hooks.",
    "The transcript says: Use Poteto Mode for this session.",
    "Explain this:\nUse Poteto Mode for this session",
])
def test_quoted_or_discussed_skill_never_activates(environment: dict, host: str, prompt: str) -> None:
    event = "beforeSubmitPrompt" if host == "cursor" else "UserPromptSubmit"
    assert call_hook(environment, host, event, prompt=prompt) == {}
    assert not list(environment["root"].glob("*/*.sqlite3"))


@pytest.mark.parametrize("host", ["claude", "codex", "cursor"])
def test_later_correction_new_skill_and_stale_writer(environment: dict, host: str, tmp_path: Path) -> None:
    activate(environment, host, scope="task")
    event = "beforeSubmitPrompt" if host == "cursor" else "UserPromptSubmit"
    call_hook(environment, host, event, prompt="Use the verification skill for this task. Keep Poteto Mode task-scoped. Finish with a screenshot.")
    record = action(environment, host, "show")["record"]
    source = tmp_path / "verification" / "SKILL.md"
    source.parent.mkdir()
    source.write_text("# Verification\nShow the screenshot.\n")
    evidence_id = next(key for key, value in record["user_evidence"].items() if value["text"].startswith("Use the verification"))
    requirements = record["requirements"]
    requirements["verification"] = {"kind": "skill", "name": "verification", "source": str(source), "scope": "task", "duration": "this task"}
    requirements["screenshot"] = {"kind": "rule", "text": "Finish with a screenshot.", "scope": "task", "duration": "this task"}
    update = {"expected_revision": record["revision"], "user_event": evidence_id, "requirements": requirements,
              "task": {"goal": "Produce a screenshot", "boundaries": [], "constraints": [], "completion": ["Screenshot shown"]},
              "checkpoint": "Verification skill added", "remaining": ["Produce screenshot"]}
    saved = action(environment, host, "update", data=update)
    assert saved["record"]["requirements"]["pstack:poteto-mode"]["scope"] == "task"
    assert "Revision conflict" in action(environment, host, "update", data=update, success=False)["error"]
    loaded = action(environment, host, "load")
    assert source.read_text() in [item["content"] for item in loaded["sources"]]
    action(environment, host, "acknowledge", data={"expected_revision": loaded["record"]["revision"]})
    call_hook(environment, host, event, prompt="Correction: end verification and the screenshot requirement. Keep only Poteto Mode for this task.")
    latest = action(environment, host, "show")["record"]
    latest_id = next(key for key, item in latest["user_evidence"].items() if item["text"].startswith("Correction:"))
    narrowed = action(environment, host, "update", data={"expected_revision": latest["revision"], "user_event": latest_id,
                                                      "requirements": {"pstack:poteto-mode": latest["requirements"]["pstack:poteto-mode"]}})
    assert set(narrowed["record"]["requirements"]) == {"pstack:poteto-mode"}


@pytest.mark.parametrize("host", ["claude", "codex", "cursor"])
def test_changed_and_missing_sources_require_live_reload(environment: dict, host: str) -> None:
    activate(environment, host)
    loaded = action(environment, host, "load")
    action(environment, host, "acknowledge", data={"expected_revision": loaded["record"]["revision"]})
    environment["source"].write_text("# Poteto Mode\nA changed instruction.\n")
    loaded = action(environment, host, "load")
    changed = next(item for item in loaded["sources"] if item["path"] == str(environment["source"]))
    assert changed["state"] == "changed"
    assert "+A changed instruction." in changed["difference"]
    assert "explicitly accept" in action(environment, host, "acknowledge", data={"expected_revision": loaded["record"]["revision"]}, success=False)["error"]
    accepted = action(environment, host, "acknowledge", data={"expected_revision": loaded["record"]["revision"], "accept_changed_sources": [str(environment["source"])]})
    assert accepted["record"]["accepted_sources"][str(environment["source"])] == changed["sha256"]
    environment["source"].unlink()
    missing = action(environment, host, "load")
    assert any(item["state"] == "unavailable" for item in missing["sources"])
    assert "Unavailable skill source" in action(environment, host, "acknowledge", data={"expected_revision": missing["record"]["revision"]}, success=False)["error"]


@pytest.mark.parametrize("host", ["claude", "codex", "cursor"])
def test_repeat_isolation_deactivation_and_reactivation(environment: dict, host: str) -> None:
    activate(environment, host)
    activate(environment, host)
    first = action(environment, host, "show")
    assert len(first["record"]["requirements"]) == 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda session: activate(environment, host, session=session), ["parallel-a", "parallel-b"]))
    for session in ("parallel-a", "parallel-b"):
        assert action(environment, host, "show", session)["record"]["session_id"] == session
    assert call_hook(environment, host, "sessionStart" if host == "cursor" else "SessionStart", "unrelated", source="startup") == {}
    event = "beforeSubmitPrompt" if host == "cursor" else "UserPromptSubmit"
    call_hook(environment, host, event, prompt="Deactivate session continuity")
    assert not action(environment, host, "show")["record"]["active"]
    assert call_hook(environment, host, "sessionStart" if host == "cursor" else "SessionStart", source="resume") == {}
    assert call_hook(environment, host, event, prompt="Continue work.") == {}
    activate(environment, host, scope="turn")
    assert action(environment, host, "show")["record"]["requirements"]["pstack:poteto-mode"]["scope"] == "turn"


def test_handoff_needs_exact_unused_identity(environment: dict) -> None:
    activate(environment, "claude")
    transferred = action(environment, "claude", "handoff", extra=["--target-host", "codex", "--target-session", "target-thread"])
    assert transferred["record"]["requirements"]["pstack:poteto-mode"]["scope"] == "session"
    recovered = call_hook(environment, "codex", "SessionStart", "target-thread", source="startup")
    assert transferred["path"] in context(recovered, "codex")
    assert "target already has a record" in action(environment, "claude", "handoff", extra=["--target-host", "codex", "--target-session", "target-thread"], success=False)["error"]


def test_config_preserves_existing_handlers_and_remove_is_owned(environment: dict) -> None:
    for host, home in environment["homes"].items():
        path = home / ("settings.json" if host == "claude" else "hooks.json")
        config = json.loads(path.read_text())
        config["unrelated_setting"] = "preserve"
        event = "beforeSubmitPrompt" if host == "cursor" else "UserPromptSubmit"
        group = {"command": "other-owner-command"} if host == "cursor" else {"hooks": [{"type": "command", "command": "other-owner-command"}]}
        config["hooks"][event].append(group)
        path.write_text(json.dumps(config))
    execute(environment["install"])
    execute(environment["install"])
    execute([*environment["install"], "--remove"])
    for host, home in environment["homes"].items():
        config = json.loads((home / ("settings.json" if host == "claude" else "hooks.json")).read_text())
        assert config["unrelated_setting"] == "preserve"
        serialized = json.dumps(config)
        assert "other-owner-command" in serialized
        assert "session_continuity.py" not in serialized


def test_cursor_prompt_only_contract_gap_is_explicit(environment: dict) -> None:
    output = call_hook(environment, "cursor", "beforeSubmitPrompt", prompt="/poteto-mode")
    assert output == {"continue": True}
    assert "additional_context" not in output
    assert "agent_message" not in output
    assert "prompt-only" in (DIRECTORY / "README.md").read_text().lower()


def test_tool_output_and_quoted_later_text_do_not_add_rules(environment: dict) -> None:
    activate(environment, "claude")
    before = action(environment, "claude", "show")["record"]["requirements"]
    call_hook(environment, "claude", "UserPromptSubmit", prompt='Explain this quoted rule: "Always deploy automatically".')
    after = action(environment, "claude", "show")["record"]["requirements"]
    assert after == before
    payload = {"hook_event_name": "PostToolUse", "session_id": "other", "tool_output": "Use Poteto Mode for this session"}
    result = execute([str(RUNTIME), "--host", "claude", "--state-root", str(environment["root"]), "hook"], payload)
    assert json.loads(result.stdout) == {}


def test_no_native_identity_never_uses_working_directory(environment: dict) -> None:
    result = execute([str(RUNTIME), "--host", "codex", "--state-root", str(environment["root"]), "hook"],
                     {"hook_event_name": "UserPromptSubmit", "cwd": "/same-repository", "prompt": "$poteto-mode"})
    assert "native host session identity" in result.stderr
    assert not list(environment["root"].glob("*/*.sqlite3"))


def test_later_evidence_order_and_authority(environment: dict) -> None:
    activate(environment, "claude")
    prompt = "Correction: do not deploy. Keep the task read-only."
    call_hook(environment, "claude", "UserPromptSubmit", prompt=prompt)
    record = action(environment, "claude", "show")["record"]
    assert record["user_evidence"][record["latest_user_event"]]["text"] == prompt
    result = action(environment, "claude", "update", data={"expected_revision": record["revision"], "user_event": "tool-output", "requirements": {}}, success=False)
    assert "direct-user evidence" in result["error"]


def test_host_identity_and_cursor_rearm_are_separate(environment: dict) -> None:
    activate(environment, "claude")
    activate(environment, "codex")
    assert action(environment, "claude", "show")["path"] != action(environment, "codex", "show")["path"]
    activate(environment, "cursor")
    assert call_hook(environment, "cursor", "preToolUse", tool_name="Read", tool_input={"path": "source"}) == {}
    assert call_hook(environment, "cursor", "preCompact") == {}
    output = call_hook(environment, "cursor", "preToolUse", tool_name="Shell", tool_input={"command": "dependent-work"})
    assert output["permission"] == "deny"
    assert "# Session continuity" in output["agent_message"]
