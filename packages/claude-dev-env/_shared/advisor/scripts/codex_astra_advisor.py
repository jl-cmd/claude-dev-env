"""Bind and consult a read-only Codex CLI session through Astra."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

_scripts_directory = Path(__file__).resolve().parent
_config_directory = _scripts_directory / "config"
for each_import_directory in (_scripts_directory, _config_directory):
    each_import_directory_text = str(each_import_directory)
    if each_import_directory_text not in sys.path:
        sys.path[:0] = [each_import_directory_text]

from advisor_scripts_constants.advisor_route_constants import (
    ADVISOR_CODEX_MODEL_ID,
    ADVISOR_EFFORT_ALIASES,
    ADVISOR_EFFORT_DEFAULT,
    ADVISOR_EFFORT_ENV_VAR,
    ADVISOR_ROUTING_TIMEOUT_SECONDS,
    ALL_ADVISOR_EFFORT_LEVELS,
    SPAWN_OUTCOME_KEY,
)
from advisor_scripts_constants.astra_advisor_constants import (
    ADVISOR_CODEX_EXECUTABLE_ENV_VAR,
    ALL_ACCOUNT_PICKER_RELATIVE_PARTS,
    ALL_ASTRA_TRUTHY_VALUES,
    ASTRA_BIND_FAILURE_REASON,
    ASTRA_CODEX_TIMEOUT_REASON,
    ASTRA_CODEX_TIMEOUT_SECONDS,
    ASTRA_EFFORT_FLAG,
    ASTRA_ENABLE_FLAG,
    ASTRA_ENV_VAR,
    ASTRA_EXECUTABLE_NOT_FOUND_REASON,
    ASTRA_FALLBACK_KIND_BROKEN,
    ASTRA_FALLBACK_KIND_DECLINED,
    ASTRA_SESSION_ID_METAVAR,
    CODEX_CONFIG_FLAG,
    CODEX_EXEC_SUBCOMMAND,
    CODEX_EXECUTABLE,
    CODEX_HOME_ENV_VAR,
    CODEX_JSON_FLAG,
    CODEX_MODEL_FLAG,
    CODEX_PROMPT_FROM_STDIN,
    CODEX_READ_ONLY_SANDBOX,
    CODEX_REASONING_CONFIG_TEMPLATE,
    CODEX_RESUME_SUBCOMMAND,
    CODEX_SANDBOX_FLAG,
    SHARED_PACKAGE_ROOT_PARENT_INDEX,
)
from codex_astra_preflight import AstraPreflight, run_astra_preflight
from codex_astra_reply import (
    CodexAstraAdvisorReply,
    build_fallback_reply,
    parse_codex_jsonl_reply,
)

def _resolved_settings(
    all_settings: Mapping[str, str] | None,
) -> Mapping[str, str]:
    return os.environ if all_settings is None else all_settings


def is_astra_advisor_enabled(all_settings: Mapping[str, str] | None) -> bool:
    """Return whether the Astra advisor flag is on.

    Args:
        all_settings: Environment mapping, or None to read os.environ.

    Returns:
        True when the flag holds a truthy value.
    """
    raw_setting = _resolved_settings(all_settings).get(ASTRA_ENV_VAR, "")
    return raw_setting.strip().lower() in ALL_ASTRA_TRUTHY_VALUES


def _advisor_route_request(
    all_settings: Mapping[str, str] | None,
    policy_path: Path | None,
) -> dict[str, object]:
    requested = _resolved_settings(all_settings).get(ADVISOR_EFFORT_ENV_VAR, "")
    request: dict[str, object] = {}
    if requested.strip():
        request["reasoning_effort"] = requested
    if policy_path is not None:
        request["policyPath"] = str(policy_path)
    return request


def _parse_advisor_route(
    completed: subprocess.CompletedProcess[str],
) -> Mapping[str, object]:
    try:
        route = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("advisor model routing returned invalid JSON") from error
    if not isinstance(route, Mapping):
        raise TypeError("advisor model routing returned an invalid response")
    if completed.returncode != 0:
        diagnostic = route.get("diagnostic")
        message = str(diagnostic) if diagnostic else f"advisor model routing failed: process exit {completed.returncode}"
        raise RuntimeError(message)
    return route


def _run_advisor_route(all_request: Mapping[str, object]) -> Mapping[str, object]:
    resolver_path = _scripts_directory.parents[2] / "scripts" / "resolve_advisor_model_route.mjs"
    try:
        completed = subprocess.run(
            ["node", str(resolver_path)],
            input=json.dumps(all_request),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=ADVISOR_ROUTING_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"advisor model routing failed: {error}") from error

    return _parse_advisor_route(completed)


def _selected_advisor_pair(all_route: Mapping[str, object]) -> tuple[str, str]:
    if all_route.get("status") not in {"pass", "remapped"}:
        raise RuntimeError(all_route.get("diagnostic") or "advisor model routing blocked")
    selected = all_route.get("selected")
    if not isinstance(selected, Mapping):
        raise TypeError("advisor model routing returned no selected pair")
    model_id = selected.get("model")
    effort = selected.get("effort")
    if not isinstance(model_id, str) or not isinstance(effort, str):
        raise TypeError("advisor model routing returned an invalid selected pair")
    return model_id, effort


def resolve_advisor_pair(
    all_settings: Mapping[str, str] | None,
    policy_path: Path | None,
) -> tuple[str, str]:
    """Return the policy-selected advisor model and effort.

    Args:
        all_settings: Environment mapping, or None to read os.environ.
        policy_path: Policy file path for the resolver, or None for the installed path.

    Returns:
        The selected native model ID and effort.

    Raises:
        RuntimeError: If the bridge fails or returns a blocked route.
        TypeError: If the bridge returns an invalid shape.
    """
    route = _run_advisor_route(_advisor_route_request(all_settings, policy_path))
    return _selected_advisor_pair(route)


def resolve_advisor_effort(all_settings: Mapping[str, str] | None) -> str:
    """Return the policy-selected advisor effort.

    Args:
        all_settings: Environment mapping, or None to read os.environ.

    Returns:
        The selected effort.
    """
    return resolve_advisor_pair(all_settings, None)[1]


def resolve_account_picker_path() -> Path:
    """Return the Codex account picker in the scripts directory beside this shared tree.

    ::

        ~/.claude/_shared/advisor/scripts  ->  ~/.claude/scripts/codex_account_choice.py

    Returns:
        Path to ``codex_account_choice.py``.
    """
    shared_root = _scripts_directory.parents[SHARED_PACKAGE_ROOT_PARENT_INDEX]
    return shared_root.joinpath(*ALL_ACCOUNT_PICKER_RELATIVE_PARTS)


def resolve_codex_executable(all_settings: Mapping[str, str] | None) -> str | None:
    """Return the Codex executable from the override or PATH.

    Args:
        all_settings: Environment mapping, or None to read os.environ.

    Returns:
        Executable path or name, or None if neither is set.
    """
    override = _resolved_settings(all_settings).get(ADVISOR_CODEX_EXECUTABLE_ENV_VAR, "").strip()
    return override or shutil.which(CODEX_EXECUTABLE)


def build_codex_arguments(
    codex_executable: str,
    session_id: str | None = None,
    reasoning_effort: str = ADVISOR_EFFORT_DEFAULT,
    model_id: str = ADVISOR_CODEX_MODEL_ID,
) -> list[str]:
    """Build the Codex command list for bind or resume.

    Args:
        codex_executable: Codex executable path or name.
        session_id: Session to resume, or None for a new bind.
        reasoning_effort: Codex reasoning effort.
        model_id: Native Codex model ID.

    Returns:
        Command arguments for Codex exec.
    """
    arguments = [
        codex_executable,
        CODEX_EXEC_SUBCOMMAND,
        CODEX_MODEL_FLAG,
        model_id,
        CODEX_CONFIG_FLAG,
        CODEX_REASONING_CONFIG_TEMPLATE.format(effort=reasoning_effort),
        CODEX_SANDBOX_FLAG,
        CODEX_READ_ONLY_SANDBOX,
        CODEX_JSON_FLAG,
    ]
    if session_id is not None:
        arguments.extend([CODEX_RESUME_SUBCOMMAND, session_id])
    arguments.append(CODEX_PROMPT_FROM_STDIN)
    return arguments


def _resolve_preflight(
    preflight: AstraPreflight | None,
    picker_path: Path | None,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> AstraPreflight:
    if preflight is not None:
        return preflight
    resolved_path = resolve_account_picker_path() if picker_path is None else picker_path
    return run_astra_preflight(resolved_path, process_runner)


def _codex_environment(codex_home: Path | None) -> dict[str, str] | None:
    if codex_home is None:
        return None
    return {**os.environ, CODEX_HOME_ENV_VAR: str(codex_home)}


def _run_codex(
    prompt: str,
    working_directory: Path,
    session_id: str | None,
    all_settings: Mapping[str, str] | None,
    executable: str,
    codex_home: Path | None,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> subprocess.CompletedProcess[str]:
    model_id, effort = resolve_advisor_pair(all_settings, None)
    return process_runner(
        build_codex_arguments(
            executable,
            session_id=session_id,
            reasoning_effort=effort,
            model_id=model_id,
        ),
        cwd=str(working_directory),
        env=_codex_environment(codex_home),
        input=prompt,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=ASTRA_CODEX_TIMEOUT_SECONDS,
    )


def _run_enabled_advisor(
    prompt: str,
    working_directory: Path,
    setting_by_name: Mapping[str, str] | None,
    session_id: str | None,
    executable: str,
    resolved_preflight: AstraPreflight,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> CodexAstraAdvisorReply:
    if not resolved_preflight.eligible:
        return build_fallback_reply(resolved_preflight.reason, True, resolved_preflight.fallback_kind)
    try:
        completed = _run_codex(
            prompt,
            working_directory,
            session_id,
            setting_by_name,
            executable,
            resolved_preflight.codex_home,
            process_runner,
        )
    except subprocess.TimeoutExpired as error:
        return build_fallback_reply(
            f"{ASTRA_CODEX_TIMEOUT_REASON}: {error}",
            True,
            ASTRA_FALLBACK_KIND_BROKEN,
        )
    except (OSError, subprocess.SubprocessError, RuntimeError, TypeError) as error:
        return build_fallback_reply(
            f"{ASTRA_BIND_FAILURE_REASON}: {error}",
            True,
            ASTRA_FALLBACK_KIND_BROKEN,
        )
    if completed.returncode != 0:
        return build_fallback_reply(
            f"{ASTRA_BIND_FAILURE_REASON}: process exit {completed.returncode}",
            True,
            ASTRA_FALLBACK_KIND_BROKEN,
        )
    return parse_codex_jsonl_reply(
        completed.stdout,
        session_id,
        True,
        ASTRA_FALLBACK_KIND_BROKEN,
    )


def run_codex_astra_advisor(
    prompt: str,
    working_directory: Path,
    preflight: AstraPreflight | None,
    picker_path: Path | None,
    setting_by_name: Mapping[str, str] | None,
    session_id: str | None,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> CodexAstraAdvisorReply:
    """Bind or resume a read-only Codex Astra advisor.

    Args:
        prompt: Advisor prompt text.
        working_directory: Working directory for Codex.
        preflight: Account picker result, or None to run the picker.
        picker_path: Account picker path, or None for the one beside this shared tree.
        setting_by_name: Environment mapping, or None to read os.environ.
        session_id: Session to resume, or None for a new bind.
        process_runner: Callable that runs the picker and Codex.

    Returns:
        Advisor reply, or a fallback.
    """
    if not is_astra_advisor_enabled(setting_by_name):
        return build_fallback_reply("Astra advisor flag is disabled", False, ASTRA_FALLBACK_KIND_DECLINED)
    executable = resolve_codex_executable(setting_by_name)
    if executable is None:
        return build_fallback_reply(ASTRA_EXECUTABLE_NOT_FOUND_REASON, True)
    resolved_preflight = _resolve_preflight(preflight, picker_path, process_runner)
    return _run_enabled_advisor(prompt, working_directory, setting_by_name, session_id, executable, resolved_preflight, process_runner)


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for bind and resume.

    Returns:
        Argument parser for this helper.
    """
    parser = argparse.ArgumentParser(description="Bind or consult a read-only Codex Astra advisor.")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--bind", action="store_true")
    mode_group.add_argument("--resume", metavar=ASTRA_SESSION_ID_METAVAR)
    parser.add_argument("--cwd", required=True, type=Path)
    parser.add_argument(ASTRA_ENABLE_FLAG, dest="is_astra_requested", action="store_true")
    parser.add_argument(
        ASTRA_EFFORT_FLAG,
        dest="astra_effort",
        choices=(*ALL_ADVISOR_EFFORT_LEVELS, *ADVISOR_EFFORT_ALIASES),
        default=None,
    )
    return parser


def main(all_cli_arguments: Sequence[str]) -> int:
    """Run one bind or resume request from stdin.

    Args:
        all_cli_arguments: CLI arguments after the program name.

    Returns:
        0 when the advisor reply succeeds, 1 on fallback.
    """
    parsed = build_argument_parser().parse_args(list(all_cli_arguments))
    all_settings = dict(os.environ)
    if parsed.is_astra_requested:
        all_settings[ASTRA_ENV_VAR] = "1"
    if parsed.astra_effort is not None:
        all_settings[ADVISOR_EFFORT_ENV_VAR] = parsed.astra_effort
    reply = run_codex_astra_advisor(
        sys.stdin.read(),
        parsed.cwd,
        None,
        None,
        all_settings,
        parsed.resume if not parsed.bind else None,
        subprocess.run,
    )
    payload = asdict(reply)
    payload[SPAWN_OUTCOME_KEY] = payload.pop("outcome")
    sys.stdout.write(f"{json.dumps(payload, sort_keys=True)}\n")
    return 0 if reply.successful else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
