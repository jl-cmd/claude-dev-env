import json
import re
from pathlib import Path


SKILL_DIRECTORY = Path(__file__).parent
REFERENCE_DIRECTORY = SKILL_DIRECTORY / "reference"
SKILL_PATH = SKILL_DIRECTORY / "SKILL.md"
SCHEMA_PATH = REFERENCE_DIRECTORY / "run-record.schema.json"
REFERENCE_NAMES = (
    "packet-contract.md",
    "review-loop.md",
    "task-seeds.md",
    "final-validation-tasks.md",
    "process-inventory.md",
    "self-audit-tasks.md",
)
FORBIDDEN_ROUTE_TEXT = (
    "external planning provider",
    "Workflow dependency",
    "skill-builder",
    "--fix",
    "C:\\Users\\",
)


def read_reference_texts() -> str:
    return "\n".join(
        [SKILL_PATH.read_text(encoding="utf-8")]
        + [
            (REFERENCE_DIRECTORY / each_name).read_text(encoding="utf-8")
            for each_name in REFERENCE_NAMES
        ]
    )


def test_references_exist_and_are_linked_directly() -> None:
    skill_text = SKILL_PATH.read_text(encoding="utf-8")

    for each_name in REFERENCE_NAMES:
        assert (REFERENCE_DIRECTORY / each_name).exists()
        assert f"reference/{each_name}" in skill_text

    assert (REFERENCE_DIRECTORY / "packet-schema.json").exists()
    assert "reference/packet-schema.json" in skill_text
    assert (SKILL_DIRECTORY / "scripts" / "validate_protocol.py").exists()
    assert (SKILL_DIRECTORY / "scripts" / "validate_run.py").exists()


def test_packet_schema_requires_native_planning_fields() -> None:
    packet_schema = json.loads(
        (REFERENCE_DIRECTORY / "packet-schema.json").read_text(encoding="utf-8")
    )

    assert {
        "schema_version",
        "slug",
        "status",
        "request",
        "allowed_files",
        "sources",
        "decisions",
        "open_questions",
        "tasks",
        "validation",
    } <= set(packet_schema["required"])
    assert packet_schema["properties"]["status"]["enum"] == ["draft", "approved"]
    assert packet_schema["$defs"]["validation"]["properties"]["validated_by"] == {
        "const": "native-plan-to-pr"
    }


def test_run_record_schema_requires_task_and_review_records() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    required_fields = set(schema["required"])

    assert {
        "task_identity",
        "commit",
        "review_record",
        "repair_record",
        "reverification_record",
        "verification_record",
    } <= required_fields
    review_fields = set(schema["$defs"]["review_record"]["required"])
    assert {"findings_only", "has_repair_flag", "command"} <= review_fields
    assert schema["$defs"]["review_record"]["properties"]["command"] == {
        "type": "string",
        "minLength": 1,
    }


def test_review_loop_requires_separate_native_review_and_repair() -> None:
    contract_text = read_reference_texts()

    assert "separate fast low-effort Luna review worker" in contract_text
    assert "native findings-only" in contract_text
    assert "/e-code-review low" in contract_text
    assert "correctness" in contract_text
    assert "/e-code-review low" in contract_text
    assert "has no repair flag" in contract_text
    assert "separate fast low-effort Luna repair worker" in contract_text
    assert "confirmed findings" in contract_text
    assert "Amend the task commit" in contract_text
    assert "repeat the native review until clean" in contract_text
    assert "packet is complete before `TaskCreate` or `TodoWrite` runs" in contract_text


def test_post_pr_cleanup_and_max_review_are_distinct() -> None:
    contract_text = read_reference_texts()

    assert "Luna xhigh `/e-simplify`" in contract_text
    assert "cleanup-only" in contract_text
    assert "Luna low `/e-code-review max loop`" in contract_text
    assert "separate Luna low repair worker" in contract_text
    assert "commits, and pushes" in contract_text
    assert "clean" in contract_text
    assert "skill-builder" not in contract_text


def test_packet_planning_precedes_task_seeding_and_has_no_external_dependency() -> None:
    contract_text = read_reference_texts()

    assert "before any `TaskCreate` or `TodoWrite` seeding" in contract_text
    assert (
        "Only a passing packet with `status: approved` may seed host tasks"
        in contract_text
    )
    assert "external planning provider" not in contract_text
    assert "Workflow dependency" not in contract_text


def test_task_seeding_and_audit_inventories_are_present() -> None:
    contract_text = read_reference_texts()

    assert "TaskCreate" in contract_text
    assert "TodoWrite" in contract_text
    assert "deterministic" in contract_text
    assert "judgment" in contract_text
    assert "borderline" in contract_text
    assert "final-validation" in contract_text
    assert "self-audit" in contract_text
    assert re.search(r"\n1\. .*\n2\. .*\n3\. ", contract_text)


def test_contract_avoids_forbidden_route_strings_and_absolute_paths() -> None:
    contract_text = read_reference_texts()

    for each_forbidden_route_text in FORBIDDEN_ROUTE_TEXT:
        assert each_forbidden_route_text not in contract_text
    assert not re.search(r"[A-Za-z]:[/\\]", contract_text)
