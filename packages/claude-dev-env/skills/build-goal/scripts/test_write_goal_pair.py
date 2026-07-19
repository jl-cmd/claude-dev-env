"""Behavioral tests for write_goal_pair against real files and real templates."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from build_goal_constants import write_goal_pair_constants as goal_constants

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

SCRIPT_PATH = SCRIPTS_DIRECTORY / "write_goal_pair.py"

MINIMAL_PACKET: dict[str, object] = {
    "objective": "Ship the build-goal skill.",
    "done_when": ["python -m pytest packages/claude-dev-env passes"],
}

FULL_PACKET: dict[str, object] = {
    "objective": "Ship the build-goal skill.",
    "done_when": [
        "python -m pytest packages/claude-dev-env passes",
        "SKILL.md reviewed",
    ],
    "in_scope": ["write the CLI script", "write the templates"],
    "out_of_scope": ["implementing the goal's own work"],
    "tasks": [
        {"id": "task-1", "status": "completed", "subject": "Write constants module"},
        {"id": "task-2", "status": "in_progress", "subject": "Write the CLI script"},
        {"id": "task-3", "status": "pending", "subject": "Write SKILL.md"},
    ],
    "context": {
        "repo": "claude-dev-env",
        "branch": "build-goal-skill",
        "pr": None,
        "paths": ["packages/claude-dev-env/skills/build-goal/"],
        "constraints": ["main ancestor required"],
    },
    "execution_notes": ["session is orchestrator"],
}


def load_write_goal_pair_module() -> ModuleType:
    module_name = "write_goal_pair_under_test"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    loaded_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = loaded_module
    spec.loader.exec_module(loaded_module)
    return loaded_module


def write_packet_file(tmp_path: Path, packet: dict[str, object]) -> Path:
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    return packet_path


class TestLoadGoalPacket:
    def should_decode_a_valid_packet_file(self, tmp_path: Path) -> None:
        module = load_write_goal_pair_module()
        packet_path = write_packet_file(tmp_path, MINIMAL_PACKET)
        assert module.load_goal_packet(packet_path) == MINIMAL_PACKET

    def should_raise_when_file_is_missing(self, tmp_path: Path) -> None:
        module = load_write_goal_pair_module()
        with pytest.raises(module.GoalPacketError):
            module.load_goal_packet(tmp_path / "missing.json")

    def should_raise_when_json_is_invalid(self, tmp_path: Path) -> None:
        module = load_write_goal_pair_module()
        packet_path = tmp_path / "packet.json"
        packet_path.write_text("{not json", encoding="utf-8")
        with pytest.raises(module.GoalPacketError):
            module.load_goal_packet(packet_path)

    def should_raise_when_root_is_not_an_object(self, tmp_path: Path) -> None:
        module = load_write_goal_pair_module()
        packet_path = tmp_path / "packet.json"
        packet_path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(module.GoalPacketError):
            module.load_goal_packet(packet_path)


class TestValidateGoalPacket:
    def should_raise_when_objective_missing(self) -> None:
        module = load_write_goal_pair_module()
        with pytest.raises(module.GoalPacketError, match="objective"):
            module.validate_goal_packet({"done_when": ["x"]})

    def should_raise_when_objective_empty(self) -> None:
        module = load_write_goal_pair_module()
        with pytest.raises(module.GoalPacketError, match="objective"):
            module.validate_goal_packet({"objective": "   ", "done_when": ["x"]})

    def should_raise_when_done_when_missing(self) -> None:
        module = load_write_goal_pair_module()
        with pytest.raises(module.GoalPacketError, match="done_when"):
            module.validate_goal_packet({"objective": "Ship it"})

    def should_raise_when_done_when_empty(self) -> None:
        module = load_write_goal_pair_module()
        with pytest.raises(module.GoalPacketError, match="done_when"):
            module.validate_goal_packet({"objective": "Ship it", "done_when": []})

    def should_raise_when_done_when_entry_is_not_a_string(self) -> None:
        module = load_write_goal_pair_module()
        with pytest.raises(module.GoalPacketError):
            module.validate_goal_packet({"objective": "Ship it", "done_when": [1]})

    def should_default_optional_fields_to_empty(self) -> None:
        module = load_write_goal_pair_module()
        packet = module.validate_goal_packet(MINIMAL_PACKET)
        assert packet.in_scope == ()
        assert packet.out_of_scope == ()
        assert packet.tasks == ()
        assert packet.execution_notes == ()
        assert packet.context == {}

    def should_normalize_a_full_packet(self) -> None:
        module = load_write_goal_pair_module()
        packet = module.validate_goal_packet(FULL_PACKET)
        assert packet.objective == FULL_PACKET["objective"]
        assert packet.tasks[0]["id"] == "task-1"
        assert packet.tasks[0]["status"] == "completed"
        assert packet.context["repo"] == "claude-dev-env"
        assert packet.context["paths"] == (
            "packages/claude-dev-env/skills/build-goal/",
        )
        assert packet.context["constraints"] == ("main ancestor required",)
        assert "pr" not in packet.context

    def should_raise_when_a_task_entry_is_missing_fields(self) -> None:
        module = load_write_goal_pair_module()
        packet = {"objective": "Ship it", "done_when": ["x"], "tasks": [{"id": "1"}]}
        with pytest.raises(module.GoalPacketError):
            module.validate_goal_packet(packet)

    def should_raise_when_a_task_status_is_invalid(self) -> None:
        module = load_write_goal_pair_module()
        packet = {
            "objective": "Ship it",
            "done_when": ["x"],
            "tasks": [{"id": "1", "status": "done", "subject": "x"}],
        }
        with pytest.raises(module.GoalPacketError, match="status"):
            module.validate_goal_packet(packet)

    def should_raise_when_context_paths_is_not_a_list(self) -> None:
        module = load_write_goal_pair_module()
        packet = {
            "objective": "Ship it",
            "done_when": ["x"],
            "context": {"paths": "nope"},
        }
        with pytest.raises(module.GoalPacketError, match="paths"):
            module.validate_goal_packet(packet)

    def should_raise_when_context_scalar_field_is_empty(self) -> None:
        module = load_write_goal_pair_module()
        packet = {"objective": "Ship it", "done_when": ["x"], "context": {"repo": "  "}}
        with pytest.raises(module.GoalPacketError):
            module.validate_goal_packet(packet)


class TestRenderBulletLines:
    def should_render_one_bullet_per_entry(self) -> None:
        module = load_write_goal_pair_module()
        assert module.render_bullet_lines(["a", "b"]) == "- a\n- b"

    def should_render_empty_string_for_no_entries(self) -> None:
        module = load_write_goal_pair_module()
        assert module.render_bullet_lines([]) == ""


class TestRenderNumberedTableRows:
    def should_number_rows_starting_at_one(self) -> None:
        module = load_write_goal_pair_module()
        assert module.render_numbered_table_rows(["a", "b"]) == "| 1 | a |\n| 2 | b |"


class TestRenderTaskRows:
    def should_render_checked_and_unchecked_marks(self) -> None:
        module = load_write_goal_pair_module()
        tasks = [
            {"id": "1", "status": "completed", "subject": "done thing"},
            {"id": "2", "status": "pending", "subject": "todo thing"},
        ]
        table = module.render_task_table_rows(tasks)
        assert "| [x] | 1 | done thing |" in table
        assert "| [ ] | 2 | todo thing |" in table
        bullets = module.render_task_bullet_lines(tasks)
        assert "- [x] 1: done thing" in bullets
        assert "- [ ] 2: todo thing" in bullets


class TestRenderContextBulletLines:
    def should_render_only_present_facts(self) -> None:
        module = load_write_goal_pair_module()
        context = module.validate_goal_packet(FULL_PACKET).context
        rendered = module.render_context_bullet_lines(context)
        assert "repo: claude-dev-env" in rendered
        assert "branch: build-goal-skill" in rendered
        assert "PR:" not in rendered
        assert "main ancestor required" in rendered

    def should_omit_constraints_when_not_included(self) -> None:
        module = load_write_goal_pair_module()
        context = module.validate_goal_packet(FULL_PACKET).context
        context_without_constraints = module._context_without_constraints(context)
        rendered = module.render_context_bullet_lines(context_without_constraints)
        assert "repo: claude-dev-env" in rendered
        assert "main ancestor required" not in rendered

    def should_render_empty_string_for_no_facts(self) -> None:
        module = load_write_goal_pair_module()
        assert module.render_context_bullet_lines({}) == ""


class TestRenderDocuments:
    def should_render_goal_cmd_document_from_the_real_template(self) -> None:
        module = load_write_goal_pair_module()
        packet = module.validate_goal_packet(FULL_PACKET)
        document = module.render_goal_cmd_document(packet)
        assert document.startswith("GOAL: Ship the build-goal skill.")
        assert "DONE WHEN:" in document
        assert "- [x] task-1: Write constants module" in document
        assert "\n\n\n" not in document

    def should_render_goal_cmd_document_with_no_placeholder_sentence(self) -> None:
        module = load_write_goal_pair_module()
        packet = module.validate_goal_packet(MINIMAL_PACKET)
        document = module.render_goal_cmd_document(packet)
        assert "OUT OF SCOPE:\n\nTASKS" in document

    def should_render_human_brief_document_from_the_real_template(self) -> None:
        module = load_write_goal_pair_module()
        packet = module.validate_goal_packet(FULL_PACKET)
        document = module.render_human_brief_document(packet)
        assert "# Goal Brief" in document
        assert "| [x] | task-1 | Write constants module |" in document
        assert "| 1 | main ancestor required |" in document

    def should_render_each_human_brief_constraint_exactly_once(self) -> None:
        module = load_write_goal_pair_module()
        packet = module.validate_goal_packet(FULL_PACKET)
        document = module.render_human_brief_document(packet)
        assert document.count("main ancestor required") == 1

    def should_fold_constraints_into_goal_cmd_context(self) -> None:
        module = load_write_goal_pair_module()
        packet = module.validate_goal_packet(FULL_PACKET)
        document = module.render_goal_cmd_document(packet)
        assert "main ancestor required" in document


class TestParseArguments:
    def should_parse_the_packet_path_argument(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_write_goal_pair_module()
        packet_path = tmp_path / "packet.json"
        monkeypatch.setattr(sys, "argv", ["write_goal_pair.py", str(packet_path)])
        parsed_arguments = module.parse_arguments()
        assert parsed_arguments.packet_path == packet_path

    def should_raise_goal_packet_error_when_argument_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_write_goal_pair_module()
        monkeypatch.setattr(sys, "argv", ["write_goal_pair.py"])
        with pytest.raises(module.GoalPacketError):
            module.parse_arguments()


class TestWriteGoalPair:
    def should_write_both_files_atomically_under_the_temp_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_write_goal_pair_module()
        monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(tmp_path))
        packet_path = write_packet_file(tmp_path, FULL_PACKET)
        goal_cmd_path, human_brief_path = module.write_goal_pair(packet_path)
        assert goal_cmd_path.is_file()
        assert human_brief_path.is_file()
        assert goal_cmd_path.parent == human_brief_path.parent
        run_directory = goal_cmd_path.parent
        assert (
            run_directory.parent
            == tmp_path / goal_constants.TEMP_ROOT_SUBDIRECTORY_NAME
        )
        assert goal_cmd_path.name == goal_constants.GOAL_CMD_OUTPUT_FILENAME
        assert human_brief_path.name == goal_constants.HUMAN_BRIEF_OUTPUT_FILENAME
        assert not any(run_directory.glob("*.tmp"))
        assert "GOAL: Ship the build-goal skill." in goal_cmd_path.read_text(
            encoding="utf-8"
        )
        assert "# Goal Brief" in human_brief_path.read_text(encoding="utf-8")

    def should_allocate_a_fresh_run_directory_per_call(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_write_goal_pair_module()
        monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(tmp_path))
        packet_path = write_packet_file(tmp_path, MINIMAL_PACKET)
        first_goal_cmd_path, _ = module.write_goal_pair(packet_path)
        second_goal_cmd_path, _ = module.write_goal_pair(packet_path)
        assert first_goal_cmd_path.parent != second_goal_cmd_path.parent


class TestMainCli:
    def should_print_both_paths_and_exit_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        module = load_write_goal_pair_module()
        monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(tmp_path))
        packet_path = write_packet_file(tmp_path, FULL_PACKET)
        monkeypatch.setattr(sys, "argv", ["write_goal_pair.py", str(packet_path)])
        exit_code = module.main()
        captured = capsys.readouterr()
        assert exit_code == goal_constants.EXIT_CODE_SUCCESS
        all_lines = captured.out.splitlines()
        assert len(all_lines) == 2
        assert all_lines[0].startswith(goal_constants.STDOUT_GOAL_CMD_PATH_PREFIX)
        assert all_lines[1].startswith(goal_constants.STDOUT_HUMAN_BRIEF_PATH_PREFIX)

    def should_exit_two_and_name_the_missing_field(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        module = load_write_goal_pair_module()
        packet_path = write_packet_file(tmp_path, {"objective": "Ship it"})
        monkeypatch.setattr(sys, "argv", ["write_goal_pair.py", str(packet_path)])
        exit_code = module.main()
        captured = capsys.readouterr()
        assert exit_code == goal_constants.EXIT_CODE_INVALID_PACKET
        assert captured.out == ""
        assert "done_when" in captured.err
        assert "Traceback" not in captured.err

    def should_exit_two_for_an_empty_objective(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        module = load_write_goal_pair_module()
        packet_path = write_packet_file(
            tmp_path, {"objective": "  ", "done_when": ["x"]}
        )
        monkeypatch.setattr(sys, "argv", ["write_goal_pair.py", str(packet_path)])
        exit_code = module.main()
        captured = capsys.readouterr()
        assert exit_code == goal_constants.EXIT_CODE_INVALID_PACKET
        assert "objective" in captured.err


class TestSubprocessCli:
    def should_run_as_a_subprocess_and_print_both_paths(self, tmp_path: Path) -> None:
        packet_path = write_packet_file(tmp_path, MINIMAL_PACKET)
        environment = dict(os.environ)
        environment["TMPDIR"] = str(tmp_path)
        environment["TEMP"] = str(tmp_path)
        environment["TMP"] = str(tmp_path)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(packet_path)],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        assert completed.returncode == goal_constants.EXIT_CODE_SUCCESS
        all_lines = completed.stdout.splitlines()
        assert len(all_lines) == 2
