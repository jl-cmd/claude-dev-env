"""Specifications for the PR label derivation logic.

Every fixture below is either a real title, path, or line count pulled from
jl-cmd/claude-dev-env's own pull request history, or a synthetic-but-realistic
conventional-commit title for a prefix (style, build) that has never appeared
in this repository's history. The derivation functions under test never call
the GitHub API, so none of this needs mocking.
"""

import dataclasses
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Self

_CI_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_CI_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_CI_SCRIPTS_DIR))

import pr_labeler
import pr_labeler_derivation
import pr_labeler_transport

CLAUDE_DEV_ENV_CONFIG_PATH = _CI_SCRIPTS_DIR / "pr_labeler_config.yml"
CLAUDE_DEV_ENV_CONFIG = pr_labeler_derivation.load_labeler_config(CLAUDE_DEV_ENV_CONFIG_PATH)


class RecordingApiCaller:
    """A GitHubApiCaller stand-in: records every call it receives, never touches the network.

    Each call pops the next canned response in order (paginated fetches issue
    more than one call); once the queue is empty, further calls return None.
    """

    def __init__(self, canned_responses: Sequence[object] = ()) -> None:
        self.remaining_responses: list[object] = list(canned_responses)
        self.all_recorded_calls: list[tuple[str, str, str, object]] = []

    def __call__(
        self, url: str, github_token: str, http_method: str, json_payload: object
    ) -> object:
        self.all_recorded_calls.append((url, github_token, http_method, json_payload))
        if not self.remaining_responses:
            return None
        return self.remaining_responses.pop(0)


class FakeUrlOpener:
    """A Callable[[Request], ReadableHttpResponse] stand-in around canned response bytes."""

    def __init__(self, response_body_bytes: bytes) -> None:
        self.response_body_bytes = response_body_bytes
        self.all_opened_requests: list[object] = []

    def __call__(self, api_request: object) -> Self:
        self.all_opened_requests.append(api_request)
        return self

    def read(self) -> bytes:
        return self.response_body_bytes

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class TestDeriveTypeLabel:
    def should_map_feat_prefix_to_feature_label(self) -> None:
        title = "feat(split-pr): fail a plan whose slice prefix is not closed under references"
        assert pr_labeler_derivation.derive_type_label(title) == "type: feature"

    def should_map_fix_prefix_to_bug_label(self) -> None:
        title = "fix(install): move stale skill files aside instead of leaving them installed"
        assert pr_labeler_derivation.derive_type_label(title) == "type: bug"

    def should_map_docs_prefix_to_docs_label(self) -> None:
        assert pr_labeler_derivation.derive_type_label("docs(rules): add state-what-is rule") == "type: docs"

    def should_map_refactor_prefix_to_refactor_label(self) -> None:
        title = "refactor(skills): move package-root _shared under skills/"
        assert pr_labeler_derivation.derive_type_label(title) == "type: refactor"

    def should_map_style_prefix_to_refactor_label(self) -> None:
        title = "style(hooks): apply ruff formatting across blocking hooks"
        assert pr_labeler_derivation.derive_type_label(title) == "type: refactor"

    def should_map_test_prefix_to_test_label(self) -> None:
        title = "test(split-pr): paired script and supersede coverage"
        assert pr_labeler_derivation.derive_type_label(title) == "type: test"

    def should_map_ci_prefix_to_ci_label(self) -> None:
        title = "ci: path-filter Python and JS suites on pull requests"
        assert pr_labeler_derivation.derive_type_label(title) == "type: ci"

    def should_map_build_prefix_to_ci_label(self) -> None:
        assert pr_labeler_derivation.derive_type_label("build(deps): bump esbuild to 0.24.2") == "type: ci"

    def should_map_chore_prefix_to_chore_label(self) -> None:
        title = "chore(labels): add label file, sync workflow, and template label names"
        assert pr_labeler_derivation.derive_type_label(title) == "type: chore"

    def should_map_revert_prefix_to_chore_label(self) -> None:
        title = "revert: undo accidental merges API merge of #286 into main"
        assert pr_labeler_derivation.derive_type_label(title) == "type: chore"

    def should_map_perf_prefix_to_perf_label(self) -> None:
        title = "perf(code_rules_gate): batch blob reads with git cat-file --batch"
        assert pr_labeler_derivation.derive_type_label(title) == "type: perf"

    def should_match_a_scoped_breaking_change_title(self) -> None:
        title = "feat(api)!: drop the legacy v1 endpoint"
        assert pr_labeler_derivation.derive_type_label(title) == "type: feature"

    def should_return_none_for_an_unparseable_title(self) -> None:
        assert pr_labeler_derivation.derive_type_label("Update xhigh.md") is None


class TestDeriveSizeLabel:
    THRESHOLDS = pr_labeler_derivation.SizeThresholds(
        extra_small_max_lines=20,
        small_max_lines=100,
        medium_max_lines=500,
        large_max_lines=1000,
    )

    def should_label_twenty_lines_as_extra_small(self) -> None:
        assert pr_labeler_derivation.derive_size_label(20, self.THRESHOLDS) == "size: XS"

    def should_label_twenty_one_lines_as_small(self) -> None:
        assert pr_labeler_derivation.derive_size_label(21, self.THRESHOLDS) == "size: S"

    def should_label_one_hundred_lines_as_small(self) -> None:
        assert pr_labeler_derivation.derive_size_label(100, self.THRESHOLDS) == "size: S"

    def should_label_one_hundred_one_lines_as_medium(self) -> None:
        assert pr_labeler_derivation.derive_size_label(101, self.THRESHOLDS) == "size: M"

    def should_label_five_hundred_lines_as_medium(self) -> None:
        assert pr_labeler_derivation.derive_size_label(500, self.THRESHOLDS) == "size: M"

    def should_label_five_hundred_one_lines_as_large(self) -> None:
        assert pr_labeler_derivation.derive_size_label(501, self.THRESHOLDS) == "size: L"

    def should_label_one_thousand_lines_as_large(self) -> None:
        assert pr_labeler_derivation.derive_size_label(1000, self.THRESHOLDS) == "size: L"

    def should_label_one_thousand_one_lines_as_extra_large(self) -> None:
        assert pr_labeler_derivation.derive_size_label(1001, self.THRESHOLDS) == "size: XL"


class TestDeriveStatusLabel:
    def should_label_a_draft_pull_request_as_draft(self) -> None:
        assert pr_labeler_derivation.derive_status_label(True) == "status: draft"

    def should_label_a_ready_pull_request_as_needs_review(self) -> None:
        assert pr_labeler_derivation.derive_status_label(False) == "status: needs-review"


class TestHasHumanManagedStatusLabel:
    def should_detect_changes_requested_label(self) -> None:
        current_labels = frozenset({"status: changes-requested"})
        assert pr_labeler_derivation.has_human_managed_status_label(current_labels)

    def should_detect_needs_rebase_label(self) -> None:
        current_labels = frozenset({"status: needs-rebase"})
        assert pr_labeler_derivation.has_human_managed_status_label(current_labels)

    def should_detect_ready_to_merge_label(self) -> None:
        current_labels = frozenset({"status: ready-to-merge"})
        assert pr_labeler_derivation.has_human_managed_status_label(current_labels)

    def should_not_detect_an_automated_status_label(self) -> None:
        assert not pr_labeler_derivation.has_human_managed_status_label(frozenset({"status: draft"}))


class TestBuildStatusLabelPlan:
    def should_desire_draft_label_when_no_human_status_label_is_present(self) -> None:
        status_plan = pr_labeler_derivation.build_status_label_plan(True, frozenset())
        assert status_plan.desired_labels == frozenset({"status: draft"})
        assert status_plan.removable_labels == pr_labeler_derivation.ALL_AUTOMATED_STATUS_LABELS

    def should_leave_the_status_axis_untouched_when_changes_are_requested(self) -> None:
        current_labels = frozenset({"status: changes-requested", "type: bug"})
        status_plan = pr_labeler_derivation.build_status_label_plan(False, current_labels)
        assert status_plan.desired_labels == frozenset()
        assert status_plan.removable_labels == frozenset()


class TestMatchesTestPath:
    def should_match_a_tests_directory_segment(self) -> None:
        assert pr_labeler_derivation.matches_test_path("hooks/blocking/tdd_enforcer_parts/tests/foo.py")

    def should_match_a_test_underscore_prefix(self) -> None:
        assert pr_labeler_derivation.matches_test_path("hooks/blocking/test_pre_tool_use_dispatcher.py")

    def should_match_a_test_underscore_suffix(self) -> None:
        assert pr_labeler_derivation.matches_test_path("skills/split-pr/scripts/verify_plan_test.py")

    def should_match_a_dot_test_mjs_suffix(self) -> None:
        assert pr_labeler_derivation.matches_test_path("skills/theme-icon-set/scripts/palette.test.mjs")

    def should_not_match_an_unrelated_production_path(self) -> None:
        assert not pr_labeler_derivation.matches_test_path("hooks/blocking/pre_tool_use_dispatcher.py")


class TestDeriveAreaLabels:
    def should_label_the_state_what_is_rule_change_as_area_rules(self) -> None:
        changed_paths = [
            "packages/claude-dev-env/rules/CLAUDE.md",
            "packages/claude-dev-env/rules/state-what-is.md",
        ]
        assert pr_labeler_derivation.derive_area_labels(changed_paths, CLAUDE_DEV_ENV_CONFIG) == ["area: rules"]

    def should_rank_hooks_above_tests_by_match_count(self) -> None:
        changed_paths = [
            "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/candidate_paths.py",
            "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/config/tdd_enforcer_constants.py",
            "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/tests/test_candidate_paths.py",
        ]
        assert pr_labeler_derivation.derive_area_labels(changed_paths, CLAUDE_DEV_ENV_CONFIG) == [
            "area: hooks",
            "area: tests",
        ]

    def should_label_root_github_template_changes_as_area_ci(self) -> None:
        changed_paths = [
            ".github/ISSUE_TEMPLATE/bug-report.yml",
            ".github/ISSUE_TEMPLATE/feature-request.yml",
            ".github/labels.yml",
            ".github/workflows/sync-labels.yml",
        ]
        assert pr_labeler_derivation.derive_area_labels(changed_paths, CLAUDE_DEV_ENV_CONFIG) == ["area: ci"]

    def should_cap_at_three_labels_ordered_by_match_count(self) -> None:
        changed_paths = [
            "packages/claude-dev-env/hooks/blocking/pre_tool_use_dispatcher.py",
            "packages/claude-dev-env/hooks/blocking/agent_model_pin_blocker.py",
            "packages/claude-dev-env/hooks/hooks_constants/pre_tool_use_dispatcher_constants.py",
            "packages/claude-dev-env/hooks/hooks_constants/agent_model_pin_blocker_constants.py",
            "packages/claude-dev-env/skills/split-pr/SKILL.md",
            "packages/claude-dev-env/skills/split-pr/scripts/verify_plan.py",
            "packages/claude-dev-env/skills/split-pr/scripts/verify_slice_dependencies.py",
            "packages/claude-dev-env/agents/caveman.md",
            "packages/claude-dev-env/agents/code-advisor.md",
            "packages/claude-dev-env/rules/state-what-is.md",
            ".github/workflows/sync-labels.yml",
        ]
        assert pr_labeler_derivation.derive_area_labels(changed_paths, CLAUDE_DEV_ENV_CONFIG) == [
            "area: hooks",
            "area: skills",
            "area: agents",
        ]


class TestDeriveStackedLabel:
    def should_flag_a_pull_request_targeting_a_stacked_split_branch(self) -> None:
        assert pr_labeler_derivation.derive_stacked_label("split/601/01-backend-part1") == "stacked"

    def should_flag_a_pull_request_targeting_a_feature_branch(self) -> None:
        assert pr_labeler_derivation.derive_stacked_label("feat/split-pr-slice-collection") == "stacked"

    def should_not_flag_a_pull_request_targeting_main(self) -> None:
        assert pr_labeler_derivation.derive_stacked_label("main") is None

    def should_not_flag_a_pull_request_targeting_master(self) -> None:
        assert pr_labeler_derivation.derive_stacked_label("master") is None


class TestLoadLabelerConfig:
    def should_load_the_configured_path_prefix_to_strip(self) -> None:
        assert CLAUDE_DEV_ENV_CONFIG.path_prefix_to_strip == "packages/claude-dev-env/"

    def should_load_the_configured_size_thresholds(self) -> None:
        assert CLAUDE_DEV_ENV_CONFIG.size_thresholds.small_max_lines == 100

    def should_load_the_hooks_and_ci_area_mappings(self) -> None:
        area_label_by_path_prefix = {
            each_mapping.path_prefix: each_mapping.area_label
            for each_mapping in CLAUDE_DEV_ENV_CONFIG.area_mappings
        }
        assert area_label_by_path_prefix["hooks/"] == "area: hooks"
        assert area_label_by_path_prefix[".github/"] == "area: ci"


class TestComputeLabelDiff:
    def should_produce_an_empty_diff_when_current_labels_already_match(self) -> None:
        snapshot = pr_labeler_derivation.PullRequestSnapshot(
            title="fix(tdd-enforcer): count a split test family for any module",
            is_draft=True,
            base_branch_name="main",
            changed_line_count=115 + 11,
            changed_file_paths=(
                "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/candidate_paths.py",
                "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/config/tdd_enforcer_constants.py",
                "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/tests/test_candidate_paths.py",
            ),
            current_labels=frozenset(
                {"type: bug", "status: draft", "size: M", "area: hooks", "area: tests", "P1"}
            ),
        )
        label_diff = pr_labeler_derivation.compute_label_diff(snapshot, CLAUDE_DEV_ENV_CONFIG)
        assert label_diff.labels_to_add == frozenset()
        assert label_diff.labels_to_remove == frozenset()

    def should_add_missing_labels_and_remove_stale_ones_while_keeping_flags(self) -> None:
        snapshot = pr_labeler_derivation.PullRequestSnapshot(
            title="fix(tdd-enforcer): count a split test family for any module",
            is_draft=False,
            base_branch_name="main",
            changed_line_count=115 + 11,
            changed_file_paths=(
                "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/candidate_paths.py",
                "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/config/tdd_enforcer_constants.py",
                "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/tests/test_candidate_paths.py",
            ),
            current_labels=frozenset(
                {"type: chore", "status: draft", "size: S", "area: docs", "tech-debt"}
            ),
        )
        label_diff = pr_labeler_derivation.compute_label_diff(snapshot, CLAUDE_DEV_ENV_CONFIG)
        assert label_diff.labels_to_add == frozenset(
            {"type: bug", "status: needs-review", "size: M", "area: hooks", "area: tests"}
        )
        assert label_diff.labels_to_remove == frozenset(
            {"type: chore", "status: draft", "size: S", "area: docs"}
        )
        assert "tech-debt" not in label_diff.labels_to_remove

    def should_leave_the_status_axis_alone_when_changes_are_requested(self) -> None:
        snapshot = pr_labeler_derivation.PullRequestSnapshot(
            title="fix(tdd-enforcer): count a split test family for any module",
            is_draft=False,
            base_branch_name="main",
            changed_line_count=115 + 11,
            changed_file_paths=(
                "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/candidate_paths.py",
            ),
            current_labels=frozenset(
                {"type: bug", "status: changes-requested", "size: S", "area: hooks"}
            ),
        )
        label_diff = pr_labeler_derivation.compute_label_diff(snapshot, CLAUDE_DEV_ENV_CONFIG)
        assert "status: changes-requested" not in label_diff.labels_to_remove
        assert "status: draft" not in label_diff.labels_to_add
        assert "status: needs-review" not in label_diff.labels_to_add

    def should_clear_the_stacked_label_when_the_base_becomes_main(self) -> None:
        snapshot = pr_labeler_derivation.PullRequestSnapshot(
            title="chore(labels): add label file, sync workflow, and template label names",
            is_draft=False,
            base_branch_name="main",
            changed_line_count=211 + 2,
            changed_file_paths=(
                ".github/ISSUE_TEMPLATE/bug-report.yml",
                ".github/ISSUE_TEMPLATE/feature-request.yml",
                ".github/labels.yml",
                ".github/workflows/sync-labels.yml",
            ),
            current_labels=frozenset(
                {"stacked", "type: chore", "size: M", "status: needs-review", "area: ci"}
            ),
        )
        label_diff = pr_labeler_derivation.compute_label_diff(snapshot, CLAUDE_DEV_ENV_CONFIG)
        assert label_diff.labels_to_add == frozenset()
        assert label_diff.labels_to_remove == frozenset({"stacked"})

    def should_leave_hand_applied_type_and_area_labels_alone_when_neither_derives(self) -> None:
        snapshot = pr_labeler_derivation.PullRequestSnapshot(
            title="Update xhigh.md",
            is_draft=False,
            base_branch_name="main",
            changed_line_count=1 + 1,
            changed_file_paths=("packages/claude-dev-env/package.json",),
            current_labels=frozenset(
                {"type: docs", "status: needs-review", "size: XS", "area: docs"}
            ),
        )
        label_diff = pr_labeler_derivation.compute_label_diff(snapshot, CLAUDE_DEV_ENV_CONFIG)
        assert label_diff.labels_to_add == frozenset()
        assert label_diff.labels_to_remove == frozenset()


class TestIdempotence:
    def should_produce_no_further_changes_after_applying_the_first_diff(self) -> None:
        snapshot = pr_labeler_derivation.PullRequestSnapshot(
            title="feat(split-pr): fail a plan whose slice prefix is not closed under references",
            is_draft=True,
            base_branch_name="feat/split-pr-slice-collection",
            changed_line_count=1276 + 3,
            changed_file_paths=(
                "packages/claude-dev-env/skills/split-pr/SKILL.md",
                (
                    "packages/claude-dev-env/skills/split-pr/scripts/split_pr_scripts_constants"
                    "/config/dependency_constants.py"
                ),
                "packages/claude-dev-env/skills/split-pr/scripts/test_verify_slice_dependencies.py",
                "packages/claude-dev-env/skills/split-pr/scripts/verify_plan.py",
                "packages/claude-dev-env/skills/split-pr/scripts/verify_slice_dependencies.py",
            ),
            current_labels=frozenset(),
        )
        first_diff = pr_labeler_derivation.compute_label_diff(snapshot, CLAUDE_DEV_ENV_CONFIG)

        snapshot_after_first_run = dataclasses.replace(
            snapshot, current_labels=first_diff.labels_to_add
        )
        second_diff = pr_labeler_derivation.compute_label_diff(snapshot_after_first_run, CLAUDE_DEV_ENV_CONFIG)

        assert second_diff.labels_to_add == frozenset()
        assert second_diff.labels_to_remove == frozenset()


class TestFormatLabelDiffReport:
    def should_render_current_add_and_remove_labels_sorted(self) -> None:
        label_diff = pr_labeler_derivation.LabelDiff(
            labels_to_add=frozenset({"type: bug", "size: M"}),
            labels_to_remove=frozenset({"type: chore"}),
        )
        current_labels = frozenset({"P1", "area: hooks"})

        report_text = pr_labeler.format_label_diff_report(label_diff, current_labels)

        assert report_text == (
            "current labels: ['P1', 'area: hooks']\n"
            "labels to add: ['size: M', 'type: bug']\n"
            "labels to remove: ['type: chore']"
        )


class TestParseCommandLineArguments:
    def should_parse_required_arguments_and_default_dry_run_to_false(self) -> None:
        parsed_arguments = pr_labeler.parse_command_line_arguments(
            ["--repo", "jl-cmd/claude-dev-env", "--pr", "679", "--config", "pr_labeler_config.yml"]
        )
        assert parsed_arguments.repo == "jl-cmd/claude-dev-env"
        assert parsed_arguments.pr == 679
        assert parsed_arguments.config == "pr_labeler_config.yml"
        assert parsed_arguments.dry_run is False

    def should_set_dry_run_true_when_the_flag_is_passed(self) -> None:
        parsed_arguments = pr_labeler.parse_command_line_arguments(
            [
                "--repo",
                "jl-cmd/claude-dev-env",
                "--pr",
                "679",
                "--config",
                "pr_labeler_config.yml",
                "--dry-run",
            ]
        )
        assert parsed_arguments.dry_run is True


class TestRemoveLabelFromPullRequest:
    def should_call_the_delete_endpoint_with_the_url_encoded_label_name(self) -> None:
        recording_api_caller = RecordingApiCaller(canned_responses=[{"id": 1}])

        returned_response = pr_labeler_transport.remove_label_from_pull_request(
            "jl-cmd/claude-dev-env",
            679,
            "fake-token",
            "status: needs-review",
            call_api=recording_api_caller,
        )

        assert recording_api_caller.all_recorded_calls == [
            (
                (
                    "https://api.github.com/repos/jl-cmd/claude-dev-env/issues/679"
                    "/labels/status%3A%20needs-review"
                ),
                "fake-token",
                "DELETE",
                None,
            )
        ]
        assert returned_response == {"id": 1}


class TestApplyLabelDiff:
    def should_add_and_remove_labels_through_the_injected_caller_only(self) -> None:
        recording_api_caller = RecordingApiCaller()
        label_diff = pr_labeler_derivation.LabelDiff(
            labels_to_add=frozenset({"type: bug", "size: M"}),
            labels_to_remove=frozenset({"type: chore", "status: draft"}),
        )

        pr_labeler_transport.apply_label_diff(
            "jl-cmd/claude-dev-env",
            679,
            "fake-token",
            label_diff,
            call_api=recording_api_caller,
        )

        all_add_calls = [
            each_call for each_call in recording_api_caller.all_recorded_calls if each_call[2] == "POST"
        ]
        all_remove_calls = [
            each_call
            for each_call in recording_api_caller.all_recorded_calls
            if each_call[2] == "DELETE"
        ]

        assert all_add_calls == [
            (
                "https://api.github.com/repos/jl-cmd/claude-dev-env/issues/679/labels",
                "fake-token",
                "POST",
                {"labels": ["size: M", "type: bug"]},
            )
        ]
        assert {each_call[0] for each_call in all_remove_calls} == {
            "https://api.github.com/repos/jl-cmd/claude-dev-env/issues/679/labels/type%3A%20chore",
            "https://api.github.com/repos/jl-cmd/claude-dev-env/issues/679/labels/status%3A%20draft",
        }
        assert len(recording_api_caller.all_recorded_calls) == 3


class TestAddLabelsToPullRequest:
    def should_post_the_sorted_label_list_and_return_the_response(self) -> None:
        recording_api_caller = RecordingApiCaller(canned_responses=[{"id": 1}])

        returned_response = pr_labeler_transport.add_labels_to_pull_request(
            "jl-cmd/claude-dev-env",
            679,
            "fake-token",
            frozenset({"type: bug", "size: M"}),
            call_api=recording_api_caller,
        )

        assert recording_api_caller.all_recorded_calls == [
            (
                "https://api.github.com/repos/jl-cmd/claude-dev-env/issues/679/labels",
                "fake-token",
                "POST",
                {"labels": ["size: M", "type: bug"]},
            )
        ]
        assert returned_response == {"id": 1}

    def should_make_no_call_when_there_is_nothing_to_add(self) -> None:
        recording_api_caller = RecordingApiCaller()

        returned_response = pr_labeler_transport.add_labels_to_pull_request(
            "jl-cmd/claude-dev-env", 679, "fake-token", frozenset(), call_api=recording_api_caller
        )

        assert returned_response is None
        assert recording_api_caller.all_recorded_calls == []


class TestStripConfiguredPathPrefix:
    def should_strip_a_matching_prefix(self) -> None:
        stripped_path = pr_labeler_derivation.strip_configured_path_prefix(
            "packages/claude-dev-env/hooks/blocking/foo.py", "packages/claude-dev-env/"
        )
        assert stripped_path == "hooks/blocking/foo.py"

    def should_leave_a_non_matching_path_untouched(self) -> None:
        stripped_path = pr_labeler_derivation.strip_configured_path_prefix(
            ".github/workflows/foo.yml", "packages/claude-dev-env/"
        )
        assert stripped_path == ".github/workflows/foo.yml"


class TestAreaLabelsForPath:
    def should_return_the_matching_area_and_the_tests_label_for_a_test_path(self) -> None:
        matched_area_labels = pr_labeler_derivation.area_labels_for_path(
            "hooks/blocking/tdd_enforcer_parts/tests/test_candidate_paths.py",
            CLAUDE_DEV_ENV_CONFIG.area_mappings,
        )
        assert matched_area_labels == {"area: hooks", "area: tests"}

    def should_return_an_empty_set_for_an_unmatched_path(self) -> None:
        assert pr_labeler_derivation.area_labels_for_path("README.md", CLAUDE_DEV_ENV_CONFIG.area_mappings) == set()


class TestCountAreaLabelMatches:
    def should_count_matches_and_record_the_first_seen_index(self) -> None:
        changed_paths = [
            "packages/claude-dev-env/hooks/blocking/pre_tool_use_dispatcher.py",
            "packages/claude-dev-env/skills/split-pr/SKILL.md",
            "packages/claude-dev-env/hooks/blocking/agent_model_pin_blocker.py",
        ]
        match_count_by_area_label, first_seen_index_by_area_label = pr_labeler_derivation.count_area_label_matches(
            changed_paths, CLAUDE_DEV_ENV_CONFIG
        )
        assert match_count_by_area_label == {"area: hooks": 2, "area: skills": 1}
        assert first_seen_index_by_area_label == {"area: hooks": 0, "area: skills": 1}


class TestAreaLabelUniverse:
    def should_include_every_configured_area_label_and_the_tests_label(self) -> None:
        area_label_universe = pr_labeler_derivation.area_label_universe(CLAUDE_DEV_ENV_CONFIG)
        assert "area: hooks" in area_label_universe
        assert "area: ci" in area_label_universe
        assert pr_labeler_derivation.TESTS_AREA_LABEL in area_label_universe


class TestBuildTypeLabelPlan:
    def should_desire_the_mapped_type_label(self) -> None:
        type_plan = pr_labeler_derivation.build_type_label_plan(
            "fix(install): move stale skill files aside instead of leaving them installed"
        )
        assert type_plan.desired_labels == frozenset({"type: bug"})
        assert type_plan.removable_labels == pr_labeler_derivation.ALL_TYPE_LABELS

    def should_desire_no_label_for_an_unparseable_title(self) -> None:
        assert pr_labeler_derivation.build_type_label_plan("Update xhigh.md").desired_labels == frozenset()

    def should_leave_the_type_axis_untouched_for_an_unparseable_title(self) -> None:
        type_plan = pr_labeler_derivation.build_type_label_plan("Update xhigh.md")
        assert type_plan.desired_labels == frozenset()
        assert type_plan.removable_labels == frozenset()


class TestBuildSizeLabelPlan:
    def should_desire_the_derived_size_label(self) -> None:
        size_plan = pr_labeler_derivation.build_size_label_plan(126, CLAUDE_DEV_ENV_CONFIG.size_thresholds)
        assert size_plan.desired_labels == frozenset({"size: M"})
        assert size_plan.removable_labels == pr_labeler_derivation.ALL_SIZE_LABELS


class TestBuildAreaLabelPlan:
    def should_desire_the_derived_area_labels(self) -> None:
        changed_paths = [
            "packages/claude-dev-env/rules/CLAUDE.md",
            "packages/claude-dev-env/rules/state-what-is.md",
        ]
        area_plan = pr_labeler_derivation.build_area_label_plan(changed_paths, CLAUDE_DEV_ENV_CONFIG)
        assert area_plan.desired_labels == frozenset({"area: rules"})
        assert area_plan.removable_labels == pr_labeler_derivation.area_label_universe(CLAUDE_DEV_ENV_CONFIG)

    def should_leave_the_area_axis_untouched_when_no_path_matches(self) -> None:
        area_plan = pr_labeler_derivation.build_area_label_plan(
            ["packages/claude-dev-env/package.json"], CLAUDE_DEV_ENV_CONFIG
        )
        assert area_plan.desired_labels == frozenset()
        assert area_plan.removable_labels == frozenset()


class TestBuildStackedLabelPlan:
    def should_desire_the_stacked_label_for_a_non_main_base(self) -> None:
        stacked_plan = pr_labeler_derivation.build_stacked_label_plan("split/601/01-backend-part1")
        assert stacked_plan.desired_labels == frozenset({"stacked"})

    def should_desire_no_label_for_main(self) -> None:
        assert pr_labeler_derivation.build_stacked_label_plan("main").desired_labels == frozenset()


class TestDiffFromLabelPlans:
    def should_union_adds_and_removes_across_plans_while_keeping_untouched_flags(self) -> None:
        current_labels = frozenset({"type: chore", "tech-debt"})
        all_label_plans = [
            pr_labeler_derivation.LabelPlan(
                desired_labels=frozenset({"type: bug"}), removable_labels=pr_labeler_derivation.ALL_TYPE_LABELS
            ),
            pr_labeler_derivation.LabelPlan(
                desired_labels=frozenset({"stacked"}), removable_labels=frozenset({"stacked"})
            ),
        ]

        label_diff = pr_labeler_derivation.diff_from_label_plans(current_labels, all_label_plans)

        assert label_diff.labels_to_add == frozenset({"type: bug", "stacked"})
        assert label_diff.labels_to_remove == frozenset({"type: chore"})
        assert "tech-debt" not in label_diff.labels_to_remove


class TestCoerceToInt:
    def should_return_the_int_value_unchanged(self) -> None:
        assert pr_labeler_derivation.coerce_to_int(42) == 42


class TestLoadSizeThresholds:
    def should_build_size_thresholds_from_a_raw_mapping(self) -> None:
        size_thresholds = pr_labeler_derivation.load_size_thresholds(
            {"xs_max": 20, "s_max": 100, "m_max": 500, "l_max": 1000}
        )
        assert size_thresholds == pr_labeler_derivation.SizeThresholds(
            extra_small_max_lines=20,
            small_max_lines=100,
            medium_max_lines=500,
            large_max_lines=1000,
        )


class TestLoadAreaMappings:
    def should_build_area_mappings_from_a_raw_list(self) -> None:
        area_mappings = pr_labeler_derivation.load_area_mappings([{"path_prefix": "hooks/", "label": "area: hooks"}])
        assert area_mappings == (pr_labeler_derivation.AreaMapping(path_prefix="hooks/", area_label="area: hooks"),)


class TestBuildGithubApiRequest:
    def should_build_a_get_request_with_no_body(self) -> None:
        api_request = pr_labeler_transport.build_github_api_request(
            "https://api.github.com/repos/jl-cmd/claude-dev-env/pulls/679", "fake-token", "GET"
        )
        assert api_request.full_url == "https://api.github.com/repos/jl-cmd/claude-dev-env/pulls/679"
        assert api_request.get_method() == "GET"
        assert api_request.data is None
        assert api_request.get_header("Authorization") == "Bearer fake-token"

    def should_build_a_post_request_with_a_json_body(self) -> None:
        api_request = pr_labeler_transport.build_github_api_request(
            "https://api.github.com/repos/jl-cmd/claude-dev-env/issues/679/labels",
            "fake-token",
            "POST",
            {"labels": ["type: bug"]},
        )
        assert api_request.get_method() == "POST"
        assert api_request.data == b'{"labels": ["type: bug"]}'
        assert api_request.get_header("Content-type") == "application/json"


class TestCallGithubApi:
    def should_parse_the_json_body_the_injected_opener_returns(self) -> None:
        fake_url_opener = FakeUrlOpener(b'{"number": 679, "draft": true}')

        parsed_response = pr_labeler_transport.call_github_api(
            "https://api.github.com/repos/jl-cmd/claude-dev-env/pulls/679",
            "fake-token",
            "GET",
            None,
            open_url=fake_url_opener,
        )

        assert parsed_response == {"number": 679, "draft": True}
        assert len(fake_url_opener.all_opened_requests) == 1

    def should_return_none_for_an_empty_response_body(self) -> None:
        fake_url_opener = FakeUrlOpener(b"")

        parsed_response = pr_labeler_transport.call_github_api(
            "https://api.github.com/repos/jl-cmd/claude-dev-env/issues/679/labels/stacked",
            "fake-token",
            "DELETE",
            None,
            open_url=fake_url_opener,
        )

        assert parsed_response is None


class TestFetchPullRequestDetail:
    def should_return_the_pull_request_detail_the_injected_caller_provides(self) -> None:
        canned_detail = {"number": 679, "title": "fix(x): y", "draft": True}
        recording_api_caller = RecordingApiCaller(canned_responses=[canned_detail])

        pull_request_detail = pr_labeler_transport.fetch_pull_request_detail(
            "jl-cmd/claude-dev-env", 679, "fake-token", call_api=recording_api_caller
        )

        assert pull_request_detail == canned_detail
        assert recording_api_caller.all_recorded_calls == [
            (
                "https://api.github.com/repos/jl-cmd/claude-dev-env/pulls/679",
                "fake-token",
                "GET",
                None,
            )
        ]


class TestFetchAllChangedFilePaths:
    def should_paginate_until_a_short_page_ends_the_walk(self) -> None:
        full_first_page = [
            {"filename": f"file{each_file_index}.py"}
            for each_file_index in range(pr_labeler_transport.PULL_REQUEST_FILES_PAGE_SIZE)
        ]
        short_second_page = [{"filename": "last.py"}]
        recording_api_caller = RecordingApiCaller(canned_responses=[full_first_page, short_second_page])

        all_paths = pr_labeler_transport.fetch_all_changed_file_paths(
            "jl-cmd/claude-dev-env", 679, "fake-token", call_api=recording_api_caller
        )

        assert all_paths == tuple(
            f"file{each_file_index}.py" for each_file_index in range(pr_labeler_transport.PULL_REQUEST_FILES_PAGE_SIZE)
        ) + ("last.py",)
        assert len(recording_api_caller.all_recorded_calls) == 2
        assert recording_api_caller.all_recorded_calls[0][0].endswith("page=1")
        assert recording_api_caller.all_recorded_calls[1][0].endswith("page=2")


class TestExtractCurrentLabels:
    def should_extract_label_names_from_the_raw_labels_array(self) -> None:
        raw_pull_request_detail: dict[str, object] = {
            "labels": [{"name": "type: bug"}, {"name": "area: hooks"}]
        }
        assert pr_labeler_transport.extract_current_labels(raw_pull_request_detail) == frozenset(
            {"type: bug", "area: hooks"}
        )

    def should_return_an_empty_set_when_no_labels_key_is_present(self) -> None:
        assert pr_labeler_transport.extract_current_labels({}) == frozenset()


class TestBuildPullRequestSnapshot:
    def should_build_a_snapshot_from_a_raw_pull_request_detail(self) -> None:
        raw_pull_request_detail: dict[str, object] = {
            "title": "fix(tdd-enforcer): count a split test family for any module",
            "draft": True,
            "base": {"ref": "main"},
            "additions": 115,
            "deletions": 11,
            "labels": [{"name": "type: bug"}, {"name": "status: draft"}],
        }

        snapshot = pr_labeler_transport.build_pull_request_snapshot(
            raw_pull_request_detail,
            ("packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/candidate_paths.py",),
        )

        assert snapshot.title == "fix(tdd-enforcer): count a split test family for any module"
        assert snapshot.is_draft is True
        assert snapshot.base_branch_name == "main"
        assert snapshot.changed_line_count == 126
        assert snapshot.current_labels == frozenset({"type: bug", "status: draft"})


class TestFetchPullRequestSnapshot:
    def should_compose_the_detail_and_file_list_into_a_snapshot(self) -> None:
        canned_detail: dict[str, object] = {
            "title": "docs(rules): add state-what-is rule",
            "draft": False,
            "base": {"ref": "main"},
            "additions": 26,
            "deletions": 0,
            "labels": [],
        }
        canned_files_page = [
            {"filename": "packages/claude-dev-env/rules/CLAUDE.md"},
            {"filename": "packages/claude-dev-env/rules/state-what-is.md"},
        ]
        recording_api_caller = RecordingApiCaller(canned_responses=[canned_detail, canned_files_page])

        snapshot = pr_labeler_transport.fetch_pull_request_snapshot(
            "jl-cmd/claude-dev-env", 682, "fake-token", call_api=recording_api_caller
        )

        assert snapshot.title == "docs(rules): add state-what-is rule"
        assert snapshot.changed_line_count == 26
        assert snapshot.changed_file_paths == (
            "packages/claude-dev-env/rules/CLAUDE.md",
            "packages/claude-dev-env/rules/state-what-is.md",
        )
        assert len(recording_api_caller.all_recorded_calls) == 2
