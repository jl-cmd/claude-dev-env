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

import pre_commit


def make_gate_script_returning(exit_code: int, target_path: Path) -> Path:
    target_path.write_text(
        f"import sys\nsys.exit({exit_code})\n",
        encoding="utf-8",
    )
    return target_path


@pytest.fixture()
def fake_gate_script_blocking(tmp_path: Path) -> Path:
    return make_gate_script_returning(1, tmp_path / "fake_gate_blocking.py")


@pytest.fixture()
def fake_gate_script_passing(tmp_path: Path) -> Path:
    return make_gate_script_returning(0, tmp_path / "fake_gate_passing.py")


def test_main_exits_zero_when_gate_script_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CODE_RULES_GATE_PATH",
        str(tmp_path / "does_not_exist.py"),
    )

    exit_code = pre_commit.main()

    assert exit_code == 0


def test_main_propagates_blocking_exit_code_from_gate(
    fake_gate_script_blocking: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(fake_gate_script_blocking))

    exit_code = pre_commit.main()

    assert exit_code == 1


def test_main_propagates_passing_exit_code_from_gate(
    fake_gate_script_passing: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(fake_gate_script_passing))

    exit_code = pre_commit.main()

    assert exit_code == 0


def test_main_invokes_gate_with_staged_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_arguments_path = tmp_path / "recorded_arguments.txt"
    recording_gate_script_path = tmp_path / "recording_gate.py"
    recording_gate_script_path.write_text(
        "import sys, pathlib\n"
        f'pathlib.Path(r"{recorded_arguments_path}").write_text('
        "'\\n'.join(sys.argv[1:]), encoding='utf-8')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(recording_gate_script_path))

    exit_code = pre_commit.main()

    assert exit_code == 0
    assert recorded_arguments_path.exists(), (
        f"recording gate did not write to {recorded_arguments_path}"
    )
    recorded_arguments = recorded_arguments_path.read_text(
        encoding="utf-8"
    ).splitlines()
    assert recorded_arguments == ["--staged"]


def test_main_exits_two_when_invoke_gate_raises_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_gate_path = tmp_path / "gate.py"
    existing_gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(existing_gate_path))

    original_run = __import__("subprocess").run

    def raising_run(*args: object, **kwargs: object) -> object:
        raise OSError("no such file")

    monkeypatch.setattr(__import__("subprocess"), "run", raising_run)

    exit_code = pre_commit.main()

    assert exit_code == 2


def test_main_emits_stderr_warning_when_gate_script_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(
        "CODE_RULES_GATE_PATH",
        str(tmp_path / "does_not_exist.py"),
    )

    exit_code = pre_commit.main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "gate script not found" in captured.err


def test_invoke_gate_returns_infrastructure_failure_when_strict_resolve_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_gate_path = tmp_path / "missing_gate.py"
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(missing_gate_path))
    missing_gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    original_resolve = Path.resolve

    def raising_resolve(self: Path, strict: bool = False) -> Path:
        if strict and self == missing_gate_path.resolve():
            raise FileNotFoundError("not found")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", raising_resolve)

    exit_code = pre_commit.invoke_gate(missing_gate_path)

    assert exit_code == 2


def test_invoke_gate_uses_resolved_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_gate_dir = tmp_path / "real"
    real_gate_dir.mkdir()
    real_gate_path = real_gate_dir / "gate.py"
    recorded_path_file = tmp_path / "recorded_path.txt"
    real_gate_path.write_text(
        "import sys, pathlib\n"
        f'pathlib.Path(r"{recorded_path_file}").write_text(sys.argv[0], encoding="utf-8")\n'
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    symlink_gate_path = tmp_path / "link_gate.py"
    symlink_gate_path.symlink_to(real_gate_path)
    resolved_path = symlink_gate_path.resolve()
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(symlink_gate_path))

    exit_code = pre_commit.main()

    assert exit_code == 0
    executed_path = recorded_path_file.read_text(encoding="utf-8")
    assert executed_path == str(resolved_path)
