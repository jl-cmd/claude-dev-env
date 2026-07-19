"""Behavioral tests for the code-review stamp-directory write blocker.

The blocker denies shell and file-tool access to
``~/.claude/code-review-stamps/`` and shell references to the stamp store
module or its mint call, while the sanctioned invoker command and unrelated
paths pass.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_HOOK_DIR = Path(__file__).resolve().parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

STAMP_STORE_IMPORT_FORGE = (
    'python -c "from code_review_stamp_store import record_clean_stamp; '
    "record_clean_stamp(root, live_hash, 'low')\""
)
MINT_CALL_FORGE = "python -c \"record_clean_stamp(root, live_hash, 'xhigh')\""
PYTEST_RUN = "python -m pytest test_code_review_stamp_store.py"
SANCTIONED_INVOKER = "python invoke_code_review.py --record-stamp --cwd . --session-model opus low"
ABSOLUTE_STAMP_ACCESS = "cat ~/.claude/code-review-stamps/abc1234567890abc.json"
DECOY_ECHO_THEN_FORGE = (
    'echo "invoke_code_review.py --record-stamp" >/dev/null; '
    "echo x > ~/.claude/code-review-stamps/abc1234567890123.json"
)
DECOY_INVOKER_THEN_FORGE = (
    "python invoke_code_review.py --record-stamp --cwd . low ; "
    "echo pwned > ~/.claude/code-review-stamps/evil.json"
)


def _load_module(module_name: str) -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        module_name, _HOOK_DIR / f"{module_name}.py"
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


blocker_module = _load_module("code_review_stamp_directory_write_blocker")


@pytest.fixture(autouse=True)
def enable_code_review_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Behavior tests exercise the write-blocker with enforcement on."""
    monkeypatch.setattr(blocker_module, "CODE_REVIEW_ENFORCEMENT_ENABLED", True)


def _isolate_home(monkeypatch: pytest.MonkeyPatch, fake_home: Path) -> None:
    home_text = str(fake_home)
    monkeypatch.setenv("HOME", home_text)
    monkeypatch.setenv("USERPROFILE", home_text)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)


def test_absolute_stamp_path_is_blocked() -> None:
    assert blocker_module.references_stamp_directory(ABSOLUTE_STAMP_ACCESS)


def test_store_module_import_forge_is_blocked() -> None:
    assert blocker_module.references_stamp_directory(STAMP_STORE_IMPORT_FORGE)


def test_mint_call_forge_is_blocked() -> None:
    assert blocker_module.references_stamp_directory(MINT_CALL_FORGE)


def test_pytest_run_naming_store_test_is_not_blocked() -> None:
    assert not blocker_module.references_stamp_directory(PYTEST_RUN)


def test_sanctioned_invoker_command_is_not_blocked() -> None:
    assert not blocker_module.references_stamp_directory(SANCTIONED_INVOKER)


def test_decoy_echo_of_invoker_then_stamp_forge_is_blocked() -> None:
    assert blocker_module.references_stamp_directory(DECOY_ECHO_THEN_FORGE)


def test_decoy_invoker_run_then_stamp_forge_is_blocked() -> None:
    assert blocker_module.references_stamp_directory(DECOY_INVOKER_THEN_FORGE)


def test_write_tool_to_stamp_directory_is_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    stamp_path = fake_home / ".claude" / "code-review-stamps" / "abc.json"
    assert blocker_module.path_targets_stamp_directory(str(stamp_path))


def test_write_tool_elsewhere_is_allowed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    other_path = tmp_path / "src" / "module.py"
    assert not blocker_module.path_targets_stamp_directory(str(other_path))


def test_write_payload_to_stamp_directory_denies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    stamp_path = fake_home / ".claude" / "code-review-stamps" / "abc.json"
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(stamp_path), "content": "{}"},
    }
    deny_decision = blocker_module.decision_for_payload(payload)
    assert deny_decision is not None
    assert deny_decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_bash_forge_payload_denies() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": STAMP_STORE_IMPORT_FORGE},
    }
    deny_decision = blocker_module.decision_for_payload(payload)
    assert deny_decision is not None
    assert deny_decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_sanctioned_invoker_payload_is_not_denied() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": SANCTIONED_INVOKER},
    }
    assert blocker_module.decision_for_payload(payload) is None


def test_main_emits_deny_for_bash_forge(monkeypatch: pytest.MonkeyPatch) -> None:
    payload_text = json.dumps({"tool_name": "Bash", "tool_input": {"command": MINT_CALL_FORGE}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload_text))
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    blocker_module.main()
    assert "STAMP_DIRECTORY_GUARD" in captured_stdout.getvalue()


STAMP_OBFUSCATION_PATH = "/.claude/code-review-stamps/a.json"
BENIGN_OBFUSCATION_PATH = "/tmp/x"
SPLIT_CD_FORGE = "cd ~/.claude && cd code-review-stamps && echo x > f.json"


def _hex_forge(path_text: str) -> str:
    return f"python -c \"open(bytes.fromhex('{path_text.encode().hex()}'),'w').write('x')\""


def _chr_chain_forge(path_text: str) -> str:
    chr_chain = "+".join(f"chr({ord(each_character)})" for each_character in path_text)
    return f"python -c \"open({chr_chain},'w').write('x')\""


def test_split_directory_change_into_stamp_is_blocked() -> None:
    assert blocker_module.references_stamp_directory(SPLIT_CD_FORGE)


def test_hex_obfuscated_stamp_path_is_blocked() -> None:
    assert blocker_module.references_stamp_directory(_hex_forge(STAMP_OBFUSCATION_PATH))


def test_chr_chain_obfuscated_stamp_path_is_blocked() -> None:
    assert blocker_module.references_stamp_directory(_chr_chain_forge(STAMP_OBFUSCATION_PATH))


def test_benign_decode_to_other_path_is_not_blocked() -> None:
    assert not blocker_module.references_stamp_directory(_hex_forge(BENIGN_OBFUSCATION_PATH))


def test_enforcement_off_allows_stamp_directory_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(blocker_module, "CODE_REVIEW_ENFORCEMENT_ENABLED", False)
    decision = blocker_module.decision_for_payload(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf ~/.claude/code-review-stamps"},
        }
    )
    assert decision is None

