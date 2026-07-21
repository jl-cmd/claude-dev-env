import re
from pathlib import Path


SKILL_DIRECTORY = Path(__file__).parent
SKILL_PATH = SKILL_DIRECTORY / "SKILL.md"
MODEL_ROUTING_PATH = SKILL_DIRECTORY / "reference" / "model-routing.md"
TASK_TICKET_PATH = SKILL_DIRECTORY / "reference" / "task-ticket.md"
FORBIDDEN_ROUTE_TEXT = (
    "claude",
    "provider",
    "helper",
    "--fix",
    "invoke_code_review.py",
    "C:\\Users\\",
)
EXPECTED_TASK_PROTOCOL_HEADING = (
    "## One-task and one-"
    "commit protocol"
)


def read_skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def read_reference_texts() -> tuple[str, str]:
    return (
        MODEL_ROUTING_PATH.read_text(encoding="utf-8"),
        TASK_TICKET_PATH.read_text(encoding="utf-8"),
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


def test_skill_contract_composes_all_peer_skills_with_missing_behavior() -> None:
    skill_text = read_skill_text()

    for each_peer_skill in ("anthropic-plan", "orchestrator", "team-advisor"):
        peer_rows = [
            each_line
            for each_line in skill_text.splitlines()
            if each_line.startswith(f"| `{each_peer_skill}` |")
        ]
        assert len(peer_rows) == 1, each_peer_skill
        missing_behavior_cell = peer_rows[0].rstrip().rstrip("|").rsplit("|", 1)[1].strip()
        assert missing_behavior_cell.startswith("Refuse"), each_peer_skill

    assert skill_text.count("Missing behavior") == 1
    assert "Approved `docs/plans/<slug>/` packet" in skill_text
    assert "Run charter, task ledger" in skill_text
    assert "A reachable high-tier advisor decision" in skill_text
    assert "workflow self-audit" in skill_text


def test_skill_contract_pins_model_roles_and_worker_routing() -> None:
    skill_text = read_skill_text()

    assert "planner and final validator use Luna xhigh" in skill_text
    assert "orchestrator uses the max route" in skill_text
    assert "Sol xhigh advisor" in skill_text
    assert "heavily at decisive points" in skill_text
    assert "Every implementation,\nreview, and repair worker uses fast, low-effort Luna" in skill_text
    assert "separate fast low-effort Luna review worker" in skill_text
    assert "separate fast low-effort Luna repair worker" in skill_text
    assert "Unavailable models fail closed" in skill_text


def test_skill_contract_enforces_task_commit_and_review_order() -> None:
    skill_text = read_skill_text()

    assert EXPECTED_TASK_PROTOCOL_HEADING in skill_text
    assert "fresh verification and `verified_commit_gate`" in skill_text
    assert "native low-effort correctness review" in skill_text
    assert "native low-effort correctness review capability at `/e-code-review low`" in skill_text
    assert "returns findings only" in skill_text
    assert "has no repair" in skill_text
    assert "separate fast low-effort Luna repair worker" in skill_text
    assert "rerun the task acceptance check and fresh" in skill_text
    assert "exact-surface verification" in skill_text
    assert "amend the task commit" in skill_text
    assert "resolved model, effort, command, findings, repair status, and\nsurface hash" in skill_text
    assert "repeat the native review" in skill_text
    assert "until clean" in skill_text
    assert "maps each commit to one\nplanned task" in skill_text


def test_skill_contract_uses_only_the_native_review_route() -> None:
    all_contract_text = "\n".join((read_skill_text(), *read_reference_texts()))

    assert "/e-code-review low" in all_contract_text
    assert "findings only" in all_contract_text
    assert "no repair flag" in all_contract_text
    assert "separate fast low-effort Luna" in all_contract_text
    assert "fresh exact-surface verification" in all_contract_text
    assert "/e-simplify" in all_contract_text
    assert "cleanup-only" in all_contract_text
    assert "does not replace correctness review" in all_contract_text
    assert "skill-builder" not in all_contract_text
    for each_forbidden_route_text in FORBIDDEN_ROUTE_TEXT:
        assert each_forbidden_route_text not in all_contract_text


def test_skill_contract_records_review_fields_in_both_references() -> None:
    model_routing_text, task_ticket_text = read_reference_texts()
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


def test_skill_contract_references_future_fixed_artifacts_without_copying_tables() -> None:
    skill_text = read_skill_text()

    assert "reference/model-routing.md" in skill_text
    assert "reference/task-ticket.md" in skill_text
    assert "scripts/validate_protocol.py" in skill_text
    assert "fixed routing and gate matrix lives only" not in skill_text
    assert "fixed fields live in" in skill_text
    assert "[`reference/run-record.schema.json`](reference/run-record.schema.json)" in skill_text


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

    assert "Run the workflow self-audit" in skill_text
    assert "Any unmapped commit, missing record, failed gate," in skill_text
    assert "unresolved finding blocks publication." in skill_text
    assert "Publish only when\nthe final validator and self-audit both pass" in skill_text
    assert "Luna xhigh `/e-simplify`" in skill_text
    assert "Luna low `/e-code-review max loop`" in skill_text
    assert "Do not add a repair flag" in skill_text
