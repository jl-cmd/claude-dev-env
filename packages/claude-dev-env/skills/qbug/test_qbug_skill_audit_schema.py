"""Tests verifying the shared audit contract and qbug's reference to it.

The contract lives in bugteam/reference/audit-contract.md and is the single
source of truth for finding schema, proof-of-absence shape, adversarial pass,
Haiku secondary, and de-dup/merge rules. qbug/SKILL.md must reference it.
"""

from __future__ import annotations

from pathlib import Path


SKILL_FILE_PATH = Path(__file__).parent / "SKILL.md"
PROMPTS_FILE_PATH = Path(__file__).parent.parent / "bugteam" / "PROMPTS.md"
CONTRACT_FILE_PATH = (
    Path(__file__).parent.parent / "bugteam" / "reference" / "audit-contract.md"
)


def _load_skill_text() -> str:
    return SKILL_FILE_PATH.read_text(encoding="utf-8")


def _load_prompts_text() -> str:
    return PROMPTS_FILE_PATH.read_text(encoding="utf-8")


def _load_contract_text() -> str:
    return CONTRACT_FILE_PATH.read_text(encoding="utf-8")


def test_skill_should_reference_audit_contract_by_path() -> None:
    skill_text = _load_skill_text()
    assert "audit-contract.md" in skill_text, (
        "qbug/SKILL.md must reference the shared audit contract by path"
    )


def test_contract_should_require_structured_finding_schema() -> None:
    contract_text = _load_contract_text()
    assert "evidence_files" in contract_text, (
        "Contract must require structured finding with evidence_files[]"
    )
    assert "proof_of_absence" in contract_text, (
        "Contract must require structured proof-of-absence for clean categories"
    )


def test_contract_should_reject_bare_verified_clean_labels() -> None:
    contract_text = _load_contract_text()
    assert "lines_quoted" in contract_text, (
        "Proof-of-absence must require lines_quoted[] not bare 'verified clean'"
    )
    assert "adversarial_probes" in contract_text, (
        "Proof-of-absence must require adversarial_probes[]"
    )


def test_contract_should_require_adversarial_second_pass() -> None:
    contract_text = _load_contract_text()
    assert "Assume your first pass missed" in contract_text, (
        "Contract must include the adversarial second-pass re-prompt"
    )


def test_should_require_haiku_secondary_auditor_spawn() -> None:
    skill_text = _load_skill_text()
    assert "haiku" in skill_text.lower(), (
        "SKILL.md must reference Haiku secondary auditor"
    )
    assert "secondary" in skill_text.lower(), (
        "SKILL.md must reference secondary auditor concept"
    )


def test_contract_should_require_dedup_merge_by_file_line_category() -> None:
    contract_text = _load_contract_text()
    assert (
        "file, line, category" in contract_text
        or "(file, line, category)" in contract_text
    ), "De-dup key must be (file, line, category)"


def test_contract_should_require_severity_max_wins_on_conflict() -> None:
    contract_text = _load_contract_text()
    assert (
        "max wins" in contract_text.lower() or "severity conflict" in contract_text.lower()
    ), "Severity conflict resolution must specify max wins"


def test_should_require_loop_n_audit_json_persistence() -> None:
    skill_text = _load_skill_text()
    assert "loop-" in skill_text and "audit.json" in skill_text, (
        "SKILL.md must reference loop-N-audit.json persistence path"
    )


def test_contract_should_require_findings_and_proof_of_absence_keys_in_json() -> None:
    contract_text = _load_contract_text()
    assert '"findings"' in contract_text or "findings[]" in contract_text, (
        "loop-N-audit.json must have findings[] key"
    )
    assert (
        '"proof_of_absence"' in contract_text or "proof_of_absence[]" in contract_text
    ), "loop-N-audit.json must have proof_of_absence[] key"


def test_contract_should_require_files_opened_in_proof_of_absence() -> None:
    contract_text = _load_contract_text()
    assert "files_opened" in contract_text, (
        "Proof-of-absence struct must include files_opened[]"
    )


def test_step2_spawn_should_include_model_opus_parameter() -> None:
    skill_text = _load_skill_text()
    assert 'model="opus"' in skill_text, (
        "Step 2 Agent() spawn template must include model=\"opus\" for the primary subagent"
    )


def test_step2_spawn_should_reference_clean_coder_and_haiku_secondary() -> None:
    skill_text = _load_skill_text()
    step2_marker = "## Step 2:"
    step3_marker = "## Step 3:"
    step2_start = skill_text.find(step2_marker)
    step3_start = skill_text.find(step3_marker)
    assert step2_start != -1, "SKILL.md must have a Step 2 section"
    assert step3_start != -1, "SKILL.md must have a Step 3 section"
    step2_region = skill_text[step2_start:step3_start]
    assert "clean-coder" in step2_region, (
        "Step 2 must reference the clean-coder primary subagent spawn"
    )
    assert "haiku" in step2_region.lower(), (
        "Step 2 must reference the Haiku secondary auditor spawn"
    )


def test_prompts_md_should_contain_expanded_category_e_dead_code_variants() -> None:
    prompts_text = _load_prompts_text()
    assert (
        "dead parameter" in prompts_text.lower()
        or "dead parameters" in prompts_text.lower()
    ), "Category E must cover dead parameters"
    assert (
        "dead local" in prompts_text.lower() or "dead locals" in prompts_text.lower()
    ), "Category E must cover dead locals"
    assert (
        "dead import" in prompts_text.lower() or "dead imports" in prompts_text.lower()
    ), "Category E must cover dead imports"
    assert (
        "dead branch" in prompts_text.lower() or "dead branches" in prompts_text.lower()
    ), "Category E must cover dead branches"
    assert (
        "dead return" in prompts_text.lower() or "dead returns" in prompts_text.lower()
    ), "Category E must cover dead returns"
