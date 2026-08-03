"""Behavioral tests for the executable Codex Sol advisor path."""

import io
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_sol_module() -> ModuleType:
    scripts_root = Path(__file__).parent.parent
    config_root = scripts_root / "config"
    sys.path.insert(0, str(config_root))
    specification = importlib.util.spec_from_file_location(
        "codex_sol_advisor", scripts_root / "codex_sol_advisor.py"
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


sol_advisor = _load_sol_module()
SCRIPTS_ROOT = Path(__file__).parent.parent
USAGE_PROBE_PATH = (
    SCRIPTS_ROOT.parents[2]
    / "skills"
    / "codex-review"
    / "scripts"
    / "codex_usage_probe.py"
)


def _probe_process(
    payload: object,
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        [sys.executable, str(USAGE_PROBE_PATH)],
        returncode,
        json.dumps(payload),
        "",
    )


def _event_stream(
    session_id: str = "thread-1",
    guidance: str = "PLAN\ninspect the change",
) -> str:
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": session_id}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": guidance,
                    },
                }
            ),
        ]
    )


def test_sol_flag_accepts_documented_truthy_values() -> None:
    assert sol_advisor.is_sol_advisor_enabled({"ADVISOR_SOL_XHIGH": "yes"})
    assert not sol_advisor.is_sol_advisor_enabled({"ADVISOR_SOL_XHIGH": "0"})


def test_resolve_usage_probe_path_uses_supplied_home_directory(tmp_path: Path) -> None:
    probe_path = sol_advisor.resolve_usage_probe_path(tmp_path)

    assert probe_path == (
        tmp_path
        / ".claude"
        / "skills"
        / "codex-review"
        / "scripts"
        / "codex_usage_probe.py"
    )


def test_argument_parser_accepts_bind_and_resume_modes() -> None:
    parser = sol_advisor.build_argument_parser()

    bind_arguments = parser.parse_args(["--bind", "--cwd", "."])
    resume_arguments = parser.parse_args(
        ["--resume", "thread-1", "--cwd", "."]
    )

    assert bind_arguments.bind
    assert bind_arguments.resume is None
    assert resume_arguments.resume == "thread-1"


def test_main_serializes_stable_result_field(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        sol_advisor,
        "run_codex_sol_advisor",
        lambda **kwargs: sol_advisor.CodexSolAdvisorReply(
            session_id="thread-1",
            guidance="PLAN\ninspect",
            successful=True,
            reason=None,
            is_fallback=False,
            signal="PLAN",
            sol_enabled=True,
            selected_tier="Sol",
            outcome="codex",
        ),
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("first consult"))

    exit_code = sol_advisor.main(["--bind", "--cwd", "."])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["result"] == "codex"
    assert "outcome" not in payload
    assert payload["sol_enabled"] is True


def test_bind_and_resume_arguments_match_installed_codex_interface() -> None:
    expected_common_arguments = [
        "codex",
        "exec",
        "--model",
        "gpt-5.6-sol",
        "--config",
        'model_reasoning_effort="xhigh"',
        "--sandbox",
        "read-only",
        "--json",
    ]
    assert sol_advisor.build_codex_arguments() == [
        *expected_common_arguments,
        "-",
    ]
    assert sol_advisor.build_codex_arguments("thread-1") == [
        *expected_common_arguments,
        "resume",
        "thread-1",
        "-",
    ]


def test_successful_probe_requires_finite_meter_above_configured_gate() -> None:
    def probe_runner(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _probe_process({"percent_left": 90})

    preflight = sol_advisor.run_sol_preflight(USAGE_PROBE_PATH, probe_runner)

    assert preflight.eligible
    assert preflight.percent_left == 90


@pytest.mark.parametrize("percent_left", [10, 10.0, 10.000])
def test_meter_at_configured_threshold_falls_back(
    percent_left: float,
) -> None:
    def probe_runner(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _probe_process({"percent_left": percent_left})

    preflight = sol_advisor.run_sol_preflight(USAGE_PROBE_PATH, probe_runner)

    assert not preflight.eligible
    assert preflight.percent_left == percent_left


@pytest.mark.parametrize(
    "payload",
    [
        {"percent_left": None},
        {"percent_left": "90"},
        {"percent_left": True},
        {"percent_left": float("nan")},
        ["percent_left", 90],
    ],
)
def test_unknown_and_malformed_meter_falls_back(payload: object) -> None:
    def probe_runner(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _probe_process(payload)

    preflight = sol_advisor.run_sol_preflight(USAGE_PROBE_PATH, probe_runner)

    assert not preflight.eligible
    assert preflight.percent_left is None


def test_malformed_probe_json_falls_back() -> None:
    def probe_runner(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(arguments, 0, "{broken", "")

    preflight = sol_advisor.run_sol_preflight(USAGE_PROBE_PATH, probe_runner)

    assert not preflight.eligible
    assert preflight.is_fallback


def test_probe_nonzero_exit_falls_back() -> None:
    def probe_runner(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _probe_process({"percent_left": 90}, returncode=2)

    preflight = sol_advisor.run_sol_preflight(USAGE_PROBE_PATH, probe_runner)

    assert not preflight.eligible
    assert preflight.is_fallback


def test_probe_timeout_falls_back() -> None:
    def probe_runner(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(arguments, 30)

    preflight = sol_advisor.run_sol_preflight(USAGE_PROBE_PATH, probe_runner)

    assert not preflight.eligible
    assert "timed out" in preflight.reason


@pytest.mark.parametrize("signal", ["ENDORSE", "CORRECTION", "PLAN", "STOP"])
def test_jsonl_parser_accepts_each_exact_guidance_signal(signal: str) -> None:
    reply = sol_advisor.parse_codex_jsonl_reply(
        _event_stream(guidance=f"{signal}\nadditional guidance"),
        existing_session_id=None,
        is_sol_enabled=True,
    )

    assert reply.successful
    assert not reply.is_fallback
    assert reply.session_id == "thread-1"
    assert reply.guidance == f"{signal}\nadditional guidance"


@pytest.mark.parametrize(
    "jsonl_text",
    [
        "{broken",
        json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
        _event_stream(session_id="", guidance="PLAN\ninspect"),
        _event_stream(guidance="ENDORSE: ready"),
        _event_stream(guidance="\n  unknown signal\nmore"),
        json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "PLAN"},
            }
        ),
    ],
)
def test_jsonl_parser_returns_typed_fallback_for_invalid_reply(
    jsonl_text: str,
) -> None:
    reply = sol_advisor.parse_codex_jsonl_reply(
        jsonl_text,
        existing_session_id=None,
        is_sol_enabled=True,
    )

    assert not reply.successful
    assert reply.is_fallback
    assert reply.session_id is None
    assert reply.guidance is None
    assert reply.reason


def test_bind_runs_probe_then_codex_with_read_only_xhigh_settings() -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def process_runner(
        arguments: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((arguments, kwargs))
        if len(calls) == 1:
            return _probe_process({"percent_left": 90})
        return subprocess.CompletedProcess(
            arguments, 0, _event_stream(guidance="PLAN\ninspect"), ""
        )

    reply = sol_advisor.run_codex_sol_advisor(
        prompt="reply only",
        working_directory=Path("."),
        preflight=None,
        probe_path=USAGE_PROBE_PATH,
        session_id=None,
        process_runner=process_runner,
        setting_by_name={"ADVISOR_SOL_XHIGH": "1"},
    )

    assert reply.successful
    assert len(calls) == 2
    assert calls[1][0] == sol_advisor.build_codex_arguments()
    assert calls[1][1]["cwd"] == "."
    assert calls[1][1]["shell"] is False
    assert calls[1][1]["timeout"]


def test_team_advisor_path_preserves_sol_routing_fields() -> None:
    team_advisor_path = SCRIPTS_ROOT.parents[2] / "skills" / "team-advisor" / "SKILL.md"
    sol_rung_path = SCRIPTS_ROOT.parent / "reference" / "sol-rung.md"
    assert "advisor-protocol.md" in team_advisor_path.read_text(encoding="utf-8")
    sol_rung = sol_rung_path.read_text(encoding="utf-8")
    assert "codex_sol_advisor.py" in sol_rung
    assert "--resume <session_id>" in sol_rung
    calls: list[list[str]] = []

    def process_runner(
        arguments: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        if len(calls) == 1:
            return _probe_process({"percent_left": 90})
        return subprocess.CompletedProcess(
            arguments, 0, _event_stream(guidance="PLAN\ninspect"), ""
        )

    reply = sol_advisor.run_codex_sol_advisor(
        prompt="first consult",
        working_directory=Path("."),
        preflight=None,
        probe_path=USAGE_PROBE_PATH,
        session_id=None,
        process_runner=process_runner,
        setting_by_name={"ADVISOR_SOL_XHIGH": "1"},
    )

    assert reply.successful
    assert reply.sol_enabled
    assert reply.selected_tier == "Sol"
    assert reply.outcome == "codex"
    assert reply.signal == "PLAN"
    assert reply.guidance == "PLAN\ninspect"


def test_team_advisor_path_uses_fable_result_when_sol_gate_is_closed() -> None:
    calls: list[list[str]] = []

    def process_runner(
        arguments: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        return _probe_process({"percent_left": 10})

    reply = sol_advisor.run_codex_sol_advisor(
        prompt="first consult",
        working_directory=Path("."),
        preflight=None,
        probe_path=USAGE_PROBE_PATH,
        session_id=None,
        process_runner=process_runner,
        setting_by_name={"ADVISOR_SOL_XHIGH": "1"},
    )

    assert not reply.successful
    assert reply.is_fallback
    assert reply.sol_enabled
    assert reply.selected_tier == "Fable"
    assert reply.outcome == "fable"
    assert len(calls) == 1


def test_disabled_flag_uses_default_optional_routing_inputs() -> None:
    reply = sol_advisor.run_codex_sol_advisor(
        prompt="first consult",
        working_directory=Path("."),
        preflight=sol_advisor.SolPreflight(
            eligible=True,
            percent_left=90,
            reason="test preflight",
            is_fallback=False,
            probe_succeeded=True,
        ),
        probe_path=None,
        setting_by_name=None,
        session_id=None,
        process_runner=subprocess.run,
    )

    assert reply.is_fallback
    assert reply.reason == "Sol advisor flag is disabled"


def test_resume_runs_the_usage_gate_before_codex() -> None:
    calls: list[list[str]] = []

    def process_runner(
        arguments: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        if len(calls) == 1:
            return _probe_process({"percent_left": 90})
        return subprocess.CompletedProcess(
            arguments, 0, _event_stream(guidance="ENDORSE\nready"), ""
        )

    reply = sol_advisor.run_codex_sol_advisor(
        prompt="resume",
        working_directory=Path("."),
        preflight=None,
        session_id="thread-1",
        probe_path=USAGE_PROBE_PATH,
        process_runner=process_runner,
        setting_by_name={"ADVISOR_SOL_XHIGH": "1"},
    )

    assert reply.successful
    assert calls == [
        [sys.executable, str(USAGE_PROBE_PATH)],
        sol_advisor.build_codex_arguments("thread-1"),
    ]


@pytest.mark.parametrize(
    "codex_failure",
    [
        "nonzero",
        "timeout",
        "malformed_jsonl",
        "missing_session",
        "missing_guidance",
        "invalid_signal",
    ],
)
def test_codex_failure_modes_always_return_fallback(
    codex_failure: str,
) -> None:
    def process_runner(
        arguments: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if len(arguments) == 2:
            return _probe_process({"percent_left": 90})
        if codex_failure == "timeout":
            raise subprocess.TimeoutExpired(arguments, 30)
        if codex_failure == "nonzero":
            return subprocess.CompletedProcess(
                arguments, 3, _event_stream(guidance="PLAN"), ""
            )
        if codex_failure == "malformed_jsonl":
            return subprocess.CompletedProcess(arguments, 0, "{broken", "")
        if codex_failure == "missing_session":
            return subprocess.CompletedProcess(
                arguments,
                0,
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": "PLAN"},
                    }
                ),
                "",
            )
        if codex_failure == "missing_guidance":
            return subprocess.CompletedProcess(
                arguments,
                0,
                json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
                "",
            )
        return subprocess.CompletedProcess(
            arguments, 0, _event_stream(guidance="PLAN: inspect"), ""
        )

    reply = sol_advisor.run_codex_sol_advisor(
        prompt="bind",
        working_directory=Path("."),
        preflight=None,
        probe_path=USAGE_PROBE_PATH,
        session_id=None,
        process_runner=process_runner,
        setting_by_name={"ADVISOR_SOL_XHIGH": "1"},
    )

    assert not reply.successful
    assert reply.is_fallback
    assert reply.session_id is None
    assert reply.guidance is None
