from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
_git_hooks_directory_string = str(SCRIPT_DIRECTORY)
while _git_hooks_directory_string in sys.path:
    sys.path.remove(_git_hooks_directory_string)
sys.path.insert(0, _git_hooks_directory_string)
for each_module_name in list(sys.modules):
    if each_module_name == "config" or each_module_name.startswith("config."):
        del sys.modules[each_module_name]
importlib.invalidate_caches()

import gate_utils


def test_resolve_gate_script_path_uses_override_env_var_when_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_path = tmp_path / "override_gate.py"
    override_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(override_path))

    resolved_path, exact_allowed = gate_utils.resolve_gate_script_path()

    assert resolved_path == override_path
    assert exact_allowed == override_path


def test_resolve_gate_script_path_defaults_to_claude_home_when_env_var_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODE_RULES_GATE_PATH", raising=False)
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path))

    resolved_path, exact_allowed = gate_utils.resolve_gate_script_path()

    expected_path = (
        tmp_path / "skills" / "bugteam" / "scripts" / "bugteam_code_rules_gate.py"
    )
    assert resolved_path == expected_path
    assert exact_allowed is None


def test_resolve_gate_script_path_falls_back_to_home_dot_claude_when_no_env_vars(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODE_RULES_GATE_PATH", raising=False)
    monkeypatch.delenv("CLAUDE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    resolved_path, exact_allowed = gate_utils.resolve_gate_script_path()

    expected_path = (
        tmp_path
        / ".claude"
        / "skills"
        / "bugteam"
        / "scripts"
        / "bugteam_code_rules_gate.py"
    )
    assert resolved_path == expected_path
    assert exact_allowed is None


def test_resolve_gate_script_path_resolves_relative_override_to_absolute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODE_RULES_GATE_PATH", "relative/gate.py")

    resolved_path, _ = gate_utils.resolve_gate_script_path()

    assert resolved_path.is_absolute()


def test_is_safe_regular_file_rejects_sibling_of_override_path(
    tmp_path: Path,
) -> None:
    override_gate = tmp_path / "gate.py"
    override_gate.write_text("", encoding="utf-8")
    sibling_script = tmp_path / "attacker_script.py"
    sibling_script.write_text("", encoding="utf-8")

    is_safe = gate_utils.is_safe_regular_file(sibling_script, override_gate.resolve())

    assert not is_safe


def test_is_safe_regular_file_accepts_exact_override_path(
    tmp_path: Path,
) -> None:
    override_gate = tmp_path / "gate.py"
    override_gate.write_text("", encoding="utf-8")

    is_safe = gate_utils.is_safe_regular_file(override_gate, override_gate.resolve())

    assert is_safe


def test_is_safe_regular_file_rejects_claude_home_override_outside_home_dot_claude(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attacker_home = tmp_path / "attacker_home"
    gate_under_attacker_home = (
        attacker_home / "skills" / "bugteam" / "scripts" / "bugteam_code_rules_gate.py"
    )
    gate_under_attacker_home.parent.mkdir(parents=True)
    gate_under_attacker_home.write_text("", encoding="utf-8")
    real_home = tmp_path / "real_home"
    monkeypatch.setattr(Path, "home", staticmethod(lambda: real_home))

    is_safe = gate_utils.is_safe_regular_file(gate_under_attacker_home, None)

    assert not is_safe


def test_is_safe_regular_file_accepts_gate_inside_home_dot_claude(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home_dir = tmp_path / "real_home"
    gate_path = (
        home_dir / ".claude" / "skills" / "bugteam" / "scripts" / "bugteam_code_rules_gate.py"
    )
    gate_path.parent.mkdir(parents=True)
    gate_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))

    is_safe = gate_utils.is_safe_regular_file(gate_path, None)

    assert is_safe


def test_is_safe_regular_file_rejects_nonexistent_path_under_trusted_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home_dir = tmp_path / "real_home"
    (home_dir / ".claude").mkdir(parents=True)
    missing_gate_path = (
        home_dir / ".claude" / "skills" / "bugteam" / "scripts" / "missing_gate.py"
    )
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))

    is_safe = gate_utils.is_safe_regular_file(missing_gate_path, None)

    assert not is_safe


def test_is_safe_regular_file_resolves_symlink_before_prefix_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home_dir = tmp_path / "home"
    claude_home = home_dir / ".claude"
    claude_home.mkdir(parents=True)
    real_target = tmp_path / "outside_claude" / "evil.py"
    real_target.parent.mkdir(parents=True)
    real_target.write_text("", encoding="utf-8")
    symlink_inside_claude = claude_home / "evil_link.py"
    symlink_inside_claude.symlink_to(real_target)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))

    is_safe = gate_utils.is_safe_regular_file(symlink_inside_claude, None)

    assert not is_safe


def test_is_safe_regular_file_uses_claude_home_env_as_trust_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom_claude_home = tmp_path / "custom_claude"
    gate_path = (
        custom_claude_home / "skills" / "bugteam" / "scripts" / "bugteam_code_rules_gate.py"
    )
    gate_path.parent.mkdir(parents=True)
    gate_path.write_text("", encoding="utf-8")
    monkeypatch.delenv("CODE_RULES_GATE_PATH", raising=False)
    monkeypatch.setenv("CLAUDE_HOME", str(custom_claude_home))

    gate_script_path, exact_allowed = gate_utils.resolve_gate_script_path()

    is_safe = gate_utils.is_safe_regular_file(gate_script_path, exact_allowed)

    assert is_safe


def test_resolve_gate_script_path_snapshot_is_consistent_with_is_safe_regular_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom_claude_home = tmp_path / "custom_claude"
    gate_path = (
        custom_claude_home / "skills" / "bugteam" / "scripts" / "bugteam_code_rules_gate.py"
    )
    gate_path.parent.mkdir(parents=True)
    gate_path.write_text("", encoding="utf-8")
    monkeypatch.delenv("CODE_RULES_GATE_PATH", raising=False)
    monkeypatch.setenv("CLAUDE_HOME", str(custom_claude_home))

    resolved_path, exact_allowed = gate_utils.resolve_gate_script_path()
    is_safe = gate_utils.is_safe_regular_file(resolved_path, exact_allowed)

    assert is_safe


def test_is_safe_regular_file_rejects_path_outside_claude_home_env_trust_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom_claude_home = tmp_path / "custom_claude"
    custom_claude_home.mkdir(parents=True)
    outside_path = tmp_path / "outside" / "gate.py"
    outside_path.parent.mkdir(parents=True)
    outside_path.write_text("", encoding="utf-8")
    monkeypatch.delenv("CODE_RULES_GATE_PATH", raising=False)
    monkeypatch.setenv("CLAUDE_HOME", str(custom_claude_home))

    is_safe = gate_utils.is_safe_regular_file(outside_path, None)

    assert not is_safe
