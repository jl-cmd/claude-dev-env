import re
from pathlib import Path


SKILL_DIRECTORY = Path(__file__).parent
SKILL_PATH = SKILL_DIRECTORY / "SKILL.md"
MODEL_ROUTING_PATH = SKILL_DIRECTORY / "reference" / "model-routing.md"
TASK_TICKET_PATH = SKILL_DIRECTORY / "reference" / "task-ticket.md"
PACKET_CONTRACT_PATH = SKILL_DIRECTORY / "reference" / "packet-contract.md"
PACKET_SCHEMA_PATH = SKILL_DIRECTORY / "reference" / "packet-schema.json"
VALIDATION_SCRIPT_PATH = SKILL_DIRECTORY / "scripts" / "validate_protocol.py"
RUN_VALIDATION_SCRIPT_PATH = SKILL_DIRECTORY / "scripts" / "validate_run.py"
PACKET_CREATOR_PATH = SKILL_DIRECTORY / "scripts" / "create_packet.py"
PACKET_VALIDATOR_PATH = SKILL_DIRECTORY / "scripts" / "validate_packet.py"
FORBIDDEN_ROUTE_TEXT = ("external planning provider", "Workflow dependency")
EXPECTED_TASK_PROTOCOL_HEADING = "## One-task and one-commit protocol"


def read_skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def read_reference_texts() -> tuple[str, str, str]:
    return (
        MODEL_ROUTING_PATH.read_text(encoding="utf-8"),
        TASK_TICKET_PATH.read_text(encoding="utf-8"),
        PACKET_CONTRACT_PATH.read_text(encoding="utf-8"),
    )


def test_skill_frontmatter_defines_third_person_trigger_catalog() -> None:
    skill_text = read_skill_text()

    assert skill_text.startswith("---\nname: plan-to-pr\n")
    description_text = skill_text.split("description:", 1)[1].split("---", 1)[0]
    assert "Triggers:" in description_text
    assert "Coordinates" in description_text
    assert not re.search(r"\b(I|[Ww]e|[Oo]ur|[Mm]y)\b", description_text)


def test_skill_contract_names_capability_boundary_and_refusals() -> None:
    skill_text = read_skill_text()

    assert "## Capability boundary" in skill_text
    assert "## Refusal cases" in skill_text
    assert "one deliverable" in skill_text
    assert "one allowed file set" in skill_text
    assert "one acceptance check" in skill_text
    assert "one commit" in skill_text
    assert "fail closed" in skill_text
    assert "Plan-to-PR blocked: <missing input or capability>." in skill_text


def test_skill_contract_requires_native_packet_planning_before_task_seeding() -> None:
    skill_text = read_skill_text()

    assert "## Native planning phase" in skill_text
    assert "before task seeding and before implementation" in skill_text
    assert "Luna xhigh planner" in skill_text
    assert "Sol xhigh advisor" in skill_text
    assert "native planning packet" in skill_text
    assert (
        "Only a passing packet with `status: approved` may seed host tasks"
        in skill_text
    )
    assert skill_text.index("## Native planning phase") < skill_text.index(
        "## Runtime and task seeding"
    )
    assert "anthropic-plan" not in skill_text
    assert "Workflow" not in skill_text


def test_skill_contract_pins_model_roles_and_worker_routing() -> None:
    skill_text = read_skill_text()

    assert "planner and final validator use Luna xhigh" in skill_text
    assert "orchestrator uses the max route" in skill_text
    assert "Sol xhigh advisor" in skill_text
    assert "Sol xhigh advisor heavily at scope" in skill_text
    assert (
        "Every implementation,\nreview, and repair worker uses fast, low-effort Luna"
        in skill_text
    )
    assert "separate fast low-effort Luna review worker" in skill_text
    assert "separate fast low-effort Luna repair worker" in skill_text
    assert "Unavailable models or routing tools\nfail closed" in skill_text


def test_skill_contract_enforces_task_commit_and_review_order() -> None:
    skill_text = read_skill_text()

    assert EXPECTED_TASK_PROTOCOL_HEADING in skill_text
    assert "fresh verification and `verified_commit_gate`" in skill_text
    assert (
        "native\nfindings-only correctness review at `/e-code-review low`" in skill_text
    )
    assert "findings-only" in skill_text
    assert "has no repair" in skill_text
    assert "separate fast low-effort Luna repair worker" in skill_text
    assert "Rerun the task acceptance check and fresh" in skill_text
    assert "exact-surface verification" in skill_text
    assert "amend the task commit" in skill_text.lower()
    assert (
        "Record resolved model, effort, command, findings, repair status, and"
        in skill_text
    )
    assert "surface" in skill_text
    assert "repeat native review" in skill_text
    assert "until clean" in skill_text
    assert "maps every commit to one packet task" in skill_text


def test_skill_contract_uses_only_the_native_review_route() -> None:
    all_contract_text = "\n".join((read_skill_text(), *read_reference_texts()))

    assert "/e-code-review low" in all_contract_text
    assert "findings only" in all_contract_text
    assert "no repair flag" in all_contract_text
    assert "separate fast low-effort Luna" in all_contract_text
    assert "fresh exact-surface verification" in all_contract_text
    assert "/e-simplify" in all_contract_text
    assert "cleanup-only" in all_contract_text
    assert "cleanup-only" in all_contract_text
    assert "skill-builder" not in all_contract_text
    for each_forbidden_route_text in FORBIDDEN_ROUTE_TEXT:
        assert each_forbidden_route_text not in all_contract_text


def test_skill_contract_records_review_fields_in_both_references() -> None:
    model_routing_text, task_ticket_text, packet_contract_text = read_reference_texts()
    review_fields = (
        "resolved model",
        "effort",
        "command",
        "findings",
        "repair status",
        "surface hash",
    )

    for each_review_field in review_fields:
        assert each_review_field in model_routing_text
        assert each_review_field in task_ticket_text
    assert "packet.json" in packet_contract_text


def test_skill_contract_references_future_fixed_artifacts_without_copying_tables() -> (
    None
):
    skill_text = read_skill_text()

    assert "reference/model-routing.md" in skill_text
    assert "reference/task-ticket.md" in skill_text
    assert "reference/packet-contract.md" in skill_text
    assert "reference/packet-schema.json" in skill_text
    assert "scripts/validate_protocol.py" in skill_text
    assert "fixed routing and gate matrix lives only" not in skill_text
    assert "fixed fields live in" in skill_text
    assert (
        "[`reference/run-record.schema.json`](reference/run-record.schema.json)"
        in skill_text
    )


def test_skill_contract_companion_reference_paths_exist() -> None:
    skill_text = read_skill_text()
    local_reference_paths = re.findall(r"\]\(([^)]+)\)", skill_text)
    repository_paths = [
        each_path
        for each_path in local_reference_paths
        if not each_path.startswith(("http://", "https://", "#"))
    ]

    assert repository_paths
    for each_path in repository_paths:
        assert (SKILL_DIRECTORY / each_path).exists(), each_path


def test_skill_contract_requires_self_audit_and_publication_gates() -> None:
    skill_text = read_skill_text()

    assert "Run the workflow self-audit and retain its evidence." in skill_text
    assert "unresolved finding blocks\npublication." in skill_text
    assert "Publish only when final validation\nand self-audit pass." in skill_text
    assert "Luna xhigh `/e-simplify`" in skill_text
    assert "Luna low `/e-code-review max loop`" in skill_text
    assert "no repair flag" in skill_text


def test_skill_contract_requires_packet_companions_and_validation_scripts() -> None:
    skill_text = read_skill_text()

    for each_path in (
        PACKET_CONTRACT_PATH,
        PACKET_SCHEMA_PATH,
        PACKET_CREATOR_PATH,
        PACKET_VALIDATOR_PATH,
        VALIDATION_SCRIPT_PATH,
        RUN_VALIDATION_SCRIPT_PATH,
    ):
        assert each_path.exists(), each_path

    assert "reference/packet-contract.md" in skill_text
    assert "reference/packet-schema.json" in skill_text
    assert "scripts/create_packet.py" in skill_text
    assert "scripts/validate_packet.py" in skill_text
    assert "scripts/validate_protocol.py" in skill_text
    assert "scripts/validate_run.py" in skill_text
