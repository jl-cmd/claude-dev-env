"""Tests for hook_timing_harness.py."""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import pytest


def _load_module_from_path(module_name: str, module_path: Path) -> ModuleType:
    """Load and execute the module found at module_path, under module_name."""
    specification = importlib.util.spec_from_file_location(module_name, module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


_VALIDATORS_DIRECTORY = Path(__file__).resolve().parent
_PACKAGE_ROOT = _VALIDATORS_DIRECTORY.parents[1]
_HOOKS_JSON_PATH = _VALIDATORS_DIRECTORY.parent / "hooks.json"
_REAL_TARGET_FILE = _PACKAGE_ROOT / "hooks" / "blocking" / "code_rules_shared.py"

if str(_VALIDATORS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_VALIDATORS_DIRECTORY))
hook_timing_harness = _load_module_from_path(
    "hook_timing_harness", _VALIDATORS_DIRECTORY / "hook_timing_harness.py"
)


def test_hook_label_for_command_names_run_all_validators() -> None:
    command = (
        'python3 -c "import sys; from validators.run_all_validators import main; '
        'sys.exit(main())" --pre-tool-use'
    )
    assert hook_timing_harness._hook_label_for_command(command) == "run_all_validators"


def test_hook_label_for_command_names_the_script_basename() -> None:
    command = "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/pre_tool_use_dispatcher.py"
    assert hook_timing_harness._hook_label_for_command(command) == "pre_tool_use_dispatcher"


def test_write_edit_hook_commands_reads_the_real_hooks_json_roster() -> None:
    all_commands = hook_timing_harness.write_edit_hook_commands(_HOOKS_JSON_PATH)
    all_labels = [each_label for each_label, _each_command in all_commands]
    assert all_labels == [
        "pre_tool_use_dispatcher",
        "post_tool_use_dispatcher",
        "session_file_edit_tracker",
    ]


def test_percentile_returns_the_nearest_rank_value() -> None:
    sample = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
    assert hook_timing_harness.percentile(sample, 0.50) == 40.0
    assert hook_timing_harness.percentile(sample, 0.95) == 70.0


def test_percentile_raises_on_an_empty_sample() -> None:
    with pytest.raises(ValueError):
        hook_timing_harness.percentile([], 0.50)


def test_ensure_real_repository_target_refuses_an_os_temp_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    ephemeral_target = Path(tempfile.gettempdir()) / "scratch.py"
    with pytest.raises(ValueError, match="ephemeral"):
        hook_timing_harness.ensure_real_repository_target(ephemeral_target)


def test_ensure_real_repository_target_accepts_a_real_repository_file() -> None:
    resolved = hook_timing_harness.ensure_real_repository_target(
        _REAL_TARGET_FILE, _PACKAGE_ROOT
    )
    assert resolved == _REAL_TARGET_FILE.resolve()


def test_ensure_real_repository_target_accepts_a_repo_file_under_the_os_temp_root(
    tmp_path: Path,
) -> None:
    """A checkout placed under the OS temp root still accepts its own real files.

    Ephemerality is judged relative to the given repository root, not the OS
    temp root alone, so a checkout that itself sits under the OS temp root (a
    common sandbox layout) does not misclassify every real file inside it as
    a throwaway scratch target.
    """
    repository_root = tmp_path / "repo"
    real_file = repository_root / "hooks" / "blocking" / "code_rules_shared.py"
    real_file.parent.mkdir(parents=True)
    real_file.write_text("x = 1\n", encoding="utf-8")

    resolved = hook_timing_harness.ensure_real_repository_target(real_file, repository_root)

    assert resolved == real_file.resolve()


def test_ensure_real_repository_target_refuses_a_scratch_path_outside_the_repository_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The refusal is under test, so this pins the temp root it is judged against.

    ``--basetemp`` places ``tmp_path`` wherever the caller asks, so a run that
    points it outside the OS temp root leaves the scratch target real and this
    assertion measures the caller's flags. Naming the root here keeps the
    subject of the test inside the test.
    """
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    scratch_target = tmp_path / "scratch.py"

    with pytest.raises(ValueError, match="ephemeral"):
        hook_timing_harness.ensure_real_repository_target(scratch_target, repository_root)


def test_ensure_real_repository_target_refuses_a_path_under_runner_temp_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GitHub Actions puts pytest basetemp under RUNNER_TEMP, not gettempdir().

    ``gettempdir()`` stays ``/tmp`` on the hosted runner while pytest's own
    ``tmp_path`` lives under ``RUNNER_TEMP`` (``/home/runner/work/_temp``), a
    directory ``gettempdir()`` never reports. A refusal that judges
    ephemerality against ``gettempdir()`` alone misses that target and reads
    the runner's own scratch file as a real repository file.
    """
    fake_os_temporary_root = tmp_path / "os-temp"
    fake_os_temporary_root.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_os_temporary_root))
    runner_temporary_root = tmp_path / "runner-temp"
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temporary_root))
    ephemeral_target = runner_temporary_root / "scratch.py"

    with pytest.raises(ValueError, match="ephemeral"):
        hook_timing_harness.ensure_real_repository_target(ephemeral_target)


def test_run_hosted_command_once_milliseconds_drives_the_real_tracker() -> None:
    """A live subprocess run against a real repository file measures a positive time.

    ::

        session_file_edit_tracker is the fastest hosted command, so this is the
        cheap live end-to-end proof: it drives the actual registered
        ``hooks.json`` command line, not a standalone hosted check module.
    """
    all_commands = hook_timing_harness.write_edit_hook_commands(_HOOKS_JSON_PATH)
    tracker_command = next(
        each_command
        for each_label, each_command in all_commands
        if each_label == "session_file_edit_tracker"
    )
    payload_text = hook_timing_harness._write_tool_payload(_REAL_TARGET_FILE)
    elapsed_milliseconds = hook_timing_harness.run_hosted_command_once_milliseconds(
        tracker_command, _PACKAGE_ROOT, payload_text
    )
    assert 0.0 < elapsed_milliseconds < 5000.0


def test_measure_hosted_command_wall_times_covers_the_real_roster() -> None:
    """A live run against the real hooks.json roster returns all three hooks.

    Runs each registered command once against a real repository file,
    so this is the one place the suite pays its full wall time to prove the roster end to end.
    """
    all_wall_times_by_label = hook_timing_harness.measure_hosted_command_wall_times(
        _HOOKS_JSON_PATH, _PACKAGE_ROOT, _REAL_TARGET_FILE, 1
    )
    assert set(all_wall_times_by_label) == {
        "pre_tool_use_dispatcher",
        "post_tool_use_dispatcher",
        "session_file_edit_tracker",
    }
    assert all(
        each_time > 0.0
        for each_times in all_wall_times_by_label.values()
        for each_time in each_times
    )


def test_measure_hosted_command_wall_times_honors_a_repository_root_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The wrapper forwards repository_root to the delegate, not just accepts it.

    ``ensure_real_repository_target`` already accepts ``repository_root``, but
    until the wrapper's own signature exposes and forwards it, no caller of
    ``measure_hosted_command_wall_times`` can reach that parameter — the exact
    gap the wrapper-plumb-through check caught.
    """
    monkeypatch.setattr(hook_timing_harness, "write_edit_hook_commands", lambda path: [])
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    repository_root = tmp_path / "repo"
    real_file = repository_root / "hooks" / "blocking" / "code_rules_shared.py"
    real_file.parent.mkdir(parents=True)
    real_file.write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="ephemeral"):
        hook_timing_harness.measure_hosted_command_wall_times(
            _HOOKS_JSON_PATH, _PACKAGE_ROOT, real_file, 1
        )

    all_wall_times_by_label = hook_timing_harness.measure_hosted_command_wall_times(
        _HOOKS_JSON_PATH, _PACKAGE_ROOT, real_file, 1, repository_root=repository_root
    )
    assert all_wall_times_by_label == {}


def test_main_writes_one_report_line_per_label(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_wall_times_by_label = {"pre_tool_use_dispatcher": [100.0, 200.0]}
    monkeypatch.setattr(
        hook_timing_harness,
        "measure_hosted_command_wall_times",
        lambda *args, **kwargs: fake_wall_times_by_label,
    )
    report_stream = io.StringIO()
    exit_code = hook_timing_harness.main(["--runs", "2"], report_stream=report_stream)
    report_text = report_stream.getvalue()
    assert exit_code == 0
    assert "pre_tool_use_dispatcher" in report_text
    assert "p50=" in report_text and "p95=" in report_text


def test_main_forwards_its_own_repository_root_to_the_wrapper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """main() forwards a caller-supplied repository_root, not just accepts it.

    Mirrors the wrapper-level gap: adding ``repository_root`` to
    ``measure_hosted_command_wall_times`` alone leaves ``main`` as a second
    wrapper dropping the same optional keyword.
    """
    all_captured_kwargs: dict[str, object] = {}

    def _spy_measure_hosted_command_wall_times(*args: object, **kwargs: object) -> dict[str, list[float]]:
        all_captured_kwargs.update(kwargs)
        return {}

    monkeypatch.setattr(
        hook_timing_harness,
        "measure_hosted_command_wall_times",
        _spy_measure_hosted_command_wall_times,
    )
    override_root = tmp_path / "repo"
    exit_code = hook_timing_harness.main([], repository_root=override_root)
    assert exit_code == 0
    assert all_captured_kwargs.get("repository_root") == override_root
