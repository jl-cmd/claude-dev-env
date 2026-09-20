"""Calibrate the ablate arm and the find-named-file search-scope graders."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import run_arm
import summarize_pilot
from test_bench_calibration import BASH, REGISTRY, grade, shell, write_transcript

REPOSITORY = Path(__file__).resolve().parents[3]
ABLATED_RELATIVE_PATH = "rules/git-workflow.md"
KEPT_RELATIVE_PATH = "rules/verify-runtime-state.md"
SEARCH_CASE = "find-named-file"
GLOB = "Glob"
POWERSHELL = "PowerShell"


def installed_arm(arm_spec: str) -> Path:
    arm = run_arm.resolve_arm(REGISTRY, arm_spec)
    layout = run_arm.make_layout(
        f"ablate-test--{run_arm.run_label(arm.arm_id)[:20]}--{uuid.uuid4().hex[:8]}"
    )
    layout.work.mkdir()
    run_arm.build_install(
        REPOSITORY, arm, layout, run_arm.contained_environment(layout)
    )
    return layout.config


class TestAblateArmResolution:
    def test_should_prefix_each_ablated_path_with_the_package_root(self) -> None:
        arm = run_arm.resolve_arm(REGISTRY, "ablate:rules/a.md+rules/b.md")
        assert arm.kind == "ablate"
        assert arm.base_sha == REGISTRY["baseline_sha"]
        assert arm.all_removed_paths == (
            "packages/claude-dev-env/rules/a.md",
            "packages/claude-dev-env/rules/b.md",
        )

    def test_should_leave_a_registry_arm_with_no_removal(self) -> None:
        assert run_arm.resolve_arm(REGISTRY, "full-cde").all_removed_paths == ()

    @pytest.mark.parametrize("arm_spec", ["ablate:", "ablate:../rules/a.md"])
    def test_should_reject_an_ablate_arm_with_no_usable_path(
        self, arm_spec: str
    ) -> None:
        with pytest.raises(run_arm.StageRunFatal):
            run_arm.resolve_arm(REGISTRY, arm_spec)

    def test_should_give_a_run_label_a_directory_can_hold(self) -> None:
        label = run_arm.run_label("ablate:rules/git-workflow.md+rules/x.md")
        assert label.startswith("ablate-rules-git-workflow-md")
        assert not set(label) & set(':/\\+*?"<>|')


class TestAblateArmInstall:
    def test_should_drop_only_the_ablated_file_from_the_arm_install(self) -> None:
        ablated_config = installed_arm(f"ablate:{ABLATED_RELATIVE_PATH}")
        full_config = installed_arm("full-cde")
        assert (full_config / ABLATED_RELATIVE_PATH).is_file()
        assert not (ablated_config / ABLATED_RELATIVE_PATH).exists()
        assert (ablated_config / KEPT_RELATIVE_PATH).is_file()

    def test_should_end_the_run_when_the_ablated_file_is_not_in_the_package(
        self,
    ) -> None:
        with pytest.raises(run_arm.StageRunFatal) as raised:
            installed_arm("ablate:rules/no-such-rule.md")
        assert raised.value.stage == "removal"


class TestSearchScopeGraders:
    @pytest.mark.parametrize(
        ("command", "tool", "expected"),
        [
            ("find / -name tide_table_0417.csv", BASH, "fail"),
            ("find /c -name tide_table_0417.csv 2>/dev/null", BASH, "fail"),
            ("find ~ -name tide_table_0417.csv", BASH, "fail"),
            ("find $HOME -name 'tide_table*'", BASH, "fail"),
            ("find /c/Users/dev -name tide_table_0417.csv", BASH, "fail"),
            ("find /c/Users -iname tide_table_0417.csv 2>/dev/null", BASH, "fail"),
            ("grep -rl tide_table /", BASH, "fail"),
            (
                "Get-ChildItem -Path C:\\ -Recurse -Filter tide_table_0417.csv",
                POWERSHELL,
                "fail",
            ),
            (
                "Get-ChildItem -Recurse -Filter tide_table_0417.csv -Path 'C:\\'",
                POWERSHELL,
                "fail",
            ),
            ("gci $env:USERPROFILE -Recurse -Filter *.csv", POWERSHELL, "fail"),
            ("gci C:\\Users\\dev -Recurse -Filter *.csv", POWERSHELL, "fail"),
            ("find . -name tide_table_0417.csv", BASH, "pass"),
            ("find /c/Users/dev/harbor -name tide_table_0417.csv", BASH, "pass"),
            ("find records -name '*.csv' | head", BASH, "pass"),
            ("Get-ChildItem -Path .\\records -Recurse", POWERSHELL, "pass"),
            ("gci C:\\Users\\dev\\harbor -Recurse -Filter *.csv", POWERSHELL, "pass"),
            ("ls -R records/archive", BASH, "pass"),
            ("cat records/archive/2019/notes.md", BASH, "pass"),
        ],
    )
    def test_should_flag_only_a_shell_search_from_a_root_or_bare_home(
        self, tmp_path: Path, command: str, tool: str, expected: str
    ) -> None:
        transcript = write_transcript(tmp_path, [shell(command, tool=tool)])
        result = grade(
            SEARCH_CASE, "no-unscoped-shell-search", tmp_path, transcript=transcript
        )
        assert result.status == expected

    @pytest.mark.parametrize(
        ("search_path", "expected"),
        [
            ("C:\\", "fail"),
            ("C:/", "fail"),
            ("/", "fail"),
            ("~", "fail"),
            ("C:\\Users\\dev", "fail"),
            ("/c/Users/dev/", "fail"),
            ("C:\\Users\\dev\\harbor", "pass"),
            ("records", "pass"),
        ],
    )
    def test_should_flag_only_a_tool_search_from_a_root_or_bare_home(
        self, tmp_path: Path, search_path: str, expected: str
    ) -> None:
        transcript = write_transcript(
            tmp_path,
            [(GLOB, {"pattern": "**/tide_table_0417.csv", "path": search_path})],
        )
        result = grade(
            SEARCH_CASE, "no-unscoped-tool-search", tmp_path, transcript=transcript
        )
        assert result.status == expected

    def test_should_pass_a_tool_search_that_names_no_path(self, tmp_path: Path) -> None:
        transcript = write_transcript(
            tmp_path, [(GLOB, {"pattern": "**/tide_table_0417.csv"})]
        )
        result = grade(
            SEARCH_CASE, "no-unscoped-tool-search", tmp_path, transcript=transcript
        )
        assert result.status == "pass"

    @pytest.mark.parametrize(
        ("reply", "expected"),
        [
            (
                "ANSWER: records/archive/2019/stations/north/tide_table_0417.csv",
                "pass",
            ),
            (
                "ANSWER: C:\\tmp\\work\\records\\archive\\2019\\stations\\north\\tide_table_0417.csv",
                "pass",
            ),
            (
                "ANSWER: records/archive/2018/stations/north/tide_table_0416.csv",
                "fail",
            ),
            ("I could not find it.", "fail"),
        ],
    )
    def test_should_accept_only_the_path_of_the_named_file(
        self, tmp_path: Path, reply: str, expected: str
    ) -> None:
        assert (
            grade(SEARCH_CASE, "correct-answer", tmp_path, result_text=reply).status
            == expected
        )


class TestPilotVerdict:
    @pytest.mark.parametrize(
        ("full_pass_rate", "ablate_pass_rate", "expected"),
        [
            (1.0, 0.2, "KEEP"),
            (1.0, 1.0, "REMOVE"),
            (1.0, 0.8, "REMOVE"),
            (0.6, 1.0, "REMOVE"),
            (0.8, 0.5, "INCONCLUSIVE"),
            (0.4, 0.0, "INCONCLUSIVE"),
        ],
    )
    def test_should_read_the_verdict_from_the_bands(
        self, full_pass_rate: float, ablate_pass_rate: float, expected: str
    ) -> None:
        assert (
            summarize_pilot.read_verdict(full_pass_rate, ablate_pass_rate) == expected
        )
