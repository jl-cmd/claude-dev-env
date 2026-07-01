"""Behavioral tests for the commit-time terminology sweep."""

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType


def _load_sweep_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "terminology_sweep.py"
    spec = importlib.util.spec_from_file_location("terminology_sweep", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sweep_module = _load_sweep_module()
sweep_diff = sweep_module.sweep_diff
staged_terminology_findings = sweep_module.staged_terminology_findings
main = sweep_module.main


def _init_git_repository(repository_path: Path) -> None:
    for each_command in (
        ["git", "init"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(each_command, cwd=repository_path, check=True, capture_output=True)


CODE_AND_PROSE_DIFF = (
    "diff --git a/api/quota.py b/api/quota.py\n"
    "--- a/api/quota.py\n"
    "+++ b/api/quota.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+def read_quota(account):\n"
    '+    return account["premium_interactions"]\n'
    "diff --git a/docs/README.md b/docs/README.md\n"
    "--- a/docs/README.md\n"
    "+++ b/docs/README.md\n"
    "@@ -0,0 +1,1 @@\n"
    "+The premium-request budget gates the run.\n"
)


def test_flags_prose_near_miss_of_code_identifier() -> None:
    findings = sweep_diff(CODE_AND_PROSE_DIFF)
    assert len(findings) == 1
    assert "docs/README.md:1" in findings[0]
    assert "premium-request" in findings[0]
    assert "premium_interactions" in findings[0]


def test_does_not_flag_exact_hyphen_variant() -> None:
    diff = (
        "diff --git a/api/quota.py b/api/quota.py\n"
        "--- a/api/quota.py\n"
        "+++ b/api/quota.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+premium_interactions = 5\n"
        "diff --git a/docs/README.md b/docs/README.md\n"
        "--- a/docs/README.md\n"
        "+++ b/docs/README.md\n"
        "@@ -0,0 +1,1 @@\n"
        "+The premium-interactions budget gates the run.\n"
    )
    assert sweep_diff(diff) == []


def _code_and_prose_collision_diff(code_identifier: str, prose_compound: str) -> str:
    return (
        "diff --git a/api/quota.py b/api/quota.py\n"
        "--- a/api/quota.py\n"
        "+++ b/api/quota.py\n"
        "@@ -0,0 +1,1 @@\n"
        f"+{code_identifier} = 5\n"
        "diff --git a/docs/README.md b/docs/README.md\n"
        "--- a/docs/README.md\n"
        "+++ b/docs/README.md\n"
        "@@ -0,0 +1,1 @@\n"
        f"+This is a {prose_compound} cache.\n"
    )


def test_does_not_flag_english_compound_tail_read_only() -> None:
    diff = _code_and_prose_collision_diff("read_config", "read-only")
    assert sweep_diff(diff) == []


def test_does_not_flag_english_compound_tail_data_driven() -> None:
    diff = _code_and_prose_collision_diff("data_source", "data-driven")
    assert sweep_diff(diff) == []


def test_does_not_flag_english_compound_tail_type_safe() -> None:
    diff = _code_and_prose_collision_diff("type_check", "type-safe")
    assert sweep_diff(diff) == []


def test_does_not_flag_english_compound_tail_test_driven() -> None:
    diff = _code_and_prose_collision_diff("test_case", "test-driven")
    assert sweep_diff(diff) == []


def test_does_not_flag_english_compound_tail_high_quality() -> None:
    diff = _code_and_prose_collision_diff("high_level", "high-quality")
    assert sweep_diff(diff) == []


def test_does_not_flag_unrelated_hyphenated_prose() -> None:
    diff = (
        "diff --git a/api/quota.py b/api/quota.py\n"
        "--- a/api/quota.py\n"
        "+++ b/api/quota.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+premium_interactions = 5\n"
        "diff --git a/docs/README.md b/docs/README.md\n"
        "--- a/docs/README.md\n"
        "+++ b/docs/README.md\n"
        "@@ -0,0 +1,1 @@\n"
        "+A well-known open-source project.\n"
    )
    assert sweep_diff(diff) == []


def test_flags_near_miss_inside_code_comment() -> None:
    diff = (
        "diff --git a/api/quota.py b/api/quota.py\n"
        "--- a/api/quota.py\n"
        "+++ b/api/quota.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+premium_interactions = 5\n"
        "+# the premium-request path resets the counter\n"
    )
    findings = sweep_diff(diff)
    assert len(findings) == 1
    assert "premium-request" in findings[0]


def test_no_findings_when_no_multiword_identifier_introduced() -> None:
    diff = (
        "diff --git a/docs/README.md b/docs/README.md\n"
        "--- a/docs/README.md\n"
        "+++ b/docs/README.md\n"
        "@@ -0,0 +1,1 @@\n"
        "+The premium-request budget gates the run.\n"
    )
    assert sweep_diff(diff) == []


def test_main_exits_one_when_findings(tmp_path: Path) -> None:
    diff_file = tmp_path / "change.diff"
    diff_file.write_text(CODE_AND_PROSE_DIFF, encoding="utf-8")
    exit_code = main(["--diff-file", str(diff_file)])
    assert exit_code == 1


def test_main_exits_zero_when_clean(tmp_path: Path) -> None:
    diff_file = tmp_path / "clean.diff"
    diff_file.write_text(
        "diff --git a/docs/README.md b/docs/README.md\n"
        "--- a/docs/README.md\n"
        "+++ b/docs/README.md\n"
        "@@ -0,0 +1,1 @@\n"
        "+Nothing to see here.\n",
        encoding="utf-8",
    )
    exit_code = main(["--diff-file", str(diff_file)])
    assert exit_code == 0


def test_staged_terminology_findings_flags_staged_prose(tmp_path: Path) -> None:
    _init_git_repository(tmp_path)
    (tmp_path / "quota.py").write_text(
        "premium_interactions = 5\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "The premium-request budget gates the run.\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    findings = staged_terminology_findings(tmp_path)
    assert any("premium-request" in each_finding for each_finding in findings)


def test_staged_terminology_findings_empty_when_clean(tmp_path: Path) -> None:
    _init_git_repository(tmp_path)
    (tmp_path / "README.md").write_text("Nothing notable here.\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    assert staged_terminology_findings(tmp_path) == []
