"""Entry-point tests proving the duplicate-body check guards hook-infrastructure files.

The cross-file duplicate-body check exists to catch a helper copied across sibling
modules in the ``blocking/`` hook directory itself — the exact directory the rest of
the code-rules suite exempts. These tests drive the real entry points (the ``main()``
stdin path and the pre-check CLI) with a hook-infrastructure target so the deny fires
on the same path a live Write would take, rather than calling the check function
directly.

Each test builds a temporary tree whose tail mirrors a production hook directory
(``packages/claude-dev-env/hooks/blocking``) so ``is_hook_infrastructure`` matches the
target path the same way it would for the real directory.
"""

from __future__ import annotations

import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from types import SimpleNamespace

import pytest

_HOOK_DIRECTORY = pathlib.Path(__file__).resolve().parent
_HOOKS_PARENT = _HOOK_DIRECTORY.parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))
if str(_HOOKS_PARENT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_PARENT))

from code_rules_enforcer import main  # noqa: E402

code_rules_enforcer = SimpleNamespace(main=main, sys=sys)

_ENFORCER_SCRIPT_PATH = _HOOK_DIRECTORY / "code_rules_enforcer.py"

SHARED_HELPER_SOURCE = (
    "import re\n"
    "\n"
    "def strip_code_and_quotes(text: str) -> str:\n"
    "    without_fences = re.sub(r'```.*?```', '', text, flags=re.DOTALL)\n"
    "    without_inline = re.sub(r'`[^`]*`', '', without_fences)\n"
    "    without_quotes = re.sub(r'(?m)^>.*$', '', without_inline)\n"
    "    return without_quotes.strip()\n"
)

_HOOK_INFRASTRUCTURE_TAIL = pathlib.Path("packages") / "claude-dev-env" / "hooks" / "blocking"


@pytest.fixture
def hook_blocking_dir() -> Iterator[pathlib.Path]:
    base_directory = pathlib.Path(tempfile.mkdtemp())
    blocking_directory = base_directory / _HOOK_INFRASTRUCTURE_TAIL
    blocking_directory.mkdir(parents=True)
    try:
        yield blocking_directory
    finally:
        shutil.rmtree(base_directory, ignore_errors=False)


def _run_main_with_write_payload(
    file_path: str,
    content: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    """Drive ``main()`` through its stdin entry point for a Write and return stdout.

    Args:
        file_path: The on-disk path the Write targets.
        content: The whole-file body the Write would create.
        monkeypatch: The fixture used to redirect ``sys.stdin``.
        capsys: The fixture used to capture the deny payload on stdout.

    Returns:
        The captured stdout, which holds the deny payload when violations fire.
    """
    write_payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
        }
    )
    monkeypatch.setattr(code_rules_enforcer.sys, "stdin", io.StringIO(write_payload))
    try:
        code_rules_enforcer.main([])
    except SystemExit:
        pass
    return capsys.readouterr().out


def test_write_of_copied_helper_into_hook_directory_denies(
    hook_blocking_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A Write that copies a sibling helper into a second hook file is denied.

    The target lives under a hook-infrastructure path the rest of the code-rules
    suite exempts, so this proves the duplicate-body check still guards the exact
    directory its module docstring names as the primary target."""
    (hook_blocking_dir / "existing_blocker.py").write_text(SHARED_HELPER_SOURCE, encoding="utf-8")
    new_file = hook_blocking_dir / "new_blocker.py"
    stdout = _run_main_with_write_payload(str(new_file), SHARED_HELPER_SOURCE, monkeypatch, capsys)
    assert stdout != "", (
        "A copied helper written into a second hook-infrastructure file must "
        "produce a deny payload, got empty stdout"
    )
    deny_payload = json.loads(stdout)
    decision = deny_payload["hookSpecificOutput"]["permissionDecision"]
    reason = deny_payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert decision == "deny", f"expected deny, got: {decision!r}"
    assert "strip_code_and_quotes" in reason, (
        f"the deny reason must name the duplicated helper, got: {reason!r}"
    )


def test_write_of_unique_helper_into_hook_directory_allows(
    hook_blocking_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A Write of a hook file with no sibling duplicate produces no deny payload.

    Routing hook ``.py`` files to the duplicate-body check must not block a hook
    file that introduces a genuinely new helper; only a copied body denies."""
    (hook_blocking_dir / "existing_blocker.py").write_text(SHARED_HELPER_SOURCE, encoding="utf-8")
    unique_helper_source = (
        "def normalize_indices(left: int, right: int) -> int:\n"
        "    combined = left + right\n"
        "    widened = combined * 5\n"
        "    return widened\n"
    )
    new_file = hook_blocking_dir / "unique_blocker.py"
    stdout = _run_main_with_write_payload(str(new_file), unique_helper_source, monkeypatch, capsys)
    assert stdout == "", f"a unique hook helper must not be denied, got stdout: {stdout!r}"


def test_precheck_of_copied_helper_at_hook_target_exits_nonzero(
    hook_blocking_dir: pathlib.Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """The pre-check CLI flags a copied helper judged at a hook-infrastructure target.

    Driving the real ``--check`` argv path proves the gate's pre-check mode also
    routes a hook ``.py`` target through the duplicate-body check rather than
    exiting clean on the blanket hook-infrastructure exemption."""
    (hook_blocking_dir / "existing_blocker.py").write_text(SHARED_HELPER_SOURCE, encoding="utf-8")
    staging_directory = tmp_path_factory.mktemp("staging")
    candidate_file = staging_directory / "candidate.py"
    candidate_file.write_text(SHARED_HELPER_SOURCE, encoding="utf-8")
    target_path = str(hook_blocking_dir / "new_blocker.py")
    completed = subprocess.run(
        [
            sys.executable,
            str(_ENFORCER_SCRIPT_PATH),
            "--check",
            str(candidate_file),
            "--as",
            target_path,
        ],
        input="",
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1, (
        "a copied helper at a hook target must exit nonzero, got: "
        f"{completed.returncode}, stdout: {completed.stdout!r}, "
        f"stderr: {completed.stderr!r}"
    )
    assert "strip_code_and_quotes" in completed.stdout, (
        f"the pre-check must name the duplicated helper, got: {completed.stdout!r}"
    )
