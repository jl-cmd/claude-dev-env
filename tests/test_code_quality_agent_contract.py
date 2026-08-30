from pathlib import Path


AGENT_PATH = (
    Path(__file__).parents[1]
    / "packages"
    / "claude-dev-env"
    / ".agents"
    / "agents"
    / "code-quality-agent.md"
)


def should_require_cross_surface_evidence_boundaries() -> None:
    content = AGENT_PATH.read_text(encoding="utf-8")

    assert "The diff is the primary evidence." in content
    assert "callers, contracts, consumers, tests" in content
    assert "Category K requires a repository search" in content
    assert "every necessary unchanged" in content
    assert "Do not assume that a counterpart is absent" in content


def should_require_evidence_scoped_shape_b_and_uncertainty_records() -> None:
    content = AGENT_PATH.read_text(encoding="utf-8")
    normalized = " ".join(content.split())

    assert "Shape B states only what the listed lines and probes show." in content
    assert "uninspected file, caller, contract" in content
    assert "open question or an evidence gap" in normalized
    assert "An evidence gap is not a finding" in normalized


def should_preserve_a_to_q_taxonomy_and_read_only_duty() -> None:
    content = AGENT_PATH.read_text(encoding="utf-8")

    taxonomy = {
        line.split("|", 2)[1].strip()
        for line in content.splitlines()
        if line.startswith("| ") and len(line.split("|", 2)) == 3
    }
    assert set("ABCDEFGHIJKLMNOPQ").issubset(taxonomy)
    assert "Author zero edits." in content
    assert "Run zero commits or pushes." in content
