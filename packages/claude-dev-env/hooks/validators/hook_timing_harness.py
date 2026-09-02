"""Measure real wall-clock time for the hooks.json-registered Write/Edit hooks.

Each timed command is the literal ``hooks.json`` command string with
``${CLAUDE_PLUGIN_ROOT}`` resolved to the real package root, run as its own
subprocess against a real repository file, timed over a configurable run
count, and reported as p50 and p95 milliseconds.

::

    $ python3 hook_timing_harness.py --runs 7
    run_all_validators         p50=1948.3ms  p95=3020.1ms
    pre_tool_use_dispatcher    p50=180.2ms   p95=230.4ms
    post_tool_use_dispatcher   p50=80.1ms    p95=1200.5ms
    session_file_edit_tracker  p50=31.0ms    p95=34.2ms

A target under the OS temp root would return before any validator ran, so this
harness refuses one. It always runs the whole command line ``hooks.json``
registers, never a single hosted check module standing in for it, so neither
shortcut can distort the numbers.

The timed payload carries no ``session_id``, so ``session_file_edit_tracker``
writes its edit record to the default-session file rather than to a
caller-specific one.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType
from typing import TextIO


def _load_module_from_path(module_name: str, module_path: Path) -> ModuleType:
    """Load and execute the module found at module_path, under module_name.

    Loads by absolute path rather than a package-qualified import, so this
    harness resolves its own constants module the same way whether it runs
    standalone (``python3 hook_timing_harness.py``) or loaded by a test —
    neither invocation shape needs ``hooks/validators`` on ``sys.path``.
    """
    specification = importlib.util.spec_from_file_location(module_name, module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


_harness_constants = _load_module_from_path(
    "hook_timing_harness_constants",
    Path(__file__).resolve().parent / "config" / "hook_timing_harness_constants.py",
)


def _hook_label_for_command(command: str) -> str:
    """Return the short name a wall-time report row uses for one hook command.

    ::

        'python3 .../pre_tool_use_dispatcher.py'      -> 'pre_tool_use_dispatcher'
        'python3 -c "... run_all_validators ..." ...' -> 'run_all_validators'
    """
    if _harness_constants.RUN_ALL_VALIDATORS_LABEL in command:
        return _harness_constants.RUN_ALL_VALIDATORS_LABEL
    script_basename_pattern = re.compile(r"([A-Za-z0-9_]+)\.py")
    all_basename_matches = script_basename_pattern.findall(command)
    if not all_basename_matches:
        raise ValueError(f"cannot derive a hook label from command: {command!r}")
    return all_basename_matches[-1]


def _commands_in_matcher_group(all_matcher_group: dict[str, object]) -> list[tuple[str, str]]:
    """Return the (label, command) pairs one hooks.json matcher group registers."""
    if all_matcher_group.get("matcher") not in _harness_constants.ALL_WRITE_EDIT_MATCHER_PATTERNS:
        return []
    all_hosted_hooks = all_matcher_group.get("hooks", [])
    if not isinstance(all_hosted_hooks, list):
        return []
    all_commands: list[tuple[str, str]] = []
    for each_hook in all_hosted_hooks:
        command = each_hook.get("command", "") if isinstance(each_hook, dict) else ""
        all_commands.append((_hook_label_for_command(command), command))
    return all_commands


def write_edit_hook_commands(hooks_json_path: Path) -> list[tuple[str, str]]:
    """Return the (label, command) pairs hooks.json registers for Write/Edit.

    Reads the real ``PreToolUse`` and ``PostToolUse`` sections and keeps only
    the matcher groups that fire on a Write or Edit tool call, so the harness
    times the same roster a live edit exercises rather than every hook in the
    file (session, lifecycle, and Bash-only hooks included).

    Args:
        hooks_json_path: Path to the ``hooks.json`` file to read.

    Returns:
        One ``(label, command)`` pair per Write/Edit-matching hook, in the
        file's own declaration order.
    """
    hooks_document = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    all_commands: list[tuple[str, str]] = []
    for each_event_name in _harness_constants.ALL_TIMED_EVENT_NAMES:
        for each_matcher_group in hooks_document["hooks"].get(each_event_name, []):
            all_commands.extend(_commands_in_matcher_group(each_matcher_group))
    return all_commands


def _is_under_directory(candidate: Path, directory: Path) -> bool:
    """Return whether *candidate* equals *directory* or sits under it."""
    return candidate == directory or directory in candidate.parents


def ensure_real_repository_target(
    target_path: Path, repository_root: Path | None = None
) -> Path:
    """Return *target_path* resolved, after refusing an ephemeral scratch path.

    A target under the OS temp root trips ``is_ephemeral_path`` inside the
    hooks themselves and returns before any validator runs, so a harness that
    measured one would report a hollow number a few dozen milliseconds wide.
    A target inside *repository_root* is always real, even when the checkout
    itself sits under the OS temp root, so that sandbox layout never
    misclassifies every real file inside it as scratch.

    Raises:
        ValueError: When the resolved path sits under the OS temp root and
            outside *repository_root*.
    """
    resolved_target = target_path.resolve()
    if repository_root is not None and _is_under_directory(
        resolved_target, repository_root.resolve()
    ):
        return resolved_target
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if _is_under_directory(resolved_target, temporary_root):
        raise ValueError(
            f"refusing an ephemeral timing target under {temporary_root}: {resolved_target}"
        )
    return resolved_target


def _write_tool_payload(target_path: Path) -> str:
    """Build a Write-tool PreToolUse/PostToolUse payload naming *target_path*."""
    return json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target_path),
                "content": target_path.read_text(encoding="utf-8"),
            },
        }
    )


def run_hosted_command_once_milliseconds(
    command_template: str, package_root: Path, payload_text: str
) -> float:
    """Run one registered hooks.json command once and return its wall time.

    Args:
        command_template: The ``hooks.json`` command string, ``${CLAUDE_PLUGIN_ROOT}``
            still unresolved.
        package_root: The real package root ``${CLAUDE_PLUGIN_ROOT}`` resolves to.
        payload_text: The JSON payload piped to the command's stdin.

    Returns:
        The wall-clock time the subprocess took, in milliseconds.
    """
    resolved_command = command_template.replace(
        _harness_constants.CLAUDE_PLUGIN_ROOT_PLACEHOLDER, str(package_root)
    )
    started_at = time.perf_counter()
    subprocess.run(
        resolved_command,
        shell=True,
        input=payload_text,
        capture_output=True,
        text=True,
        timeout=_harness_constants.SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )
    finished_at = time.perf_counter()
    return (finished_at - started_at) * 1000.0


def percentile(
    all_sorted_wall_times_milliseconds: list[float], fraction: float
) -> float:
    """Return the nearest-rank percentile of an already-sorted sample.

    ::

        percentile([10, 20, 30, 40, 50, 60, 70], 0.95) -> 70  (rank 7 of 7)
        percentile([10, 20, 30, 40, 50, 60, 70], 0.50) -> 40  (rank 4 of 7)

    Args:
        all_sorted_wall_times_milliseconds: Ascending wall-time samples.
        fraction: The percentile as a fraction between 0 and 1.

    Returns:
        The nearest-rank percentile value.

    Raises:
        ValueError: When the sample is empty.
    """
    if not all_sorted_wall_times_milliseconds:
        raise ValueError("cannot compute a percentile of an empty sample")
    sample_size = len(all_sorted_wall_times_milliseconds)
    rank_index = math.ceil(fraction * sample_size) - 1
    return all_sorted_wall_times_milliseconds[max(0, min(rank_index, sample_size - 1))]


def measure_hosted_command_wall_times(
    hooks_json_path: Path,
    package_root: Path,
    target_path: Path,
    run_count: int,
    *,
    repository_root: Path | None = None,
) -> dict[str, list[float]]:
    """Time every Write/Edit hooks.json command over *run_count* runs each.

    ``repository_root`` is the root ``ensure_real_repository_target`` judges
    ephemerality against; it defaults to ``package_root``.
    """
    real_target = ensure_real_repository_target(
        target_path, repository_root if repository_root is not None else package_root
    )
    payload_text = _write_tool_payload(real_target)
    all_wall_times_by_label: dict[str, list[float]] = {}
    for each_label, each_command_template in write_edit_hook_commands(hooks_json_path):
        all_wall_times_by_label[each_label] = [
            run_hosted_command_once_milliseconds(each_command_template, package_root, payload_text)
            for _ in range(run_count)
        ]
    return all_wall_times_by_label


def _report_line(label: str, all_wall_times_milliseconds: list[float]) -> str:
    sorted_wall_times_milliseconds = sorted(all_wall_times_milliseconds)
    p50 = percentile(sorted_wall_times_milliseconds, _harness_constants.P50_FRACTION)
    p95 = percentile(sorted_wall_times_milliseconds, _harness_constants.P95_FRACTION)
    return f"{label:<26} p50={p50:.1f}ms  p95={p95:.1f}ms"


def main(
    all_arguments: list[str],
    report_stream: TextIO = sys.stdout,
    repository_root: Path | None = None,
) -> int:
    """Run the harness CLI; report_stream and repository_root are injectable seams."""
    package_root = Path(__file__).resolve().parents[
        _harness_constants.PARENT_LEVELS_TO_PACKAGE_ROOT
    ]
    hooks_json_path = Path(__file__).resolve().parent.parent / "hooks.json"
    default_target_path = package_root / _harness_constants.DEFAULT_TARGET_RELATIVE_PATH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=_harness_constants.DEFAULT_RUN_COUNT)
    parser.add_argument("--target", type=Path, default=default_target_path)
    arguments = parser.parse_args(all_arguments)
    effective_repository_root = repository_root if repository_root is not None else package_root
    all_wall_times_by_label = measure_hosted_command_wall_times(
        hooks_json_path, package_root, arguments.target, arguments.runs,
        repository_root=effective_repository_root,
    )
    for each_label, each_wall_times in all_wall_times_by_label.items():
        report_stream.write(_report_line(each_label, each_wall_times) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
