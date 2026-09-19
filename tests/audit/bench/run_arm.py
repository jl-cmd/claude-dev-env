"""Run one benchmark case once in one arm and append a run row to a TSV.

Every mutation happens under a disposable run directory in the OS temp root.
The installer runs with a substitute home and a substitute global git config,
and writes the arm into ``<work>/.claude`` as a project-level install.

The model session signs in through the live home. It loads project settings
only, skips every MCP server, keeps no session file, and carries a
``claudeMdExcludes`` entry that hides the live home's memory and rule files.
A run whose init event still names a path under the live home ends as
``harness_error:leak``.

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
from typing import Any

from arm_isolation import (
    find_live_home_tool_calls,
    find_outside_writes,
    link_arm_home,
    redirect_environment,
    rewrite_live_home_references,
)
from graders import GraderResult, GradingContext, run_graders

BENCH_DIRECTORY = Path(__file__).resolve().parent

INSTALLER_RELATIVE_PATH = Path("packages/claude-dev-env/bin/install.mjs")
ALL_AUTH_PASSTHROUGH_VARIABLES = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
ALL_SESSION_VARIABLE_PREFIXES = ("CLAUDE", "ANTHROPIC")
DEFAULT_ALLOWED_TOOLS = "Bash,PowerShell,Read,Glob,Grep"
ALL_PROJECT_INSTALL_NAMES = (".claude", ".agents")
SHIM_LOG_RELATIVE_PATH = Path(".git") / "bench-shim.log"
DEFAULT_SESSION_TIMEOUT_SECONDS = 1800
ALL_FIXTURE_CACHE_NAMES = ("__pycache__", ".pytest_cache", "*.pyc")
INSTALL_TIMEOUT_SECONDS = 600
ALL_ROW_COLUMNS = (
    "run_id",
    "case",
    "case_revision",
    "arm",
    "tree_identity",
    "repetition",
    "model",
    "claude_version",
    "exit",
    "grader_results",
    "turns",
    "tokens",
    "token_detail",
    "wall_seconds",
    "permission_denials",
    "transcript_path",
)


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
    result_text: str
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


def load_registry(registry_path: Path) -> dict[str, Any]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(registry, dict):
        raise StageRunFatal("registry", f"{registry_path} is not an object")
    return registry


def find_by_id(
    all_entries: list[dict[str, Any]], entry_id: str, label: str
) -> dict[str, Any]:
    all_matches = [
        each_entry for each_entry in all_entries if each_entry.get("id") == entry_id
    ]
    if len(all_matches) != 1:
        raise StageRunFatal(
            "registry", f"{label} {entry_id!r} matched {len(all_matches)} entries"
        )
    return all_matches[0]


def parse_arm(arm_entry: dict[str, Any]) -> Arm:
    return Arm(
        arm_id=str(arm_entry["id"]),
        kind=str(arm_entry["kind"]),
        base_sha=str(arm_entry.get("base_sha", "")),
        all_removed_paths=tuple(
            str(each_path) for each_path in arm_entry.get("removed_paths", [])
        ),
        removal_patch=arm_entry.get("removal_patch"),
    )


def make_layout(run_id: str) -> RunLayout:
    root = Path(tempfile.gettempdir()) / "cde-bench" / "runs" / run_id
    layout = RunLayout(
        root=root,
        source=root / "source",
        home=root / "home",
        config=root / "work" / ".claude",
        work=root / "work",
        shim=root / "shim",
    )
    for each_directory in (layout.source, layout.home, layout.shim):
        each_directory.mkdir(parents=True, exist_ok=False)
    return layout


def contained_environment(layout: RunLayout) -> dict[str, str]:
    environment = {
        each_name: each_value
        for each_name, each_value in os.environ.items()
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
            "GIT_CONFIG_GLOBAL": str(git_config_path),
            "GIT_CONFIG_NOSYSTEM": "1",
            "CODEX_HOME": str(layout.home / ".codex"),
            "CDE_INSTALL_PSTACK": "0",
            "PATH": str(layout.shim) + os.pathsep + os.environ.get("PATH", ""),
        }
    )
    return environment


def run_stage(
    stage: str,
    all_arguments: list[str],
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            all_arguments,
            cwd=cwd,
            env=environment,
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
    if completed.returncode != 0:
        raise StageRunFatal(
            stage, f"exit {completed.returncode}: {completed.stderr[-800:]}"
        )


def export_source(
    repository: Path, arm: Arm, layout: RunLayout, environment: dict[str, str]
) -> None:
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
        environment,
        INSTALL_TIMEOUT_SECONDS,
    )
    require_success("archive", completed)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(layout.source)


def apply_removals(arm: Arm, layout: RunLayout, environment: dict[str, str]) -> None:
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
            environment,
            INSTALL_TIMEOUT_SECONDS,
        )
        require_success("removal", completed)


def tree_identity(directory: Path) -> str:
    digest = hashlib.sha256()
    for each_path in sorted(
        each_file for each_file in directory.rglob("*") if each_file.is_file()
    ):
        digest.update(each_path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(each_path.read_bytes())
    return digest.hexdigest()[:16]


def session_environment(layout: RunLayout) -> dict[str, str]:
    """Return the model session's environment: live home for sign-in, the rest substituted."""
    environment = dict(contained_environment(layout))
    for each_name in ("USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH"):
        if each_name in os.environ:
            environment[each_name] = os.environ[each_name]
        else:
            environment.pop(each_name, None)
    environment["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    environment["BENCH_SHIM_LOG"] = str(layout.work / SHIM_LOG_RELATIVE_PATH)
    environment.update(redirect_environment(layout.home, layout.config))
    run_temp_directory = layout.root / "tmp"
    run_temp_directory.mkdir(parents=True, exist_ok=True)
    for each_name in ("TEMP", "TMP", "TMPDIR"):
        environment[each_name] = str(run_temp_directory)
    return environment


def live_home_exclude_patterns() -> list[str]:
    live_config = (Path.home() / ".claude").as_posix()
    return [f"{live_config}/**", f"{live_config}/*"]


def build_install(
    repository: Path, arm: Arm, layout: RunLayout, environment: dict[str, str]
) -> str:
    identity = "bare"
    if arm.kind != "bare":
        export_source(repository, arm, layout, environment)
        apply_removals(arm, layout, environment)
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
            environment,
            INSTALL_TIMEOUT_SECONDS,
        )
        (layout.root / "install.log").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        require_success("install", completed)
    layout.config.mkdir(parents=True, exist_ok=True)
    settings_path = layout.config / "settings.json"
    settings = (
        json.loads(settings_path.read_text(encoding="utf-8"))
        if settings_path.exists()
        else {}
    )
    settings["claudeMdExcludes"] = live_home_exclude_patterns()
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    all_install_roots = [
        each_root
        for each_root in (layout.config, layout.work / ".agents")
        if each_root.is_dir()
    ]
    report = rewrite_live_home_references(all_install_roots, layout.config)
    all_linked = link_arm_home(layout.home, layout.work)
    (layout.root / "isolation.json").write_text(
        json.dumps({"rewrite": asdict(report), "linked": all_linked}, indent=2),
        encoding="utf-8",
    )
    return identity


def find_checkout_mentions(work_directory: Path) -> list[str]:
    """Name each work file whose bytes hold the path of this checkout.

    ::

        flag: tests/__pycache__/test_core.pyc   (compiled inside the fixture)
        ok:   tests/test_core.py

    A session that sees the checkout path can reach out of its run directory.
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


def expand_tokens(all_parts: list[Any], case_directory: Path) -> list[str]:
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
    case: dict[str, Any],
    case_directory: Path,
    layout: RunLayout,
    environment: dict[str, str],
) -> None:
    fixture_directory = case_directory / str(case["fixture"])
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
        "setup", ["git", "init", "-q"], layout.work, environment, INSTALL_TIMEOUT_SECONDS
    )
    require_success("setup", init_completed)
    (layout.work / ".git" / "info").mkdir(exist_ok=True)
    (layout.work / ".git" / "info" / "exclude").write_text(
        "".join(f"/{each_name}/\n" for each_name in ALL_PROJECT_INSTALL_NAMES),
        encoding="utf-8",
    )
    all_setup_commands: list[list[Any]] = [
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "fixture"],
        *case.get("setup", []),
    ]
    all_failures = [
        f"{each_command[:3]}: exit {each_completed.returncode}: {each_completed.stderr[-400:]}"
        for each_command in all_setup_commands
        for each_completed in [
            run_stage(
                "setup",
                expand_tokens(each_command, case_directory),
                layout.work,
                environment,
                INSTALL_TIMEOUT_SECONDS,
            )
        ]
        if each_completed.returncode != 0
    ]
    if all_failures:
        raise StageRunFatal("setup", "; ".join(all_failures))
    all_checkout_mentions = find_checkout_mentions(layout.work)
    if all_checkout_mentions:
        raise StageRunFatal(
            "fixture-leak", f"work files name the checkout: {all_checkout_mentions[:5]}"
        )


def read_stream_events(raw_stdout: str) -> list[dict[str, Any]]:
    all_events: list[dict[str, Any]] = []
    for each_line in raw_stdout.splitlines():
        try:
            event = json.loads(each_line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            all_events.append(event)
    return all_events


def find_live_home_leaks(init_event: dict[str, Any]) -> list[str]:
    """Return each inventory entry of the init event that names the live config home."""
    live_config = (Path.home() / ".claude").as_posix().lower()
    all_leaks: list[str] = []
    for each_key in ("plugins", "memory_paths", "mcp_servers"):
        flattened = json.dumps(init_event.get(each_key)).replace("\\\\", "/").lower()
        if live_config in flattened:
            all_leaks.append(f"{each_key}: {flattened[:200]}")
    return all_leaks


def run_session(
    case: dict[str, Any], model: str, layout: RunLayout, environment: dict[str, str]
) -> SessionOutcome:
    resolved_executable = shutil.which("claude", path=environment["PATH"])
    if resolved_executable is None:
        raise StageRunFatal("session", "claude executable missing")
    all_arguments = [
        resolved_executable,
        "-p",
        str(case["prompt"]),
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
        str(case.get("allowed_tools", DEFAULT_ALLOWED_TOOLS)),
    ]
    started = time.monotonic()
    completed = run_stage(
        "session",
        all_arguments,
        layout.work,
        environment,
        int(case.get("timeout_seconds", DEFAULT_SESSION_TIMEOUT_SECONDS)),
    )
    wall_seconds = round(time.monotonic() - started, 1)
    transcript_path = layout.root / "session.stream.jsonl"
    transcript_path.write_text(completed.stdout, encoding="utf-8")
    (layout.root / "session.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    all_events = read_stream_events(completed.stdout)
    all_init_events = [
        each_event
        for each_event in all_events
        if each_event.get("type") == "system" and each_event.get("subtype") == "init"
    ]
    all_result_events = [
        each_event for each_event in all_events if each_event.get("type") == "result"
    ]
    if not all_init_events or not all_result_events:
        raise StageRunFatal(
            "session", f"stream lacks init or result: {completed.stdout[:300]!r}"
        )
    init_event = all_init_events[0]
    payload = all_result_events[-1]
    (layout.root / "init.json").write_text(
        json.dumps(init_event, indent=2), encoding="utf-8"
    )
    all_leaks = find_live_home_leaks(init_event)
    if all_leaks:
        raise StageRunFatal("leak", f"init event names the live home: {all_leaks}")
    all_live_reads = find_live_home_tool_calls(all_events)
    if all_live_reads:
        raise StageRunFatal(
            "live-home-read", f"tool calls under the live home: {all_live_reads[:5]}"
        )
    all_denied_ids = frozenset(
        str(each_denial.get("tool_use_id"))
        for each_denial in payload.get("permission_denials") or []
        if isinstance(each_denial, dict)
    )
    all_outside_writes = find_outside_writes(all_events, layout.root, all_denied_ids)
    if all_outside_writes:
        raise StageRunFatal(
            "outside-write", f"writes outside the run: {all_outside_writes[:5]}"
        )
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    token_detail = {
        each_key: int(usage.get(each_key, 0) or 0)
        for each_key in (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )
    }
    exit_label = "ok"
    if payload.get("is_error") or completed.returncode != 0:
        exit_label = (
            f"session_error:{payload.get('terminal_reason') or completed.returncode}"
        )
    return SessionOutcome(
        exit_label=exit_label,
        claude_version=str(init_event.get("claude_code_version", "")),
        result_text=str(payload.get("result", "")),
        turns=int(payload.get("num_turns", 0) or 0),
        token_detail=token_detail,
        permission_denial_count=len(payload.get("permission_denials") or []),
        wall_seconds=wall_seconds,
        transcript_path=transcript_path,
    )


def append_row(rows_path: Path, row: dict[str, str]) -> None:
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not rows_path.exists()
    with rows_path.open("a", encoding="utf-8", newline="") as rows_file:
        writer = csv.DictWriter(rows_file, fieldnames=ALL_ROW_COLUMNS, delimiter="\t")
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def serialize_results(all_results: list[GraderResult]) -> str:
    return json.dumps(
        {
            each_result.grader_id: [each_result.status, each_result.detail]
            for each_result in all_results
        },
        sort_keys=True,
    )


def execute_run(arguments: argparse.Namespace) -> dict[str, str]:
    registry = load_registry(Path(arguments.registry))
    case = find_by_id(registry["cases"], arguments.case, "case")
    arm = parse_arm(find_by_id(registry["arms"], arguments.arm, "arm"))
    case_directory = (
        Path(arguments.registry).resolve().parent / "cases" / str(case["id"])
    )
    run_id = (
        f"{case['id']}--{arm.arm_id}--r{arguments.repetition}--{uuid.uuid4().hex[:8]}"
    )
    layout = make_layout(run_id)
    environment = contained_environment(layout)
    row = {each_column: "" for each_column in ALL_ROW_COLUMNS}
    row.update(
        {
            "run_id": run_id,
            "case": str(case["id"]),
            "case_revision": str(case["revision"]),
            "arm": arm.arm_id,
            "repetition": str(arguments.repetition),
            "model": arguments.model,
        }
    )
    try:
        prepare_work_directory(case, case_directory, layout, environment)
        row["tree_identity"] = build_install(
            Path(arguments.repo).resolve(), arm, layout, environment
        )
        outcome = run_session(
            case, arguments.model, layout, session_environment(layout)
        )
    except StageRunFatal as failure:
        row["exit"] = f"harness_error:{failure.stage}"
        row["grader_results"] = json.dumps({"harness": ["error", failure.detail[:400]]})
        return row
    row["exit"] = outcome.exit_label
    row["claude_version"] = outcome.claude_version
    row["turns"] = str(outcome.turns)
    row["tokens"] = str(sum(outcome.token_detail.values()))
    row["token_detail"] = json.dumps(outcome.token_detail, sort_keys=True)
    row["wall_seconds"] = str(outcome.wall_seconds)
    row["permission_denials"] = str(outcome.permission_denial_count)
    row["transcript_path"] = str(outcome.transcript_path or "")
    if outcome.exit_label != "ok":
        row["grader_results"] = json.dumps(
            {"harness": ["error", outcome.result_text[:400]]}
        )
        return row
    context = GradingContext(
        work_directory=layout.work,
        case_directory=case_directory,
        result_text=outcome.result_text,
        transcript_path=outcome.transcript_path,
    )
    row["grader_results"] = serialize_results(run_graders(case["graders"], context))
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--repetition", type=int, default=1)
    parser.add_argument("--model", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--rows", required=True)
    parser.add_argument("--registry", default=str(BENCH_DIRECTORY / "cases.json"))
    arguments = parser.parse_args()
    row = execute_run(arguments)
    append_row(Path(arguments.rows), row)
    print(json.dumps(row, indent=2))
    return 0 if row["exit"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
