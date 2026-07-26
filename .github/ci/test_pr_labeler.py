"""Specifications for the PR label derivation logic.

Every fixture below is either a real title, path, or line count pulled from
jl-cmd/claude-dev-env's own pull request history, or a synthetic-but-realistic
conventional-commit title for a prefix (style, build) that has never appeared
in this repository's history. The derivation functions under test never call
the GitHub API, so none of this needs mocking.
"""

import dataclasses
import io
import subprocess
import sys
import urllib.error
import urllib.parse
from collections.abc import Sequence
from email.message import Message
from pathlib import Path
from typing import ClassVar, Self

import pytest
import yaml

_CI_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_CI_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_CI_SCRIPTS_DIR))

import pr_labeler
import pr_labeler_derivation
import pr_labeler_transport

CLAUDE_DEV_ENV_CONFIG_PATH = _CI_SCRIPTS_DIR / "pr_labeler_config.yml"
CLAUDE_DEV_ENV_CONFIG = pr_labeler_derivation.load_labeler_config(CLAUDE_DEV_ENV_CONFIG_PATH)

TDD_ENFORCER_SNAPSHOT = pr_labeler_derivation.PullRequestSnapshot(
    title="fix(tdd-enforcer): count a split test family for any module",
    is_draft=True,
    base_branch_name="main",
    default_branch_name="main",
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


class RaisingApiCaller:
    """A GitHubApiCaller stand-in: raises a typed API error on every call it receives."""

    def __init__(self, status_code: int, response_body: str) -> None:
        self.status_code = status_code
        self.response_body = response_body

    def __call__(
        self, url: str, github_token: str, http_method: str, json_payload: object
    ) -> object:
        raise pr_labeler_transport.GitHubApiError(self.status_code, self.response_body)


class FlakyRemovalApiCaller:
    """A GitHubApiCaller stand-in whose DELETE calls fail for a chosen subset of labels."""

    def __init__(self, failing_status_code_by_label_name: dict[str, int]) -> None:
        self.failing_status_code_by_label_name = failing_status_code_by_label_name
        self.all_recorded_calls: list[tuple[str, str, str, object]] = []

    def __call__(
        self, url: str, github_token: str, http_method: str, json_payload: object
    ) -> object:
        self.all_recorded_calls.append((url, github_token, http_method, json_payload))
        if http_method != "DELETE":
            return None
        for each_label_name, each_status_code in self.failing_status_code_by_label_name.items():
            encoded_label_name = urllib.parse.quote(each_label_name, safe="")
            if encoded_label_name in url:
                raise pr_labeler_transport.GitHubApiError(each_status_code, "removal failed")
        return None


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


class FakeUrlOpenerThatRaisesHttpError:
    """A Callable[[Request], ReadableHttpResponse] stand-in that always raises HTTPError."""

    def __init__(self, status_code: int, response_body_bytes: bytes) -> None:
        self.status_code = status_code
        self.response_body_bytes = response_body_bytes

    def __call__(self, api_request: object) -> pr_labeler_transport.GithubApiConnection:
        raise urllib.error.HTTPError(
            url="https://api.github.com/repos/jl-cmd/claude-dev-env/pulls/679",
            code=self.status_code,
            msg="Forbidden",
            hdrs=Message(),
            fp=io.BytesIO(self.response_body_bytes),
        )


class TestDeriveTypeLabel:
    @pytest.mark.parametrize(
        ("pull_request_title", "expected_type_label"),
        [
            (
                "feat(split-pr): fail a plan whose slice prefix is not closed under references",
                "type: feature",
            ),
            (
                "fix(install): move stale skill files aside instead of leaving them installed",
                "type: bug",
            ),
            ("docs(rules): add state-what-is rule", "type: docs"),
            ("refactor(skills): move package-root _shared under skills/", "type: refactor"),
            ("style(hooks): apply ruff formatting across blocking hooks", "type: refactor"),
            ("test(split-pr): paired script and supersede coverage", "type: test"),
            ("ci: path-filter Python and JS suites on pull requests", "type: ci"),
            ("build(deps): bump esbuild to 0.24.2", "type: ci"),
            (
                "chore(labels): add label file, sync workflow, and template label names",
                "type: chore",
            ),
            ("revert: undo accidental merges API merge of #286 into main", "type: chore"),
            ("perf(code_rules_gate): batch blob reads with git cat-file --batch", "type: perf"),
            ("feat(api)!: drop the legacy v1 endpoint", "type: feature"),
        ],
    )
    def should_map_conventional_commit_prefix_to_type_label(
        self, pull_request_title: str, expected_type_label: str
    ) -> None:
        assert pr_labeler_derivation.derive_type_label(pull_request_title) == expected_type_label

    def should_return_none_for_an_unparseable_title(self) -> None:
        assert pr_labeler_derivation.derive_type_label("Update xhigh.md") is None

    def should_return_none_for_an_unmapped_conventional_commit_prefix(self) -> None:
        assert pr_labeler_derivation.derive_type_label("wip: pause the installer rewrite") is None

    def should_return_none_for_a_mapped_prefix_that_is_not_at_the_start(self) -> None:
        assert pr_labeler_derivation.derive_type_label('Revert "feat: add the v2 endpoint"') is None

    def should_reject_a_mapped_prefix_that_is_not_at_the_start_of_the_title(self) -> None:
        """Pins the `^` anchor directly, independent of `derive_type_label`'s `.match()` call.

        ::

            ok:   pattern with `^`     -> search("Revert \\"feat: ...\\"") finds nothing
            flag: pattern without `^`  -> search finds "feat:" at index 8

        `derive_type_label` only ever calls `.match()`, which is itself
        anchored to position 0 regardless of `^` — so this case alone would
        never catch the anchor going missing. Probing `.search()` directly
        pins the anchor's own behavior, so a future caller that reaches for
        `.search()` (a natural choice for scanning a longer commit body) does
        not silently pick up a mid-string conventional-commit prefix.
        """
        assert (
            pr_labeler_derivation.CONVENTIONAL_COMMIT_PREFIX_PATTERN.search(
                'Revert "feat: add the v2 endpoint"'
            )
            is None
        )


class TestDeriveSizeLabel:
    @pytest.mark.parametrize(
        ("changed_line_count", "expected_size_label"),
        [
            (20, "size: XS"),
            (21, "size: S"),
            (100, "size: S"),
            (101, "size: M"),
            (500, "size: M"),
            (501, "size: L"),
            (1000, "size: L"),
            (1001, "size: XL"),
        ],
    )
    def should_label_lines_at_each_threshold_boundary(
        self, changed_line_count: int, expected_size_label: str
    ) -> None:
        assert (
            pr_labeler_derivation.derive_size_label(
                changed_line_count, CLAUDE_DEV_ENV_CONFIG.size_thresholds
            )
            == expected_size_label
        )


class TestDeriveStatusLabel:
    def should_label_a_draft_pull_request_as_draft(self) -> None:
        assert pr_labeler_derivation.derive_status_label(True) == "status: draft"

    def should_label_a_ready_pull_request_as_needs_review(self) -> None:
        assert pr_labeler_derivation.derive_status_label(False) == "status: needs-review"


class TestHasHumanManagedStatusLabel:
    @pytest.mark.parametrize(
        ("current_labels", "expected_has_human_managed_status_label"),
        [
            (frozenset({"status: changes-requested"}), True),
            (frozenset({"status: needs-rebase"}), True),
            (frozenset({"status: ready-to-merge"}), True),
            (frozenset({"status: draft"}), False),
        ],
    )
    def should_detect_whether_a_human_managed_status_label_is_present(
        self, current_labels: frozenset[str], expected_has_human_managed_status_label: bool
    ) -> None:
        assert (
            pr_labeler_derivation.has_human_managed_status_label(current_labels)
            == expected_has_human_managed_status_label
        )


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
    @pytest.mark.parametrize(
        ("changed_file_path", "expected_matches_test_path"),
        [
            ("hooks/blocking/tdd_enforcer_parts/tests/foo.py", True),
            ("hooks/blocking/test_pre_tool_use_dispatcher.py", True),
            ("skills/split-pr/scripts/verify_plan_test.py", True),
            ("skills/theme-icon-set/scripts/palette.test.mjs", True),
            ("skills/theme-icon-set/scripts/palette.spec.mjs", True),
            ("hooks/blocking/pre_tool_use_dispatcher.py", False),
        ],
    )
    def should_match_test_shaped_paths_only(
        self, changed_file_path: str, expected_matches_test_path: bool
    ) -> None:
        assert (
            pr_labeler_derivation.matches_test_path(changed_file_path)
            == expected_matches_test_path
        )


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

    def should_break_a_four_way_tie_deterministically_at_the_cap(self) -> None:
        """Pins the A1 regression: a same-count tie must not flap across PYTHONHASHSEED.

        ::

            ok:   skills, rules, hooks each match once; hooks also matches tests
                  -> ["area: skills", "area: rules", "area: hooks"] every run
            flag: an unordered set feeding the count map could let the third
                  slot flip between "area: hooks" and "area: tests" run to run

        Four labels match this snapshot (skills, rules, hooks, tests), all
        tied at one match each, and the 3-label cap must drop exactly one of
        them — always the same one, regardless of PYTHONHASHSEED.
        """
        changed_paths = [
            "packages/claude-dev-env/skills/x.md",
            "packages/claude-dev-env/rules/y.md",
            "packages/claude-dev-env/hooks/test_z.py",
        ]
        assert pr_labeler_derivation.derive_area_labels(changed_paths, CLAUDE_DEV_ENV_CONFIG) == [
            "area: skills",
            "area: rules",
            "area: hooks",
        ]


class TestDeriveStackedLabel:
    @pytest.mark.parametrize(
        ("base_branch_name", "default_branch_name", "expected_stacked_label"),
        [
            ("split/601/01-backend-part1", "main", "stacked"),
            ("feat/split-pr-slice-collection", "main", "stacked"),
            ("main", "main", None),
            ("master", "master", None),
            ("main", "develop", "stacked"),
            ("develop", "develop", None),
        ],
    )
    def should_flag_a_pull_request_targeting_a_branch_other_than_the_repos_default(
        self, base_branch_name: str, default_branch_name: str, expected_stacked_label: str | None
    ) -> None:
        assert (
            pr_labeler_derivation.derive_stacked_label(base_branch_name, default_branch_name)
            == expected_stacked_label
        )


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


_REPO_ROOT_PATH = _CI_SCRIPTS_DIR.parent.parent


def _tracked_file_count_for_prefix(path_prefix: str) -> int:
    completed_git_ls_files = subprocess.run(
        ["git", "ls-files", "--", path_prefix],
        cwd=_REPO_ROOT_PATH,
        capture_output=True,
        text=True,
        check=True,
    )
    return len(completed_git_ls_files.stdout.splitlines())


class TestAreaMapPrefixesStayLive:
    """Guards the area map against a dead prefix: one that matches no tracked file.

    Round 3 fixed a dead prefix; nothing guarded against the next one. Every
    prefix resolves either bare or under the configured strip prefix, since
    this repo's area map targets paths inside `packages/claude-dev-env/`.
    """

    def should_resolve_every_configured_prefix_to_at_least_one_tracked_file(self) -> None:
        for each_mapping in CLAUDE_DEV_ENV_CONFIG.area_mappings:
            bare_match_count = _tracked_file_count_for_prefix(each_mapping.path_prefix)
            stripped_match_count = _tracked_file_count_for_prefix(
                CLAUDE_DEV_ENV_CONFIG.path_prefix_to_strip + each_mapping.path_prefix
            )
            assert bare_match_count > 0 or stripped_match_count > 0, each_mapping.path_prefix

    def should_declare_exactly_the_expected_prefix_set(self) -> None:
        all_declared_prefixes = frozenset(
            each_mapping.path_prefix for each_mapping in CLAUDE_DEV_ENV_CONFIG.area_mappings
        )
        assert all_declared_prefixes == frozenset(
            {
                "hooks/",
                "skills/",
                "agents/",
                "commands/",
                "rules/",
                "bin/",
                "scripts/",
                "_shared/",
                "docs/",
                "audit-rubrics/",
                ".github/",
            }
        )


class TestLabelPlanPostInit:
    def should_reject_empty_desired_with_non_empty_removable_when_built_by_a_future_axis(
        self,
    ) -> None:
        """A shape a real caller could produce: a sixth axis that hand-builds

        a `LabelPlan` instead of routing through `from_derivation`, and
        forgets to route its "no signal" case through `None` first.
        """
        with pytest.raises(ValueError):
            pr_labeler_derivation.LabelPlan(
                desired_labels=frozenset(), removable_labels=frozenset({"type: bug"})
            )

    def should_allow_the_legitimate_stacked_shape_through_the_factory(self) -> None:
        label_plan = pr_labeler_derivation.LabelPlan.from_derivation(
            frozenset(), frozenset({"stacked"})
        )
        assert label_plan.desired_labels == frozenset()
        assert label_plan.removable_labels == frozenset({"stacked"})
        assert label_plan.should_clear_stale_labels is True

    def should_return_an_untouchable_plan_for_a_none_derivation(self) -> None:
        label_plan = pr_labeler_derivation.LabelPlan.from_derivation(None, frozenset({"type: bug"}))
        assert label_plan.desired_labels == frozenset()
        assert label_plan.removable_labels == frozenset()
        assert label_plan.should_clear_stale_labels is False

    def should_run_post_init_on_the_production_path_through_from_derivation(self) -> None:
        """Production-path guard check.

        ::

            ok:   build_stacked_label_plan("main", "main") -> desired=∅,
                  removable={"stacked"}, should_clear_stale_labels=True

        `from_derivation` now constructs through `cls(...)` instead of
        `object.__new__`, so `__post_init__` runs on every axis plan it
        returns instead of being skipped entirely. The one legitimate
        empty-desired-with-removable shape, produced by a real builder,
        comes back correctly flagged rather than silently unvalidated.
        """
        stacked_plan = pr_labeler_derivation.build_stacked_label_plan("main", "main")
        assert stacked_plan.desired_labels == frozenset()
        assert stacked_plan.removable_labels == frozenset({pr_labeler_derivation.STACKED_LABEL})
        assert stacked_plan.should_clear_stale_labels is True


class TestComputeLabelDiff:
    def should_produce_an_empty_diff_when_current_labels_already_match(self) -> None:
        label_diff = pr_labeler_derivation.compute_label_diff(
            TDD_ENFORCER_SNAPSHOT, CLAUDE_DEV_ENV_CONFIG
        )
        assert label_diff.labels_to_add == frozenset()
        assert label_diff.labels_to_remove == frozenset()

    def should_add_missing_labels_and_remove_stale_ones_while_keeping_flags(self) -> None:
        snapshot = dataclasses.replace(
            TDD_ENFORCER_SNAPSHOT,
            is_draft=False,
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
        snapshot = dataclasses.replace(
            TDD_ENFORCER_SNAPSHOT,
            is_draft=False,
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
            default_branch_name="main",
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
            default_branch_name="main",
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
            default_branch_name="main",
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


class TestMain:
    def _canned_pull_request_detail(
        self, *, is_draft: bool, current_labels: list[str]
    ) -> dict[str, object]:
        return {
            "title": "fix(tdd-enforcer): count a split test family for any module",
            "draft": is_draft,
            "base": {"ref": "main", "repo": {"default_branch": "main"}},
            "additions": 115,
            "deletions": 11,
            "labels": [{"name": each_label_name} for each_label_name in current_labels],
        }

    _CANNED_FILES_PAGE: ClassVar[list[dict[str, object]]] = [
        {"filename": "packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/candidate_paths.py"}
    ]

    def should_dry_run_and_record_only_the_two_gets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(pr_labeler.GITHUB_TOKEN_ENVIRONMENT_VARIABLE_NAME, "fake-token")
        recording_api_caller = RecordingApiCaller(
            canned_responses=[
                self._canned_pull_request_detail(is_draft=True, current_labels=[]),
                self._CANNED_FILES_PAGE,
            ]
        )

        exit_code = pr_labeler.main(
            [
                "--repo",
                "jl-cmd/claude-dev-env",
                "--pr",
                "679",
                "--config",
                str(CLAUDE_DEV_ENV_CONFIG_PATH),
                "--dry-run",
            ],
            call_api=recording_api_caller,
        )

        assert exit_code == 0
        assert len(recording_api_caller.all_recorded_calls) == 2
        assert {each_call[2] for each_call in recording_api_caller.all_recorded_calls} == {"GET"}

    def should_apply_the_diff_and_record_post_and_delete_when_not_dry_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(pr_labeler.GITHUB_TOKEN_ENVIRONMENT_VARIABLE_NAME, "fake-token")
        recording_api_caller = RecordingApiCaller(
            canned_responses=[
                self._canned_pull_request_detail(
                    is_draft=False, current_labels=["type: chore", "P1", "epic"]
                ),
                self._CANNED_FILES_PAGE,
                {"id": 1},
            ]
        )

        exit_code = pr_labeler.main(
            [
                "--repo",
                "jl-cmd/claude-dev-env",
                "--pr",
                "679",
                "--config",
                str(CLAUDE_DEV_ENV_CONFIG_PATH),
            ],
            call_api=recording_api_caller,
        )

        assert exit_code == 0
        all_recorded_methods = [each_call[2] for each_call in recording_api_caller.all_recorded_calls]
        assert all_recorded_methods == ["GET", "GET", "POST", "DELETE"]

        post_call = recording_api_caller.all_recorded_calls[2]
        assert post_call[0] == "https://api.github.com/repos/jl-cmd/claude-dev-env/issues/679/labels"
        assert post_call[3] == {
            "labels": ["area: hooks", "size: M", "status: needs-review", "type: bug"]
        }

        delete_call = recording_api_caller.all_recorded_calls[3]
        assert delete_call[0] == (
            "https://api.github.com/repos/jl-cmd/claude-dev-env/issues/679/labels/type%3A%20chore"
        )

    def should_return_one_and_record_no_calls_when_github_token_is_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(pr_labeler.GITHUB_TOKEN_ENVIRONMENT_VARIABLE_NAME, raising=False)
        recording_api_caller = RecordingApiCaller()

        exit_code = pr_labeler.main(
            [
                "--repo",
                "jl-cmd/claude-dev-env",
                "--pr",
                "679",
                "--config",
                str(CLAUDE_DEV_ENV_CONFIG_PATH),
            ],
            call_api=recording_api_caller,
        )

        assert exit_code == 1
        assert recording_api_caller.all_recorded_calls == []

    def should_return_one_and_report_an_error_when_the_api_call_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(pr_labeler.GITHUB_TOKEN_ENVIRONMENT_VARIABLE_NAME, "fake-token")
        raising_api_caller = RaisingApiCaller(403, "rate limited")

        exit_code = pr_labeler.main(
            [
                "--repo",
                "jl-cmd/claude-dev-env",
                "--pr",
                "679",
                "--config",
                str(CLAUDE_DEV_ENV_CONFIG_PATH),
            ],
            call_api=raising_api_caller,
        )

        assert exit_code == 1


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

    def should_treat_a_404_on_delete_as_already_removed_and_continue(self) -> None:
        flaky_api_caller = FlakyRemovalApiCaller({"size: M": 404})
        label_diff = pr_labeler_derivation.LabelDiff(
            labels_to_add=frozenset(),
            labels_to_remove=frozenset({"size: M", "status: draft", "type: chore"}),
        )

        pr_labeler_transport.apply_label_diff(
            "jl-cmd/claude-dev-env", 679, "fake-token", label_diff, call_api=flaky_api_caller
        )

        all_delete_calls = [
            each_call for each_call in flaky_api_caller.all_recorded_calls if each_call[2] == "DELETE"
        ]
        assert len(all_delete_calls) == 3

    def should_attempt_every_removal_then_raise_when_a_non_404_failure_occurs(self) -> None:
        flaky_api_caller = FlakyRemovalApiCaller({"size: M": 500})
        label_diff = pr_labeler_derivation.LabelDiff(
            labels_to_add=frozenset(),
            labels_to_remove=frozenset({"size: M", "status: draft", "type: chore"}),
        )

        with pytest.raises(pr_labeler_transport.GitHubApiError):
            pr_labeler_transport.apply_label_diff(
                "jl-cmd/claude-dev-env", 679, "fake-token", label_diff, call_api=flaky_api_caller
            )

        all_delete_calls = [
            each_call for each_call in flaky_api_caller.all_recorded_calls if each_call[2] == "DELETE"
        ]
        assert len(all_delete_calls) == 3


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
        assert matched_area_labels == ["area: hooks", "area: tests"]

    def should_return_an_empty_list_for_an_unmatched_path(self) -> None:
        assert pr_labeler_derivation.area_labels_for_path("README.md", CLAUDE_DEV_ENV_CONFIG.area_mappings) == []

    def should_preserve_config_declaration_order_for_overlapping_prefixes(self) -> None:
        """Pins the within-path order the list comprehension guarantees over a set.

        ::

            ok:   config declares docs/, docs/api/, docs/api/v2/,
                  docs/api/v2/schemas/ in that order
                  -> ["area: docs", "area: api", "area: v2", "area: schemas"]
                     every run
            flag: a set comprehension in area_labels_for_path
                  -> the four labels come back in a PYTHONHASHSEED-dependent
                     order

        A two-element fixture only catches this at half of all hash seeds (a
        two-element set has a coin-flip chance of preserving declaration
        order by accident). Four overlapping prefixes drop the odds of an
        accidental pass to 1 in 24 (4!) per seed, so a set-comprehension
        regression fails reliably rather than flapping. Neither repo's real
        area map has overlapping top-level prefixes today, so this builds
        its own config to exercise the case directly.
        """
        overlapping_area_mappings = (
            pr_labeler_derivation.AreaMapping(path_prefix="docs/", area_label="area: docs"),
            pr_labeler_derivation.AreaMapping(path_prefix="docs/api/", area_label="area: api"),
            pr_labeler_derivation.AreaMapping(path_prefix="docs/api/v2/", area_label="area: v2"),
            pr_labeler_derivation.AreaMapping(
                path_prefix="docs/api/v2/schemas/", area_label="area: schemas"
            ),
        )
        assert pr_labeler_derivation.area_labels_for_path(
            "docs/api/v2/schemas/x.md", overlapping_area_mappings
        ) == ["area: docs", "area: api", "area: v2", "area: schemas"]


class TestCountAreaLabelMatches:
    def should_count_matches_across_every_changed_path(self) -> None:
        changed_paths = [
            "packages/claude-dev-env/hooks/blocking/pre_tool_use_dispatcher.py",
            "packages/claude-dev-env/skills/split-pr/SKILL.md",
            "packages/claude-dev-env/hooks/blocking/agent_model_pin_blocker.py",
        ]
        match_count_by_area_label = pr_labeler_derivation.count_area_label_matches(
            changed_paths, CLAUDE_DEV_ENV_CONFIG
        )
        assert match_count_by_area_label == {"area: hooks": 2, "area: skills": 1}


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

    def should_leave_the_type_axis_untouched_for_an_unmapped_prefix(self) -> None:
        type_plan = pr_labeler_derivation.build_type_label_plan("wip: pause the installer rewrite")
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
    def should_desire_the_stacked_label_for_a_non_default_base(self) -> None:
        stacked_plan = pr_labeler_derivation.build_stacked_label_plan(
            "split/601/01-backend-part1", "main"
        )
        assert stacked_plan.desired_labels == frozenset({"stacked"})

    def should_desire_no_label_for_the_repos_default_branch(self) -> None:
        assert pr_labeler_derivation.build_stacked_label_plan("main", "main").desired_labels == frozenset()

    def should_still_be_able_to_clear_a_stale_stacked_label_for_the_default_branch(self) -> None:
        stacked_plan = pr_labeler_derivation.build_stacked_label_plan("main", "main")
        assert stacked_plan.removable_labels == frozenset({"stacked"})


class TestDiffFromLabelPlans:
    def should_union_adds_and_removes_across_plans_while_keeping_untouched_flags(self) -> None:
        current_labels = frozenset({"type: chore", "tech-debt"})
        all_label_plans = [
            pr_labeler_derivation.LabelPlan(
                desired_labels=frozenset({"type: bug"}), removable_labels=pr_labeler_derivation.ALL_TYPE_LABELS
            ),
            pr_labeler_derivation.LabelPlan.from_derivation(
                frozenset({"stacked"}), frozenset({"stacked"})
            ),
        ]

        label_diff = pr_labeler_derivation.diff_from_label_plans(current_labels, all_label_plans)

        assert label_diff.labels_to_add == frozenset({"type: bug", "stacked"})
        assert label_diff.labels_to_remove == frozenset({"type: chore"})
        assert "tech-debt" not in label_diff.labels_to_remove


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


class TestCallGithubApiHttpError:
    def should_translate_an_http_error_into_a_typed_api_error(self) -> None:
        fake_url_opener = FakeUrlOpenerThatRaisesHttpError(403, b'{"message": "rate limited"}')

        with pytest.raises(pr_labeler_transport.GitHubApiError) as raised_error:
            pr_labeler_transport.call_github_api(
                "https://api.github.com/repos/jl-cmd/claude-dev-env/pulls/679",
                "fake-token",
                "GET",
                None,
                open_url=fake_url_opener,
            )

        assert raised_error.value.status_code == 403
        assert "rate limited" in raised_error.value.failure_detail_text


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


class TestDefaultBranchNameFromBaseRef:
    def should_read_the_configured_default_branch(self) -> None:
        base_ref_info: dict[str, object] = {"ref": "feat/x", "repo": {"default_branch": "develop"}}
        assert pr_labeler_transport.default_branch_name_from_base_ref(base_ref_info) == "develop"

    def should_fall_back_to_main_when_the_repo_object_is_missing(self) -> None:
        base_ref_info: dict[str, object] = {"ref": "feat/x"}
        assert pr_labeler_transport.default_branch_name_from_base_ref(base_ref_info) == "main"

    def should_fall_back_to_main_when_default_branch_is_missing(self) -> None:
        base_ref_info: dict[str, object] = {"ref": "feat/x", "repo": {}}
        assert pr_labeler_transport.default_branch_name_from_base_ref(base_ref_info) == "main"


class TestBuildPullRequestSnapshot:
    def should_build_a_snapshot_from_a_raw_pull_request_detail(self) -> None:
        raw_pull_request_detail: dict[str, object] = {
            "title": "fix(tdd-enforcer): count a split test family for any module",
            "draft": True,
            "base": {"ref": "main", "repo": {"default_branch": "main"}},
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
        assert snapshot.default_branch_name == "main"
        assert snapshot.changed_line_count == 126
        assert snapshot.current_labels == frozenset({"type: bug", "status: draft"})


class TestFetchPullRequestSnapshot:
    def should_compose_the_detail_and_file_list_into_a_snapshot(self) -> None:
        canned_detail: dict[str, object] = {
            "title": "docs(rules): add state-what-is rule",
            "draft": False,
            "base": {"ref": "main", "repo": {"default_branch": "main"}},
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


def _declared_label_names() -> frozenset[str]:
    labels_yml_path = _CI_SCRIPTS_DIR.parent / "labels.yml"
    raw_labels = yaml.safe_load(labels_yml_path.read_text(encoding="utf-8"))
    return frozenset(str(each_entry["name"]) for each_entry in raw_labels)


class TestLabelVocabularyMatchesDeclaredLabels:
    def should_declare_every_label_the_labeler_can_add_or_remove(self) -> None:
        declared_label_names = _declared_label_names()
        all_labeler_managed_labels = (
            pr_labeler_derivation.ALL_TYPE_LABELS
            | pr_labeler_derivation.ALL_SIZE_LABELS
            | pr_labeler_derivation.ALL_AUTOMATED_STATUS_LABELS
            | pr_labeler_derivation.ALL_HUMAN_MANAGED_STATUS_LABELS
            | pr_labeler_derivation.area_label_universe(CLAUDE_DEV_ENV_CONFIG)
            | frozenset({pr_labeler_derivation.STACKED_LABEL})
        )
        assert all_labeler_managed_labels <= declared_label_names


def _semantic_pull_request_step(all_steps: list[dict[str, object]]) -> dict[str, object]:
    for each_step in all_steps:
        uses_value = each_step.get("uses", "")
        assert isinstance(uses_value, str)
        if "action-semantic-pull-request" in uses_value:
            return each_step
    raise AssertionError("no step uses action-semantic-pull-request")


def _pr_check_conventional_commit_types() -> frozenset[str]:
    pr_check_workflow_path = _CI_SCRIPTS_DIR.parent / "workflows" / "pr-check.yml"
    raw_workflow = yaml.safe_load(pr_check_workflow_path.read_text(encoding="utf-8"))
    semantic_pull_request_step = _semantic_pull_request_step(raw_workflow["jobs"]["validate"]["steps"])
    types_block = semantic_pull_request_step["with"]["types"]
    return frozenset(each_line.strip() for each_line in types_block.splitlines() if each_line.strip())


class TestTypeLabelMapCoversPrCheckTypes:
    def should_map_every_type_the_pr_title_check_enforces(self) -> None:
        all_pr_check_types = _pr_check_conventional_commit_types()
        assert all_pr_check_types <= pr_labeler_derivation.ALL_TYPE_LABELS_BY_COMMIT_PREFIX.keys()


def _pr_labeler_workflow_steps() -> list[dict[str, object]]:
    pr_labeler_workflow_path = _CI_SCRIPTS_DIR.parent / "workflows" / "pr-labeler.yml"
    raw_workflow = yaml.safe_load(pr_labeler_workflow_path.read_text(encoding="utf-8"))
    return raw_workflow["jobs"]["label"]["steps"]


def _pr_labeler_step(all_steps: list[dict[str, object]]) -> dict[str, object]:
    for each_step in all_steps:
        run_value = each_step.get("run", "")
        assert isinstance(run_value, str)
        if "pr_labeler.py" in run_value:
            return each_step
    raise AssertionError("no step runs pr_labeler.py")


class TestPrLabelerWorkflowContract:
    """Pins the workflow that actually drives `pr_labeler.py` in production.

    Every `TestMain` case sets the `GITHUB_TOKEN` environment variable
    through `pr_labeler.GITHUB_TOKEN_ENVIRONMENT_VARIABLE_NAME`, so those
    tests validate the constant against itself and would stay green even if
    the constant and the workflow's `env:` key drifted apart. This class
    reads `pr-labeler.yml` directly instead, so a typo in the workflow's own
    `GITHUB_TOKEN:` key fails here regardless of what the Python constant says.
    """

    def should_set_the_configured_token_env_var_in_the_labeler_steps_environment(self) -> None:
        """Pins both sides of the token name against each other, not a hardcoded literal.

        ::

            ok:   constant == "GITHUB_TOKEN", workflow env has "GITHUB_TOKEN"  -> pass
            flag: constant renamed to "GH_TOKEN", workflow still sets
                  "GITHUB_TOKEN"                                              -> fails here

        Asserting a literal `"GITHUB_TOKEN"` only catches a typo on the
        workflow side. Every labeler run reads the token through
        `pr_labeler.GITHUB_TOKEN_ENVIRONMENT_VARIABLE_NAME`, so a rename of
        that constant with no matching workflow update is the failure this
        finding actually describes, and only comparing the two live sources
        against each other catches it.
        """
        labeler_step = _pr_labeler_step(_pr_labeler_workflow_steps())
        assert pr_labeler.GITHUB_TOKEN_ENVIRONMENT_VARIABLE_NAME in labeler_step.get("env", {})

    def should_run_the_labeler_script_at_its_known_repository_path(self) -> None:
        labeler_step = _pr_labeler_step(_pr_labeler_workflow_steps())
        assert ".github/ci/pr_labeler.py" in labeler_step["run"]

    def should_pass_a_config_argument_that_is_the_suite_config(self) -> None:
        """Pins the workflow's `--config` path to the exact file the suite loads, not just any file.

        ::

            ok:   workflow --config resolves to CLAUDE_DEV_ENV_CONFIG_PATH  -> pass
            flag: workflow --config points at a different, still-existing
                  config file (a new downstream config, or a moved file
                  updated only in the workflow)                            -> fails here

        An existence check alone passes for any config file, so a workflow
        drifted onto the wrong config would still read as correct while
        every area, size, and prefix-liveness test kept validating the old
        config through the module-level path. `load_labeler_config` already
        fails collection when the file is missing, so identity subsumes
        the existence check for free.
        """
        labeler_step = _pr_labeler_step(_pr_labeler_workflow_steps())
        config_flag_parts = labeler_step["run"].split("--config", 1)
        assert len(config_flag_parts) == 2, "labeler step passes no --config"
        assert config_flag_parts[1].split(), "labeler step passes --config with no path"
        configured_config_path_token = config_flag_parts[1].split()[0]
        configured_config_path = _CI_SCRIPTS_DIR.parent.parent / configured_config_path_token
        assert configured_config_path.resolve() == CLAUDE_DEV_ENV_CONFIG_PATH.resolve()
