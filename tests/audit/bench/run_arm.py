"""Run one benchmark case once in one arm and append a run row to a TSV.

::

    --case fix-flaky-test --arm ablate:rules/git-workflow.md --repetition 1
    ok                  the session finished and every grader ran
    harness_error:leak  the init event named a path under the live home

Every mutation happens under a disposable run directory in the OS temp root.
The installer runs with a substitute home and a substitute global git config,
and writes the arm into ``<work>/.claude`` as a project-level install.

The model session signs in through the live home. It loads project settings
only, skips every MCP server, and keeps no session file.

Usage:
    python tests/audit/bench/run_arm.py --case <id> --arm <id> --repetition 1
        --model <model-id> --repo <path-to-git-repo> --rows <runs.tsv>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO

from arm_isolation import (
    find_live_home_tool_calls,
    find_outside_writes,
    link_arm_home,
    redirect_environment,
    rewrite_live_home_references,
)
from config.run_arm_constants import (
    ABLATE_ARM_PREFIX,
    ABLATE_PATH_SEPARATOR,
    AGENTS_DIRECTORY_NAME,
    ALL_AUTH_PASSTHROUGH_VARIABLES,
    ALL_FIXTURE_CACHE_NAMES,
    ALL_GIT_ADD_ARGUMENTS,
    ALL_GIT_COMMIT_ARGUMENTS,
    ALL_GIT_INIT_ARGUMENTS,
    ALL_INIT_INVENTORY_KEYS,
    ALL_LIVE_HOME_VARIABLES,
    ALL_PROJECT_INSTALL_NAMES,
    ALL_ROW_COLUMNS,
    ALL_RUN_SCRATCH_VARIABLES,
    ALL_SESSION_VARIABLE_PREFIXES,
    ALL_TOKEN_USAGE_KEYS,
    BENCH_DIRECTORY,
    CLAUDE_DIRECTORY_NAME,
    CODEX_DIRECTORY_NAME,
    DEFAULT_ALLOWED_TOOLS,
    DEFAULT_SESSION_TIMEOUT_SECONDS,
    DISABLE_AUTO_MEMORY_VARIABLE,
    GIT_CONFIG_GLOBAL_VARIABLE,
    GIT_CONFIG_NOSYSTEM_VARIABLE,
    GIT_DIRECTORY_NAME,
    HARNESS_DETAIL_CHARACTER_LIMIT,
    INSTALL_PSTACK_VARIABLE,
    INSTALL_TIMEOUT_SECONDS,
    INSTALLER_RELATIVE_PATH,
    JSON_INDENT_SPACES,
    PACKAGE_RELATIVE_ROOT,
    RUN_LABEL_CHARACTER_LIMIT,
    SETUP_FAILURE_SEPARATOR,
    SHIM_LOG_RELATIVE_PATH,
    SHIM_LOG_VARIABLE,
    CODEX_HOME_VARIABLE,
)
from graders import GraderVerdict, GradingContext, run_graders


@dataclass(frozen=True)
class Arm:
    arm_id: str
    kind: str
    base_sha: str
    all_removed_paths: tuple[str, ...]
    removal_patch: str | None


@dataclass(frozen=True)
class RunLayout:
    root: Path
    source: Path
    home: Path
    config: Path
    work: Path
    shim: Path


@dataclass(frozen=True)
class SessionOutcome:
    exit_label: str
    claude_version: str
    completion_text: str
    turns: int
    token_detail: dict[str, int]
    permission_denial_count: int
    wall_seconds: float
    transcript_path: Path | None


class StageRunFatal(Exception):
    def __init__(self, stage: str, detail: str) -> None:
        super().__init__(f"{stage}: {detail}")
        self.stage = stage
        self.detail = detail


def load_registry(registry_path: Path) -> dict[str, object]:
    """Read the case and arm registry from a JSON file.

    Args:
        registry_path: Path of the registry JSON file.

    Returns:
        The registry mapping, with one entry per top-level registry section.

    Raises:
        StageRunFatal: The file holds something other than a JSON object.
    """
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(registry, dict):
        raise StageRunFatal("registry", f"{registry_path} is not an object")
    return registry


def find_by_id(
    all_entries: list[dict[str, object]], entry_id: str, label: str
) -> dict[str, object]:
    """Return the one registry entry whose ``id`` field matches.

    Args:
        all_entries: Registry entries to search.
        entry_id: The ``id`` field to match.
        label: Word naming the entry kind, used in the failure text.

    Returns:
        The single matching entry.

    Raises:
        StageRunFatal: No entry matched, or more than one matched.
    """
    all_matches = [
        each_entry for each_entry in all_entries if each_entry.get("id") == entry_id
    ]
    if len(all_matches) != 1:
        raise StageRunFatal(
            "registry", f"{label} {entry_id!r} matched {len(all_matches)} entries"
        )
    return all_matches[0]


def parse_arm(all_arm_fields: dict[str, object]) -> Arm:
    """Turn a registry arm entry into an Arm.

    Args:
        all_arm_fields: One arm entry of the registry.

    Returns:
        The arm the entry describes.
    """
    return Arm(
        arm_id=str(all_arm_fields["id"]),
        kind=str(all_arm_fields["kind"]),
        base_sha=str(all_arm_fields.get("base_sha", "")),
        all_removed_paths=tuple(
            str(each_path) for each_path in all_arm_fields.get("removed_paths", [])
        ),
        removal_patch=all_arm_fields.get("removal_patch"),
    )


def resolve_arm(all_registry_sections: dict[str, object], arm_spec: str) -> Arm:
    """Turn an arm name into an arm, building an ablation arm from its own name.

    ::

        full-cde                                  registry entry, nothing removed
        ablate:rules/a.md+rules/b.md              full install minus those two files
        flag: ablate:                             no path named
        flag: ablate:../outside.md                path climbs out of the package

    Each ablated path is relative to the package directory. The removal happens
    in the arm's source copy, so the full install keeps the file.

    Args:
        all_registry_sections: The registry mapping the arm is read from.
        arm_spec: A registry arm name, or an ``ablate:`` specification.

    Returns:
        The arm the specification names.

    Raises:
        StageRunFatal: An ablate specification names no usable path.
    """
    if not arm_spec.startswith(ABLATE_ARM_PREFIX):
        return parse_arm(find_by_id(all_registry_sections["arms"], arm_spec, "arm"))
    all_relative_paths = [
        each_path.strip()
        for each_path in arm_spec[len(ABLATE_ARM_PREFIX) :].split(ABLATE_PATH_SEPARATOR)
        if each_path.strip()
    ]
    all_unsafe_paths = [
        each_path
        for each_path in all_relative_paths
        if ".." in Path(each_path).parts or Path(each_path).is_absolute()
    ]
    if not all_relative_paths or all_unsafe_paths:
        raise StageRunFatal(
            "registry", f"ablate arm {arm_spec!r} names no usable path: {all_unsafe_paths}"
        )
    return Arm(
        arm_id=arm_spec,
        kind="ablate",
        base_sha=str(all_registry_sections["baseline_sha"]),
        all_removed_paths=tuple(
            f"{PACKAGE_RELATIVE_ROOT}/{each_path}" for each_path in all_relative_paths
        ),
        removal_patch=None,
    )


def run_label(arm_id: str) -> str:
    """Return the arm name in a form a directory name can hold.

    Args:
        arm_id: The arm name to fold into path-safe characters.

    Returns:
        The folded name, trimmed to the run-label character limit.
    """
    all_safe_characters = [
        each_character if each_character.isalnum() else "-" for each_character in arm_id
    ]
    return "".join(all_safe_characters)[:RUN_LABEL_CHARACTER_LIMIT].strip("-")


def make_layout(run_id: str) -> RunLayout:
    """Create the disposable directory tree one run works in.

    Args:
        run_id: Name of the run directory under the benchmark temp root.

    Returns:
        The layout of the created run directory.
    """
    root = Path(tempfile.gettempdir()) / "cde-bench" / "runs" / run_id
    layout = RunLayout(
        root=root,
        source=root / "source",
        home=root / "home",
        config=root / "work" / CLAUDE_DIRECTORY_NAME,
        work=root / "work",
        shim=root / "shim",
    )
    for each_directory in (layout.source, layout.home, layout.shim):
        each_directory.mkdir(parents=True, exist_ok=False)
    return layout


def contained_environment(layout: RunLayout) -> dict[str, str]:
    """Build the installer environment: substitute home, substitute git config.

    Args:
        layout: The run directory layout the substitutes live in.

    Returns:
        The environment mapping, keyed by variable name.
    """
    environment = {
        each_name: each_setting
        for each_name, each_setting in os.environ.items()
        if not each_name.upper().startswith(ALL_SESSION_VARIABLE_PREFIXES)
    }
    for each_name in ALL_AUTH_PASSTHROUGH_VARIABLES:
        if each_name in os.environ:
            environment[each_name] = os.environ[each_name]
    git_config_path = layout.home / "gitconfig"
    if not git_config_path.exists():
        git_config_path.write_text(
            "[user]\n\tname = Bench\n\temail = bench@example.invalid\n[init]\n\tdefaultBranch = main\n",
            encoding="utf-8",
        )
    environment.update(
        {
            "USERPROFILE": str(layout.home),
            "HOME": str(layout.home),
            "HOMEDRIVE": layout.home.drive,
            "HOMEPATH": str(layout.home)[len(layout.home.drive) :],
            GIT_CONFIG_GLOBAL_VARIABLE: str(git_config_path),
            GIT_CONFIG_NOSYSTEM_VARIABLE: "1",
            CODEX_HOME_VARIABLE: str(layout.home / CODEX_DIRECTORY_NAME),
            INSTALL_PSTACK_VARIABLE: "0",
            "PATH": str(layout.shim) + os.pathsep + os.environ.get("PATH", ""),
        }
    )
    return environment


def run_stage(
    stage: str,
    all_arguments: list[str],
    cwd: Path,
    all_environment: dict[str, str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    """Run one stage of the run as a child process and capture its streams.

    Args:
        stage: Name of the stage, used in the failure text.
        all_arguments: The command line to run.
        cwd: Working directory of the child process.
        all_environment: Environment mapping the child process runs with.
        timeout_seconds: How long the child process may run.

    Returns:
        The completed child process, whatever its exit status.

    Raises:
        StageRunFatal: The executable is missing, or the child timed out.
    """
    try:
        completed = subprocess.run(
            all_arguments,
            cwd=cwd,
            env=all_environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError as missing_executable:
        raise StageRunFatal(
            stage, f"executable missing: {missing_executable}"
        ) from missing_executable
    except subprocess.TimeoutExpired as timed_out:
        raise StageRunFatal(stage, f"timed out after {timeout_seconds}s") from timed_out
    return completed


def require_success(stage: str, completed: subprocess.CompletedProcess[str]) -> None:
    """End the run when a stage exited non-zero.

    Args:
        stage: Name of the stage, used in the failure text.
        completed: The completed child process to judge.

    Raises:
        StageRunFatal: The child process exited non-zero.
    """
    if completed.returncode != 0:
        raise StageRunFatal(
            stage, f"exit {completed.returncode}: {completed.stderr[-800:]}"
        )


def export_source(
    repository: Path, arm: Arm, layout: RunLayout, all_environment: dict[str, str]
) -> None:
    """Copy the arm's base revision out of the repository into the run tree.

    Args:
        repository: Path of the git repository to archive from.
        arm: The arm naming the base revision.
        layout: The run directory layout the archive lands in.
        all_environment: Environment mapping the git child process runs with.
    """
    archive_path = layout.root / "source.zip"
    completed = run_stage(
        "archive",
        [
            "git",
            "-C",
            str(repository),
            "archive",
            "--format=zip",
            "-o",
            str(archive_path),
            arm.base_sha,
        ],
        layout.root,
        all_environment,
        INSTALL_TIMEOUT_SECONDS,
    )
    require_success("archive", completed)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(layout.source)


def apply_removals(arm: Arm, layout: RunLayout, all_environment: dict[str, str]) -> None:
    """Remove the arm's ablated paths from the source copy.

    Args:
        arm: The arm naming the paths to remove and the patch to apply.
        layout: The run directory layout holding the source copy.
        all_environment: Environment mapping the git child process runs with.

    Raises:
        StageRunFatal: A named path is absent or sits outside the source copy.
    """
    source_root = layout.source.resolve()
    all_targets = [
        (source_root / each_path).resolve() for each_path in arm.all_removed_paths
    ]
    all_escapes = [
        str(each_target)
        for each_target in all_targets
        if source_root not in each_target.parents or not each_target.exists()
    ]
    if all_escapes:
        raise StageRunFatal(
            "removal", f"paths outside the source copy or absent: {all_escapes}"
        )
    for each_target in all_targets:
        if each_target.is_dir():
            shutil.rmtree(each_target)
        else:
            each_target.unlink()
    if arm.removal_patch is not None:
        patch_path = (BENCH_DIRECTORY / arm.removal_patch).resolve()
        completed = run_stage(
            "removal",
            ["git", "apply", str(patch_path)],
            layout.source,
            all_environment,
            INSTALL_TIMEOUT_SECONDS,
        )
        require_success("removal", completed)


def tree_identity(directory: Path) -> str:
    """Digest a directory tree so two arms built from one revision compare equal.

    Args:
        directory: Root of the tree to digest.

    Returns:
        A short hexadecimal digest of every file path and its bytes.
    """
    digest = hashlib.sha256()
    for each_path in sorted(
        each_file for each_file in directory.rglob("*") if each_file.is_file()
    ):
        digest.update(each_path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(each_path.read_bytes())
    return digest.hexdigest()[:16]


def session_environment(layout: RunLayout) -> dict[str, str]:
    """Build the model session environment: live home for sign-in, the rest substituted.

    Args:
        layout: The run directory layout the substitutes live in.

    Returns:
        The environment mapping the session child process runs with.
    """
    environment = dict(contained_environment(layout))
    for each_name in ALL_LIVE_HOME_VARIABLES:
        if each_name in os.environ:
            environment[each_name] = os.environ[each_name]
        else:
            environment.pop(each_name, None)
    environment[DISABLE_AUTO_MEMORY_VARIABLE] = "1"
    environment[SHIM_LOG_VARIABLE] = str(layout.work / SHIM_LOG_RELATIVE_PATH)
    environment.update(redirect_environment(layout.home, layout.config))
    run_scratch_directory = layout.root / "tmp"
    run_scratch_directory.mkdir(parents=True, exist_ok=True)
    for each_name in ALL_RUN_SCRATCH_VARIABLES:
        environment[each_name] = str(run_scratch_directory)
    return environment


def live_home_exclude_patterns() -> list[str]:
    """Return the glob patterns that hide the live config home from a session."""
    live_config = (Path.home() / CLAUDE_DIRECTORY_NAME).as_posix()
    return [f"{live_config}/**", f"{live_config}/*"]


def build_install(
    repository: Path, arm: Arm, layout: RunLayout, all_environment: dict[str, str]
) -> str:
    """Install the arm into the work directory and report the source identity.

    Args:
        repository: Path of the git repository the arm is built from.
        arm: The arm to install.
        layout: The run directory layout the install lands in.
        all_environment: Environment mapping each child process runs with.

    Returns:
        The tree identity of the installed source, or ``bare`` for a bare arm.
    """
    identity = "bare"
    if arm.kind != "bare":
        export_source(repository, arm, layout, all_environment)
        apply_removals(arm, layout, all_environment)
        identity = tree_identity(layout.source)
        completed = run_stage(
            "install",
            [
                "node",
                str(layout.source / INSTALLER_RELATIVE_PATH),
                "--target",
                str(layout.config),
            ],
            layout.source,
            all_environment,
            INSTALL_TIMEOUT_SECONDS,
        )
        (layout.root / "install.log").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        require_success("install", completed)
    layout.config.mkdir(parents=True, exist_ok=True)
    _write_install_settings(layout)
    all_install_roots = [
        each_root
        for each_root in (layout.config, layout.work / AGENTS_DIRECTORY_NAME)
        if each_root.is_dir()
    ]
    report = rewrite_live_home_references(all_install_roots, layout.config)
    all_linked = link_arm_home(layout.home, layout.work)
    (layout.root / "isolation.json").write_text(
        json.dumps(
            {"rewrite": asdict(report), "linked": all_linked}, indent=JSON_INDENT_SPACES
        ),
        encoding="utf-8",
    )
    return identity


def _write_install_settings(layout: RunLayout) -> None:
    """Add the live-home exclusions to the arm's project settings file."""
    settings_path = layout.config / "settings.json"
    settings = (
        json.loads(settings_path.read_text(encoding="utf-8"))
        if settings_path.exists()
        else {}
    )
    settings["claudeMdExcludes"] = live_home_exclude_patterns()
    settings_path.write_text(
        json.dumps(settings, indent=JSON_INDENT_SPACES), encoding="utf-8"
    )


def find_checkout_mentions(work_directory: Path) -> list[str]:
    """Name each work file whose bytes hold the path of this checkout.

    ::

        flag: tests/__pycache__/test_core.pyc   (compiled inside the fixture)
        ok:   tests/test_core.py

    A session that sees the checkout path can reach out of its run directory.

    Args:
        work_directory: Root of the work directory to scan.

    Returns:
        The relative path of each file naming the checkout.
    """
    all_needles = [
        str(BENCH_DIRECTORY).encode("utf-8").lower(),
        BENCH_DIRECTORY.as_posix().encode("utf-8").lower(),
    ]
    return [
        each_path.relative_to(work_directory).as_posix()
        for each_path in sorted(work_directory.rglob("*"))
        if each_path.is_file()
        and any(each_needle in each_path.read_bytes().lower() for each_needle in all_needles)
    ]


def expand_tokens(all_parts: list[object], case_directory: Path) -> list[str]:
    """Fill the case and bench placeholders of one setup command.

    Args:
        all_parts: The command parts, before expansion.
        case_directory: Directory the ``{case}`` placeholder names.

    Returns:
        The expanded command line, with ``python`` pointing at this interpreter.
    """
    all_expanded = [
        str(each_part)
        .replace("{case}", case_directory.as_posix())
        .replace("{bench}", BENCH_DIRECTORY.as_posix())
        for each_part in all_parts
    ]
    if all_expanded and all_expanded[0] == "python":
        all_expanded[0] = sys.executable
    return all_expanded


def prepare_work_directory(
    all_case_fields: dict[str, object],
    case_directory: Path,
    layout: RunLayout,
    all_environment: dict[str, str],
) -> None:
    """Copy the case fixture into the work directory and run its setup commands.

    Args:
        all_case_fields: One case entry of the registry.
        case_directory: Directory holding the case fixture and shim.
        layout: The run directory layout the fixture lands in.
        all_environment: Environment mapping each child process runs with.

    Raises:
        StageRunFatal: The fixture is missing, a setup command failed, or a
            work file names this checkout.
    """
    fixture_directory = case_directory / str(all_case_fields["fixture"])
    if not fixture_directory.is_dir():
        raise StageRunFatal("fixture", f"fixture missing: {fixture_directory}")
    shutil.copytree(
        fixture_directory,
        layout.work,
        ignore=shutil.ignore_patterns(*ALL_FIXTURE_CACHE_NAMES),
    )
    shim_directory = case_directory / "shim"
    if shim_directory.is_dir():
        shutil.copytree(shim_directory, layout.shim, dirs_exist_ok=True)
    init_completed = run_stage(
        "setup", ALL_GIT_INIT_ARGUMENTS, layout.work, all_environment, INSTALL_TIMEOUT_SECONDS
    )
    require_success("setup", init_completed)
    _write_git_exclusions(layout)
    all_setup_commands: list[list[object]] = [
        ALL_GIT_ADD_ARGUMENTS,
        ALL_GIT_COMMIT_ARGUMENTS,
        *all_case_fields.get("setup", []),
    ]
    all_failures = _run_setup_commands(
        all_setup_commands, case_directory, layout, all_environment
    )
    if all_failures:
        raise StageRunFatal("setup", SETUP_FAILURE_SEPARATOR.join(all_failures))
    all_checkout_mentions = find_checkout_mentions(layout.work)
    if all_checkout_mentions:
        raise StageRunFatal(
            "fixture-leak", f"work files name the checkout: {all_checkout_mentions[:5]}"
        )


def _write_git_exclusions(layout: RunLayout) -> None:
    """Keep the project installs out of the fixture's git index."""
    (layout.work / GIT_DIRECTORY_NAME / "info").mkdir(exist_ok=True)
    (layout.work / GIT_DIRECTORY_NAME / "info" / "exclude").write_text(
        "".join(f"/{each_name}/\n" for each_name in ALL_PROJECT_INSTALL_NAMES),
        encoding="utf-8",
    )


def _run_setup_commands(
    all_setup_commands: list[list[object]],
    case_directory: Path,
    layout: RunLayout,
    all_environment: dict[str, str],
) -> list[str]:
    """Run each setup command in order and describe the ones that failed."""
    return [
        f"{each_command[:3]}: exit {each_completed.returncode}: {each_completed.stderr[-400:]}"
        for each_command in all_setup_commands
        for each_completed in [
            run_stage(
                "setup",
                expand_tokens(each_command, case_directory),
                layout.work,
                all_environment,
                INSTALL_TIMEOUT_SECONDS,
            )
        ]
        if each_completed.returncode != 0
    ]


def read_stream_events(raw_stdout: str) -> list[dict[str, object]]:
    """Parse the session stream into one mapping per JSON line.

    Args:
        raw_stdout: The captured stream-json output of a session.

    Returns:
        Every line that parsed as a JSON object, in order.
    """
    all_events: list[dict[str, object]] = []
    for each_line in raw_stdout.splitlines():
        try:
            event = json.loads(each_line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            all_events.append(event)
    return all_events


def find_live_home_leaks(all_init_fields: dict[str, object]) -> list[str]:
    """Return each inventory entry of the init event that names the live config home.

    Args:
        all_init_fields: The session's init event.

    Returns:
        One entry per inventory key that names the live config home.
    """
    live_config = (Path.home() / CLAUDE_DIRECTORY_NAME).as_posix().lower()
    all_leaks: list[str] = []
    for each_key in ALL_INIT_INVENTORY_KEYS:
        flattened = json.dumps(all_init_fields.get(each_key)).replace("\\\\", "/").lower()
        if live_config in flattened:
            all_leaks.append(f"{each_key}: {flattened[:200]}")
    return all_leaks


def session_arguments(
    executable_path: str, all_case_fields: dict[str, object], model: str
) -> list[str]:
    """Build the command line one model session runs with.

    Args:
        executable_path: Resolved path of the ``claude`` executable.
        all_case_fields: One case entry of the registry.
        model: The model identifier to run.

    Returns:
        The command line for the session child process.
    """
    return [
        executable_path,
        "-p",
        str(all_case_fields["prompt"]),
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        model,
        "--setting-sources",
        "project",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        str(all_case_fields.get("allowed_tools", DEFAULT_ALLOWED_TOOLS)),
    ]


def _record_session_streams(
    layout: RunLayout, completed: subprocess.CompletedProcess[str]
) -> Path:
    """Write the session's captured streams beside the run directory."""
    transcript_path = layout.root / "session.stream.jsonl"
    transcript_path.write_text(completed.stdout, encoding="utf-8")
    (layout.root / "session.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    return transcript_path


def _split_stream_events(
    all_events: list[dict[str, object]], raw_stdout: str
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the first init event and the last result event of a session stream."""
    all_init_events = [
        each_event
        for each_event in all_events
        if each_event.get("type") == "system" and each_event.get("subtype") == "init"
    ]
    all_completion_events = [
        each_event for each_event in all_events if each_event.get("type") == "result"
    ]
    if not all_init_events or not all_completion_events:
        raise StageRunFatal(
            "session", f"stream lacks init or result: {raw_stdout[:300]!r}"
        )
    return all_init_events[0], all_completion_events[-1]


def _require_isolated_session(
    all_init_fields: dict[str, object],
    all_events: list[dict[str, object]],
    all_payload_fields: dict[str, object],
    layout: RunLayout,
) -> None:
    """End the run when the session reached the live home or wrote outside the run."""
    all_leaks = find_live_home_leaks(all_init_fields)
    if all_leaks:
        raise StageRunFatal("leak", f"init event names the live home: {all_leaks}")
    all_live_reads = find_live_home_tool_calls(all_events)
    if all_live_reads:
        raise StageRunFatal(
            "live-home-read", f"tool calls under the live home: {all_live_reads[:5]}"
        )
    all_denied_ids = frozenset(
        str(each_denial.get("tool_use_id"))
        for each_denial in all_payload_fields.get("permission_denials") or []
        if isinstance(each_denial, dict)
    )
    all_outside_writes = find_outside_writes(all_events, layout.root, all_denied_ids)
    if all_outside_writes:
        raise StageRunFatal(
            "outside-write", f"writes outside the run: {all_outside_writes[:5]}"
        )


def _session_token_detail(all_payload_fields: dict[str, object]) -> dict[str, int]:
    """Return the token counts of a session's result event."""
    usage = (
        all_payload_fields.get("usage")
        if isinstance(all_payload_fields.get("usage"), dict)
        else {}
    )
    return {
        each_key: int(usage.get(each_key, 0) or 0) for each_key in ALL_TOKEN_USAGE_KEYS
    }


def _session_exit_label(all_payload_fields: dict[str, object], return_code: int) -> str:
    """Return ``ok``, or the label naming how the session ended badly."""
    if all_payload_fields.get("is_error") or return_code != 0:
        return f"session_error:{all_payload_fields.get('terminal_reason') or return_code}"
    return "ok"


def run_session(
    all_case_fields: dict[str, object],
    model: str,
    layout: RunLayout,
    all_environment: dict[str, str],
) -> SessionOutcome:
    """Run one model session over the prepared work directory.

    Args:
        all_case_fields: One case entry of the registry.
        model: The model identifier to run.
        layout: The run directory layout the session works in.
        all_environment: Environment mapping the session child process runs with.

    Returns:
        What the session did: its exit label, counts, and transcript path.

    Raises:
        StageRunFatal: The executable is missing, the stream lacks its init or
            result event, or the session broke out of the run directory.
    """
    resolved_executable = shutil.which("claude", path=all_environment["PATH"])
    if resolved_executable is None:
        raise StageRunFatal("session", "claude executable missing")
    started = time.monotonic()
    completed = run_stage(
        "session",
        session_arguments(resolved_executable, all_case_fields, model),
        layout.work,
        all_environment,
        int(all_case_fields.get("timeout_seconds", DEFAULT_SESSION_TIMEOUT_SECONDS)),
    )
    wall_seconds = round(time.monotonic() - started, 1)
    transcript_path = _record_session_streams(layout, completed)
    all_events = read_stream_events(completed.stdout)
    init_event, all_payload_fields = _split_stream_events(all_events, completed.stdout)
    (layout.root / "init.json").write_text(
        json.dumps(init_event, indent=JSON_INDENT_SPACES), encoding="utf-8"
    )
    _require_isolated_session(init_event, all_events, all_payload_fields, layout)
    return SessionOutcome(
        exit_label=_session_exit_label(all_payload_fields, completed.returncode),
        claude_version=str(init_event.get("claude_code_version", "")),
        completion_text=str(all_payload_fields.get("result", "")),
        turns=int(all_payload_fields.get("num_turns", 0) or 0),
        token_detail=_session_token_detail(all_payload_fields),
        permission_denial_count=len(all_payload_fields.get("permission_denials") or []),
        wall_seconds=wall_seconds,
        transcript_path=transcript_path,
    )


def append_row(rows_path: Path, all_row_cells: dict[str, str]) -> None:
    """Append one run row to the TSV, writing the header for a new file.

    Args:
        rows_path: Path of the TSV the row is appended to.
        all_row_cells: The row, keyed by column name.
    """
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not rows_path.exists()
    with rows_path.open("a", encoding="utf-8", newline="") as rows_file:
        writer = csv.DictWriter(rows_file, fieldnames=ALL_ROW_COLUMNS, delimiter="\t")
        if is_new:
            writer.writeheader()
        writer.writerow(all_row_cells)


def serialize_grades(all_grades: list[GraderVerdict]) -> str:
    """Render every grader verdict as one JSON object for the row.

    Args:
        all_grades: One verdict per grader of the case.

    Returns:
        A JSON object keyed by grader identifier, sorted by key.
    """
    return json.dumps(
        {
            each_grade.grader_id: [each_grade.status, each_grade.detail]
            for each_grade in all_grades
        },
        sort_keys=True,
    )


def _opening_row(
    run_id: str,
    all_case_fields: dict[str, object],
    arm: Arm,
    arguments: argparse.Namespace,
) -> dict[str, str]:
    """Return the row with every column present and the run's own fields filled."""
    all_row_cells = {each_column: "" for each_column in ALL_ROW_COLUMNS}
    all_row_cells.update(
        {
            "run_id": run_id,
            "case": str(all_case_fields["id"]),
            "case_revision": str(all_case_fields["revision"]),
            "arm": arm.arm_id,
            "repetition": str(arguments.repetition),
            "model": arguments.model,
        }
    )
    return all_row_cells


def _fill_outcome_columns(
    all_row_cells: dict[str, str], outcome: SessionOutcome
) -> None:
    """Copy the session's counts and paths into the row."""
    all_row_cells["exit"] = outcome.exit_label
    all_row_cells["claude_version"] = outcome.claude_version
    all_row_cells["turns"] = str(outcome.turns)
    all_row_cells["tokens"] = str(sum(outcome.token_detail.values()))
    all_row_cells["token_detail"] = json.dumps(outcome.token_detail, sort_keys=True)
    all_row_cells["wall_seconds"] = str(outcome.wall_seconds)
    all_row_cells["permission_denials"] = str(outcome.permission_denial_count)
    all_row_cells["transcript_path"] = str(outcome.transcript_path or "")


def execute_run(arguments: argparse.Namespace) -> dict[str, str]:
    """Run one case once in one arm and return the row that describes it.

    Args:
        arguments: The parsed command line of this run.

    Returns:
        The run row, keyed by column name.
    """
    registry = load_registry(Path(arguments.registry))
    all_case_fields = find_by_id(registry["cases"], arguments.case, "case")
    arm = resolve_arm(registry, str(arguments.arm))
    case_directory = (
        Path(arguments.registry).resolve().parent / "cases" / str(all_case_fields["id"])
    )
    run_id = (
        f"{all_case_fields['id']}--{run_label(arm.arm_id)}"
        f"--r{arguments.repetition}--{uuid.uuid4().hex[:8]}"
    )
    layout = make_layout(run_id)
    environment = contained_environment(layout)
    all_row_cells = _opening_row(run_id, all_case_fields, arm, arguments)
    try:
        prepare_work_directory(all_case_fields, case_directory, layout, environment)
        all_row_cells["tree_identity"] = build_install(
            Path(arguments.repo).resolve(), arm, layout, environment
        )
        outcome = run_session(
            all_case_fields, arguments.model, layout, session_environment(layout)
        )
    except StageRunFatal as failure:
        all_row_cells["exit"] = f"harness_error:{failure.stage}"
        all_row_cells["grader_results"] = json.dumps(
            {"harness": ["error", failure.detail[:HARNESS_DETAIL_CHARACTER_LIMIT]]}
        )
        return all_row_cells
    _fill_outcome_columns(all_row_cells, outcome)
    if outcome.exit_label != "ok":
        all_row_cells["grader_results"] = json.dumps(
            {"harness": ["error", outcome.completion_text[:HARNESS_DETAIL_CHARACTER_LIMIT]]}
        )
        return all_row_cells
    context = GradingContext(
        work_directory=layout.work,
        case_directory=case_directory,
        reply_text=outcome.completion_text,
        transcript_path=outcome.transcript_path,
    )
    all_row_cells["grader_results"] = serialize_grades(
        run_graders(all_case_fields["graders"], context)
    )
    return all_row_cells


def main(stream: TextIO = sys.stdout) -> int:
    """Parse the command line, run one case once, and report the row.

    Args:
        stream: Where the run row is written.

    Returns:
        Zero when the run ended ``ok``, one otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--repetition", type=int, default=1)
    parser.add_argument("--model", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--rows", required=True)
    parser.add_argument("--registry", default=str(BENCH_DIRECTORY / "cases.json"))
    arguments = parser.parse_args()
    all_row_cells = execute_run(arguments)
    append_row(Path(arguments.rows), all_row_cells)
    stream.write(json.dumps(all_row_cells, indent=JSON_INDENT_SPACES) + "\n")
    return 0 if all_row_cells["exit"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
