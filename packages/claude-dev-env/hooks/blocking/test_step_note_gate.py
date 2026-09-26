import io
import json
import threading
from pathlib import Path

import pytest

import step_note_gate

PROMPT_ENTRY = {"type": "user", "message": {"role": "user", "content": "List the folder."}}


def assistant_entry(message_id, block):
    return {
        "type": "assistant",
        "message": {"id": message_id, "role": "assistant", "content": [block]},
    }


def note_entry(message_id, text):
    return assistant_entry(message_id, {"type": "text", "text": text})


def call_entry(message_id, tool_use_id):
    return assistant_entry(
        message_id,
        {"type": "tool_use", "id": tool_use_id, "name": "Bash", "input": {"command": "echo one"}},
    )


def result_entry(tool_use_id):
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": "one"}],
        },
    }


def write_transcript(path, all_entries):
    path.write_text("".join(json.dumps(each) + "\n" for each in all_entries), encoding="utf-8")


def run_gate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    transcript_path: Path,
    tool_use_id: str,
    **extra_input: str,
) -> tuple[int, str]:
    hook_input = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_use_id": tool_use_id,
        "transcript_path": str(transcript_path),
        **extra_input,
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
    exit_code = step_note_gate.main()
    return exit_code, capsys.readouterr().err


@pytest.fixture(autouse=True)
def isolated_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(step_note_gate, "POLL_LIMIT_SECONDS", 0.3)
    on_flag_path = tmp_path / ".step-notes-on"
    on_flag_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(step_note_gate, "STEP_NOTES_ON_FLAG_PATH", on_flag_path)


def test_should_allow_a_call_that_follows_a_note_in_its_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(
        transcript,
        [PROMPT_ENTRY, note_entry("m1", "Listing the folder."), call_entry("m1", "call_1")],
    )

    exit_code, stderr_text = run_gate(monkeypatch, capsys, transcript, "call_1")

    assert (exit_code, stderr_text) == (0, "")


def test_should_block_a_call_with_no_note_after_the_previous_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(
        transcript,
        [
            PROMPT_ENTRY,
            note_entry("m1", "Listing the folder."),
            call_entry("m1", "call_1"),
            result_entry("call_1"),
            call_entry("m2", "call_2"),
        ],
    )

    exit_code, stderr_text = run_gate(monkeypatch, capsys, transcript, "call_2")

    assert exit_code == 2
    assert stderr_text == step_note_gate.BLOCK_MESSAGE


def test_should_allow_a_bare_call_while_the_on_flag_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(transcript, [PROMPT_ENTRY, call_entry("m1", "call_1")])
    step_note_gate.STEP_NOTES_ON_FLAG_PATH.unlink()

    exit_code, _ = run_gate(monkeypatch, capsys, transcript, "call_1")

    assert exit_code == 0


def test_should_block_the_first_call_after_a_prompt_when_no_note_precedes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(transcript, [PROMPT_ENTRY, call_entry("m1", "call_1")])

    exit_code, _ = run_gate(monkeypatch, capsys, transcript, "call_1")

    assert exit_code == 2


def test_should_block_when_the_only_text_is_blank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(
        transcript, [PROMPT_ENTRY, note_entry("m1", "  \n "), call_entry("m1", "call_1")]
    )

    exit_code, _ = run_gate(monkeypatch, capsys, transcript, "call_1")

    assert exit_code == 2


def test_should_allow_every_parallel_call_under_one_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(
        transcript,
        [
            PROMPT_ENTRY,
            note_entry("m1", "Running two echoes together."),
            call_entry("m1", "call_1"),
            call_entry("m1", "call_2"),
        ],
    )

    first_exit_code, _ = run_gate(monkeypatch, capsys, transcript, "call_1")
    second_exit_code, _ = run_gate(monkeypatch, capsys, transcript, "call_2")

    assert (first_exit_code, second_exit_code) == (0, 0)


def test_should_see_a_note_the_harness_writes_after_the_hook_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(transcript, [PROMPT_ENTRY])
    late_lines = "".join(
        json.dumps(each) + "\n"
        for each in (note_entry("m1", "Listing the folder."), call_entry("m1", "call_1"))
    )

    def append_late_lines():
        with transcript.open("a", encoding="utf-8") as transcript_file:
            transcript_file.write(late_lines)

    writer = threading.Timer(0.15, append_late_lines)
    writer.start()
    exit_code, _ = run_gate(monkeypatch, capsys, transcript, "call_1")
    writer.join()

    assert exit_code == 0


def test_should_block_a_bare_call_the_harness_writes_after_the_hook_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(transcript, [PROMPT_ENTRY])

    def append_late_call():
        with transcript.open("a", encoding="utf-8") as transcript_file:
            transcript_file.write(json.dumps(call_entry("m1", "call_1")) + "\n")

    writer = threading.Timer(0.15, append_late_call)
    writer.start()
    exit_code, _ = run_gate(monkeypatch, capsys, transcript, "call_1")
    writer.join()

    assert exit_code == 2


def test_should_allow_a_call_that_never_reaches_the_transcript(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(transcript, [PROMPT_ENTRY])

    exit_code, _ = run_gate(monkeypatch, capsys, transcript, "call_1")

    assert exit_code == 0


def test_should_allow_a_subagent_call_even_without_a_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(transcript, [PROMPT_ENTRY, call_entry("m1", "call_1")])

    exit_code, _ = run_gate(
        monkeypatch, capsys, transcript, "call_1", agent_id="a1", agent_type="general-purpose"
    )

    assert exit_code == 0


def test_should_allow_a_call_whose_message_outgrows_the_tail_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(
        transcript,
        [
            PROMPT_ENTRY,
            call_entry("m1", "call_0"),
            result_entry("call_0"),
            call_entry("m2", "call_1"),
        ],
    )
    call_line_bytes = len(json.dumps(call_entry("m2", "call_1")).encode("utf-8")) + 1
    monkeypatch.setattr(step_note_gate, "TAIL_WINDOW_BYTES", call_line_bytes + 10)

    exit_code, _ = run_gate(monkeypatch, capsys, transcript, "call_1")

    assert exit_code == 0
