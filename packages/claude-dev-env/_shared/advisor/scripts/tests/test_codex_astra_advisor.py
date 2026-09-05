"""Behavioral tests for the executable Codex Astra advisor path."""
import io
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
import pytest

_ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]


def _load_astra_module() -> ModuleType:
    scripts_root = Path(__file__).parent.parent
    config_root = str(scripts_root / "config")
    if config_root not in sys.path:
        sys.path.insert(0, config_root)
    specification = importlib.util.spec_from_file_location(
        "codex_astra_advisor", scripts_root / "codex_astra_advisor.py"
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


astra_advisor = _load_astra_module()
SCRIPTS_ROOT = Path(__file__).parent.parent
USAGE_PROBE_PATH = (
    SCRIPTS_ROOT.parents[1] / "pr-loop" / "scripts" / "codex_usage_probe.py"
)
ENABLED_SETTINGS = {astra_advisor.ASTRA_ENV_VAR: "1"}


@pytest.fixture(autouse=True)
def _codex_on_search_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(astra_advisor.shutil, "which", lambda name: "codex")


def _probe(payload: object, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        [sys.executable, str(USAGE_PROBE_PATH)],
        returncode,
        json.dumps(payload),
        "",
    )


def _events(session_id: str = "thread-1", guidance: str = "PLAN\ninspect") -> str:
    return "\n".join(
        (
            json.dumps({"type": "thread.started", "thread_id": session_id}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": guidance},
                }
            ),
        )
    )


def _two_step_runner(
    all_calls: list[list[str]], guidance: str = "PLAN\ninspect"
) -> _ProcessRunner:
    def runner(
        arguments: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        all_calls.append(arguments)
        if len(all_calls) == 1:
            return _probe({"percent_left": 90})
        return subprocess.CompletedProcess(arguments, 0, _events(guidance=guidance), "")
    return runner


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "on", " On "])
def test_astra_flag_accepts_documented_truthy_values(truthy: str) -> None:
    assert astra_advisor.is_astra_advisor_enabled({"ADVISOR_ASTRA": truthy})


def test_astra_flag_rejects_legacy_sol_setting() -> None:
    assert not astra_advisor.is_astra_advisor_enabled({"ADVISOR_SOL": "1"})


def test_resolve_advisor_effort_uses_shared_setting_and_default() -> None:
    assert astra_advisor.resolve_advisor_effort({"ADVISOR_EFFORT": "HIGH"}) == "high"
    assert astra_advisor.resolve_advisor_effort({"ADVISOR_EFFORT": "unknown"}) == "low"


def test_resolve_codex_executable_prefers_override_and_falls_back_to_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert astra_advisor.resolve_codex_executable(
        {astra_advisor.ADVISOR_CODEX_EXECUTABLE_ENV_VAR: "/tmp/codex-custom"}
    ) == "/tmp/codex-custom"
    monkeypatch.setattr(astra_advisor.shutil, "which", lambda name: "/usr/bin/codex")
    assert astra_advisor.resolve_codex_executable({}) == "/usr/bin/codex"


@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max"])
def test_codex_arguments_apply_selected_effort(effort: str) -> None:
    arguments = astra_advisor.build_codex_arguments("codex", reasoning_effort=effort)
    config_index = arguments.index("--config")
    assert arguments[config_index + 1] == f'model_reasoning_effort="{effort}"'


def test_codex_arguments_use_astra_and_read_only_sandbox() -> None:
    arguments = astra_advisor.build_codex_arguments("codex", session_id="thread-1")
    assert arguments[:4] == ["codex", "exec", "--model", "gpt-6-astra"]
    assert ["--sandbox", "read-only"] == arguments[6:8]
    assert arguments[-3:] == ["resume", "thread-1", "-"]


def test_argument_parser_accepts_astra_and_rejects_sol() -> None:
    parser = astra_advisor.build_argument_parser()
    parsed = parser.parse_args(["--bind", "--cwd", ".", "--enable-astra"])
    assert parsed.is_astra_requested
    with pytest.raises(SystemExit):
        parser.parse_args(["--bind", "--cwd", ".", "--enable-sol"])


def test_usage_probe_path_uses_supplied_home(tmp_path: Path) -> None:
    path = astra_advisor.resolve_usage_probe_path(tmp_path)
    assert path == tmp_path / ".claude" / "_shared" / "pr-loop" / "scripts" / "codex_usage_probe.py"


def test_preflight_accepts_meter_above_gate() -> None:
    preflight = astra_advisor.run_astra_preflight(
        USAGE_PROBE_PATH, lambda arguments, **kwargs: _probe({"percent_left": 90})
    )
    assert preflight.eligible
    assert preflight.percent_left == 90


def test_preflight_declines_meter_at_gate() -> None:
    preflight = astra_advisor.run_astra_preflight(
        USAGE_PROBE_PATH, lambda arguments, **kwargs: _probe({"percent_left": 10})
    )
    assert not preflight.eligible
    assert preflight.fallback_kind == astra_advisor.ASTRA_FALLBACK_KIND_DECLINED


@pytest.mark.parametrize("payload", [{"percent_left": None}, {"percent_left": "90"}, ["bad"]])
def test_preflight_rejects_malformed_meter(payload: object) -> None:
    preflight = astra_advisor.run_astra_preflight(
        USAGE_PROBE_PATH, lambda arguments, **kwargs: _probe(payload)
    )
    assert not preflight.eligible
    assert preflight.fallback_kind == astra_advisor.ASTRA_FALLBACK_KIND_BROKEN


@pytest.mark.parametrize("signal", ["ENDORSE", "CORRECTION", "PLAN", "STOP"])
def test_jsonl_parser_accepts_guidance_signals(signal: str) -> None:
    reply = astra_advisor.parse_codex_jsonl_reply(
        _events(guidance=f"{signal}\nmore"), None, True
    )
    assert reply.successful
    assert reply.signal == signal


@pytest.mark.parametrize(
    "jsonl_text",
    [
        "{broken",
        json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
        _events(guidance="PLAN: inspect"),
    ],
)
def test_jsonl_parser_falls_back_for_invalid_reply(jsonl_text: str) -> None:
    reply = astra_advisor.parse_codex_jsonl_reply(jsonl_text, None, True)
    assert reply.is_fallback
    assert not reply.successful


def test_bind_runs_probe_then_codex() -> None:
    calls: list[list[str]] = []
    reply = astra_advisor.run_codex_astra_advisor(
        "consult",
        Path("."),
        None,
        USAGE_PROBE_PATH,
        ENABLED_SETTINGS,
        None,
        _two_step_runner(calls),
    )
    assert reply.successful
    assert calls[1] == astra_advisor.build_codex_arguments("codex")


def test_disabled_flag_returns_declined_fallback() -> None:
    reply = astra_advisor.run_codex_astra_advisor(
        "consult",
        Path("."),
        astra_advisor.AstraPreflight(True, 90, "ok"),
        None,
        {},
        None,
        subprocess.run,
    )
    assert reply.is_fallback
    assert reply.fallback_kind == astra_advisor.ASTRA_FALLBACK_KIND_DECLINED


def test_missing_codex_returns_broken_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(astra_advisor.shutil, "which", lambda name: None)
    reply = astra_advisor.run_codex_astra_advisor(
        "consult", Path("."), None, USAGE_PROBE_PATH, ENABLED_SETTINGS, None, subprocess.run
    )
    assert reply.is_fallback
    assert reply.fallback_kind == astra_advisor.ASTRA_FALLBACK_KIND_BROKEN


def test_resume_uses_existing_session() -> None:
    calls: list[list[str]] = []
    reply = astra_advisor.run_codex_astra_advisor(
        "resume",
        Path("."),
        None,
        USAGE_PROBE_PATH,
        ENABLED_SETTINGS,
        "thread-1",
        _two_step_runner(calls, "ENDORSE\nready"),
    )
    assert reply.successful
    assert calls[1][-3:] == ["resume", "thread-1", "-"]


def test_main_serializes_result_and_astra_fields(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        astra_advisor,
        "run_codex_astra_advisor",
        lambda *args, **kwargs: astra_advisor.CodexAstraAdvisorReply(
            "thread-1", "PLAN\ninspect", True, None, False, "PLAN", True, "Astra", "codex", None
        ),
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("consult"))
    assert astra_advisor.main(["--bind", "--cwd", "."]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "codex"
    assert payload["astra_enabled"] is True
    assert "sol_enabled" not in payload


def test_active_docs_use_astra_names() -> None:
    package_root = SCRIPTS_ROOT.parents[2]
    advisor_root = SCRIPTS_ROOT.parent
    all_paths = [
        advisor_root / "advisor-protocol.md",
        *sorted((advisor_root / "reference").glob("*.md")),
        package_root / ".agents" / "skills" / "team-advisor" / "SKILL.md",
        package_root / "docs" / "references" / "team-advisor-skill.md",
    ]
    legacy_names = ("ADVISOR_SOL", "--enable-sol", "codex_sol_advisor", "sol-rung.md")
    for each_path in all_paths:
        content = each_path.read_text(encoding="utf-8")
        assert all(name not in content for name in legacy_names)


def test_astra_docs_name_shared_effort_and_helper() -> None:
    advisor_root = SCRIPTS_ROOT.parent
    rung = (advisor_root / "reference" / "astra-rung.md").read_text(encoding="utf-8")
    protocol = (advisor_root / "advisor-protocol.md").read_text(encoding="utf-8")
    assert "ADVISOR_EFFORT" in rung
    assert "ADVISOR_ASTRA=1" in protocol
    assert "codex_astra_advisor.py" in rung
    assert "--resume <session_id>" in rung
