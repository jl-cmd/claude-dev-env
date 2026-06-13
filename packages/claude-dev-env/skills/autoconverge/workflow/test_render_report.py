"""Tests for render_report.py against the real wf_881252e6-700 fixture."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_report

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "wf_run"
FIXTURE_JOURNAL = FIXTURE_DIR / "workflows" / "wf_881252e6-700.json"

EXPECTED_TOTAL_FINDINGS = 15
EXPECTED_CRITICAL_COUNT = 0
EXPECTED_MINOR_COUNT = 15
EXPECTED_FIX_COMMIT_COUNT = 2
EXPECTED_GENERATED_DATE = "2026-06-13"
EXPECTED_FINDINGS_BY_ROUND = {1: 11, 2: 2, 3: 2, 4: 0}
EXPECTED_FINDINGS_BY_THEME = {"src/exports": 11, "src/logging": 2, "src/web": 2}


def test_load_run_data_aggregate_counts() -> None:
    """Should parse the fixture journal and transcripts into correct aggregate counts."""
    run_data = render_report.load_run_data(FIXTURE_JOURNAL, Path("."))

    assert run_data.total_finding_count == EXPECTED_TOTAL_FINDINGS
    assert run_data.critical_finding_count == EXPECTED_CRITICAL_COUNT
    assert run_data.minor_finding_count == EXPECTED_MINOR_COUNT
    assert run_data.fix_commit_count == EXPECTED_FIX_COMMIT_COUNT
    assert run_data.generated_date == EXPECTED_GENERATED_DATE


def test_load_run_data_by_round_counts() -> None:
    """Should assign findings to rounds by workflowProgress position boundary."""
    run_data = render_report.load_run_data(FIXTURE_JOURNAL, Path("."))

    for each_round, expected_count in EXPECTED_FINDINGS_BY_ROUND.items():
        actual_count = run_data.finding_count_by_round.get(each_round, 0)
        assert actual_count == expected_count, (
            f"Round {each_round}: expected {expected_count}, got {actual_count}"
        )


def test_load_run_data_by_theme_counts() -> None:
    """Should group distinct findings by the first two path segments."""
    run_data = render_report.load_run_data(FIXTURE_JOURNAL, Path("."))

    assert len(run_data.finding_count_by_theme) == len(EXPECTED_FINDINGS_BY_THEME)
    for each_theme, expected_count in EXPECTED_FINDINGS_BY_THEME.items():
        actual_count = run_data.finding_count_by_theme.get(each_theme, 0)
        assert actual_count == expected_count, (
            f"Theme {each_theme}: expected {expected_count}, got {actual_count}"
        )


def test_cli_end_to_end(tmp_path: Path) -> None:
    """Should exit 0, print the output path, and write HTML with expected substrings."""
    out_path = tmp_path / "report.html"
    render_script = Path(__file__).resolve().parent / "render_report.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(render_script),
            "--journal",
            str(FIXTURE_JOURNAL),
            "--out",
            str(out_path),
            "--pr",
            "example-owner/example-repo#211",
            "--final-sha",
            "7c2f420c4d5b7c83aa47f93d99a0f1420e3373c4",
            "--rounds",
            "4",
            "--repo",
            ".",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"

    printed_path = completed.stdout.strip()
    assert printed_path == str(out_path), (
        f"Expected stdout {out_path!r}, got {printed_path!r}"
    )

    assert out_path.exists(), "Output HTML file was not written"
    html_content = out_path.read_text(encoding="utf-8")

    expected_substrings = [
        "PR #211 Convergence Insights",
        "at-a-glance",
        "Findings by severity",
        "Findings by round",
        "Tests added per round",
        "Findings by theme",
        "Banned identifier",
        "result",
        "in test",
        "Converged",
        "7c2f420c",
    ]
    for each_substring in expected_substrings:
        assert each_substring in html_content, (
            f"Expected substring not found in HTML: {each_substring!r}"
        )

    minor_card_count = html_content.count('class="bug-card minor"')
    assert minor_card_count == EXPECTED_MINOR_COUNT, (
        f"Expected {EXPECTED_MINOR_COUNT} minor cards, found {minor_card_count}"
    )


def test_html_contains_no_hedging_words(tmp_path: Path) -> None:
    """Should produce HTML with no hedging language anywhere in the rendered text."""
    out_path = tmp_path / "report-hedge.html"
    render_script = Path(__file__).resolve().parent / "render_report.py"

    subprocess.run(
        [
            sys.executable,
            str(render_script),
            "--journal",
            str(FIXTURE_JOURNAL),
            "--out",
            str(out_path),
            "--pr",
            "example-owner/example-repo#211",
            "--final-sha",
            "7c2f420c4d5b7c83aa47f93d99a0f1420e3373c4",
            "--rounds",
            "4",
            "--repo",
            ".",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    html_content = out_path.read_text(encoding="utf-8")
    all_hedging_words = [
        "could",
        "might",
        "would",
        "should",
        "likely",
        "probably",
        "appears",
        "seems",
    ]
    for each_word in all_hedging_words:
        pattern = re.compile(r"\b" + re.escape(each_word) + r"\b", re.IGNORECASE)
        assert not pattern.search(html_content), (
            f"Hedging word {each_word!r} found in rendered HTML"
        )


def _init_git_repo(repo_path: Path) -> None:
    """Initialize a git repo with a committed baseline so diffs resolve."""
    subprocess.run(
        ["git", "-C", str(repo_path), "init"], capture_output=True, check=True
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.name", "Test"],
        capture_output=True,
        check=True,
    )
    (repo_path / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo_path), "add", "."], capture_output=True, check=True
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "commit", "-m", "baseline"],
        capture_output=True,
        check=True,
    )


def _resolve_head(repo_path: Path) -> str:
    """Return the current HEAD sha of the repo."""
    completed = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_count_tests_added_does_not_double_count_new_file(tmp_path: Path) -> None:
    """Should count a new test file with two test functions as exactly two."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _init_git_repo(repo_path)
    base_sha = _resolve_head(repo_path)

    new_test_file = repo_path / "test_feature.py"
    new_test_file.write_text(
        "def test_one() -> None:\n"
        "    assert True\n"
        "\n"
        "def test_two() -> None:\n"
        "    assert True\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "add", "."], capture_output=True, check=True
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "commit", "-m", "add tests"],
        capture_output=True,
        check=True,
    )
    new_sha = _resolve_head(repo_path)

    test_count = render_report._count_tests_added(base_sha, new_sha, repo_path)

    assert test_count == 2, f"Expected 2 added test definitions, got {test_count}"


def test_count_tests_added_counts_nested_test_directory(tmp_path: Path) -> None:
    """Should count test functions added under a nested src/<pkg>/tests/ layout."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _init_git_repo(repo_path)
    base_sha = _resolve_head(repo_path)

    nested_test_file = repo_path / "src" / "exports" / "tests" / "test_feature.py"
    nested_test_file.parent.mkdir(parents=True)
    nested_test_file.write_text(
        "def test_one() -> None:\n"
        "    assert True\n"
        "\n"
        "def test_two() -> None:\n"
        "    assert True\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "add", "."], capture_output=True, check=True
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "commit", "-m", "add nested tests"],
        capture_output=True,
        check=True,
    )
    new_sha = _resolve_head(repo_path)

    test_count = render_report._count_tests_added(base_sha, new_sha, repo_path)

    assert test_count == 2, (
        f"Expected 2 added test definitions in nested dir, got {test_count}"
    )


def test_count_tests_added_counts_should_functions(tmp_path: Path) -> None:
    """Should count pytest should_* functions, not only def test functions."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _init_git_repo(repo_path)
    base_sha = _resolve_head(repo_path)

    new_test_file = repo_path / "test_behavior.py"
    new_test_file.write_text(
        "def should_validate_order() -> None:\n"
        "    assert True\n"
        "\n"
        "def test_explicit() -> None:\n"
        "    assert True\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "add", "."], capture_output=True, check=True
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "commit", "-m", "add should and test"],
        capture_output=True,
        check=True,
    )
    new_sha = _resolve_head(repo_path)

    test_count = render_report._count_tests_added(base_sha, new_sha, repo_path)

    assert test_count == 2, (
        f"Expected 2 added definitions (should_ + test), got {test_count}"
    )


def test_extract_structured_output_returns_last_tool_input(tmp_path: Path) -> None:
    """Should return the input of the last StructuredOutput tool_use in the transcript."""
    transcript_path = tmp_path / "agent-stream.jsonl"
    earlier_line = json.dumps(
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": render_report.STRUCTURED_OUTPUT_TOOL_NAME,
                        "input": {"newSha": "aaaa1111", "pushed": False},
                    }
                ]
            }
        }
    )
    later_line = json.dumps(
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": render_report.STRUCTURED_OUTPUT_TOOL_NAME,
                        "input": {"newSha": "bbbb2222", "pushed": True},
                    }
                ]
            }
        }
    )
    transcript_path.write_text(earlier_line + "\n" + later_line + "\n", encoding="utf-8")

    extracted = render_report._extract_structured_output(transcript_path)

    assert extracted == {"newSha": "bbbb2222", "pushed": True}


def test_extract_structured_output_returns_none_on_missing_file(tmp_path: Path) -> None:
    """Should return None when the transcript file does not exist."""
    missing_path = tmp_path / "does-not-exist.jsonl"

    extracted = render_report._extract_structured_output(missing_path)

    assert extracted is None


def test_render_fix_block_falls_back_when_sha_empty() -> None:
    """Should not claim a commit when the fix record has an empty new sha."""
    finding = render_report.RawFinding(
        file="src/exports/writer.py",
        line=10,
        severity="P2",
        title="example finding",
        detail="example detail",
        round_number=2,
        sha="abc",
    )
    fix_by_round = {
        2: render_report.FixRecord(
            new_sha="",
            pushed=False,
            resolved_without_commit=False,
            round_number=2,
            base_sha="base",
        )
    }

    fix_html = render_report._render_fix_block(finding, fix_by_round)

    assert "<code></code>" not in fix_html
    assert "fix commit" not in fix_html
    assert "resolved during convergence" in fix_html


def _write_structured_output_transcript(
    transcript_path: Path, tool_input: dict[str, object]
) -> None:
    """Write a one-line agent transcript carrying a single StructuredOutput tool_use."""
    line = json.dumps(
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": render_report.STRUCTURED_OUTPUT_TOOL_NAME,
                        "input": tool_input,
                    }
                ]
            }
        }
    )
    transcript_path.write_text(line + "\n", encoding="utf-8")


def test_base_sha_resets_each_round_when_prior_fix_transcript_missing(
    tmp_path: Path,
) -> None:
    """Should bind each round's fix base sha to that round's own head, never a prior round's."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    round_one_head = "1111111111111111111111111111111111111111"
    round_two_head = "2222222222222222222222222222222222222222"

    round_one_gate_id = "round-one-gate"
    round_two_gate_id = "round-two-gate"
    round_two_fix_id = "round-two-fix"

    _write_structured_output_transcript(
        agents_dir / f"agent-{round_one_gate_id}.jsonl",
        {"sha": round_one_head, "clean": False, "findings": []},
    )
    _write_structured_output_transcript(
        agents_dir / f"agent-{round_two_gate_id}.jsonl",
        {"sha": round_two_head, "clean": False, "findings": []},
    )
    _write_structured_output_transcript(
        agents_dir / f"agent-{round_two_fix_id}.jsonl",
        {"newSha": round_two_head, "pushed": True, "resolvedWithoutCommit": False},
    )

    progress_entries: list[dict] = [
        {"label": render_report.LABEL_RESOLVE_HEAD, "agentId": "round-one-resolve"},
        {"label": render_report.LABEL_COPILOT_GATE, "agentId": round_one_gate_id},
        {"label": render_report.LABEL_PREFIX_FIX + "copilot", "agentId": "missing-fix"},
        {"label": render_report.LABEL_RESOLVE_HEAD, "agentId": "round-two-resolve"},
        {"label": render_report.LABEL_COPILOT_GATE, "agentId": round_two_gate_id},
        {"label": render_report.LABEL_PREFIX_FIX + "copilot", "agentId": round_two_fix_id},
    ]

    _all_findings, fix_by_round = render_report._parse_progress_entries(
        progress_entries, agents_dir
    )

    assert fix_by_round[2].base_sha == round_two_head, (
        "Round 2 fix recorded a stale base sha leaked from round 1; "
        f"expected {round_two_head}, got {fix_by_round[2].base_sha}"
    )


def test_robustness_with_missing_transcripts(tmp_path: Path) -> None:
    """Should exit 0 and render zero finding cards when no agent transcripts exist."""
    run_root = tmp_path / "wf_run"
    journal_destination = run_root / "workflows" / FIXTURE_JOURNAL.name
    journal_destination.parent.mkdir(parents=True)
    shutil.copy(FIXTURE_JOURNAL, journal_destination)

    run_id = FIXTURE_JOURNAL.stem
    empty_agents_dir = run_root / "subagents" / "workflows" / run_id
    empty_agents_dir.mkdir(parents=True)

    out_path = tmp_path / "report-robust.html"
    render_script = Path(__file__).resolve().parent / "render_report.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(render_script),
            "--journal",
            str(journal_destination),
            "--out",
            str(out_path),
            "--pr",
            "example-owner/example-repo#211",
            "--final-sha",
            "7c2f420c4d5b7c83aa47f93d99a0f1420e3373c4",
            "--rounds",
            "4",
            "--repo",
            ".",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, (
        f"Render failed despite missing transcripts:\n{completed.stderr}"
    )

    html_content = out_path.read_text(encoding="utf-8")
    assert "PR #211 Convergence Insights" in html_content

    finding_card_count = html_content.count('class="bug-card')
    assert finding_card_count == 0, (
        f"Missing transcripts yielded findings: expected 0 cards, got {finding_card_count}"
    )
