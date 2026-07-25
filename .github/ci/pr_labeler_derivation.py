"""Pure derivation for the five PR label axes: type, size, status, area, stacked.

::

    ok:   title="fix(install): ..."           -> derive_type_label -> "type: bug"
    ok:   changed_line_count=126, thresholds   -> derive_size_label -> "size: M"
    flag: changed_line_count=100, thresholds   -> derive_size_label -> "size: S" (boundary)

Every function here is pure: it takes a title, a line count, a path list, or a
`PullRequestSnapshot`, and returns labels or a `LabelDiff`. None of it touches
the network — the GitHub API transport lives in `pr_labeler_transport.py`
beside this module, and the CLI entrypoint lives in `pr_labeler.py`.
"""

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

_repo_root_path = str(Path(__file__).resolve().parents[2])
if _repo_root_path not in sys.path:
    sys.path.insert(0, _repo_root_path)

from config.pr_labeler_constants import (
    ALL_AUTOMATED_STATUS_LABELS,
    ALL_DEFAULT_BASE_BRANCH_NAMES,
    ALL_HUMAN_MANAGED_STATUS_LABELS,
    ALL_SIZE_LABELS,
    ALL_TEST_PATH_PATTERNS,
    ALL_TYPE_LABELS,
    ALL_TYPE_LABELS_BY_COMMIT_PREFIX,
    CONVENTIONAL_COMMIT_PREFIX_PATTERN,
    MAXIMUM_AREA_LABELS,
    SIZE_LABEL_EXTRA_LARGE,
    SIZE_LABEL_EXTRA_SMALL,
    SIZE_LABEL_LARGE,
    SIZE_LABEL_MEDIUM,
    SIZE_LABEL_SMALL,
    STACKED_LABEL,
    STATUS_LABEL_DRAFT,
    STATUS_LABEL_NEEDS_REVIEW,
    TESTS_AREA_LABEL,
)

__all__ = [
    "ALL_AUTOMATED_STATUS_LABELS",
    "ALL_SIZE_LABELS",
    "ALL_TYPE_LABELS",
    "TESTS_AREA_LABEL",
]


@dataclass(frozen=True)
class SizeThresholds:
    extra_small_max_lines: int
    small_max_lines: int
    medium_max_lines: int
    large_max_lines: int


@dataclass(frozen=True)
class AreaMapping:
    path_prefix: str
    area_label: str


@dataclass(frozen=True)
class LabelerConfig:
    path_prefix_to_strip: str
    area_mappings: tuple[AreaMapping, ...]
    size_thresholds: SizeThresholds


@dataclass(frozen=True)
class PullRequestSnapshot:
    title: str
    is_draft: bool
    base_branch_name: str
    changed_line_count: int
    changed_file_paths: tuple[str, ...]
    current_labels: frozenset[str]


@dataclass(frozen=True)
class LabelPlan:
    desired_labels: frozenset[str]
    removable_labels: frozenset[str]


@dataclass(frozen=True)
class LabelDiff:
    labels_to_add: frozenset[str]
    labels_to_remove: frozenset[str]


def derive_type_label(pull_request_title: str) -> str | None:
    """Return the `type:` label for a PR title, or None when it has no conventional-commit prefix.

    ::

        ok:   "fix(install): move stale skill files"  -> "type: bug"
        flag: "Update xhigh.md"                        -> None (no matching prefix)

    Args:
        pull_request_title: The pull request's title.

    Returns:
        The mapped `type:` label, or None when the prefix is missing or unmapped.
    """
    matched_prefix = CONVENTIONAL_COMMIT_PREFIX_PATTERN.match(pull_request_title)
    if matched_prefix is None:
        return None
    return ALL_TYPE_LABELS_BY_COMMIT_PREFIX.get(matched_prefix.group(1))


def derive_size_label(changed_line_count: int, size_thresholds: SizeThresholds) -> str:
    """Return the `size:` label for a changed-line count against the configured thresholds.

    Args:
        changed_line_count: Total additions plus deletions for the pull request.
        size_thresholds: The per-repo XS/S/M/L boundary values.

    Returns:
        One of the five `size:` labels, from XS up to XL.
    """
    if changed_line_count <= size_thresholds.extra_small_max_lines:
        return SIZE_LABEL_EXTRA_SMALL
    if changed_line_count <= size_thresholds.small_max_lines:
        return SIZE_LABEL_SMALL
    if changed_line_count <= size_thresholds.medium_max_lines:
        return SIZE_LABEL_MEDIUM
    if changed_line_count <= size_thresholds.large_max_lines:
        return SIZE_LABEL_LARGE
    return SIZE_LABEL_EXTRA_LARGE


def derive_status_label(is_pull_request_draft: bool) -> str:
    return STATUS_LABEL_DRAFT if is_pull_request_draft else STATUS_LABEL_NEEDS_REVIEW


def has_human_managed_status_label(all_current_labels: frozenset[str]) -> bool:
    return bool(all_current_labels & ALL_HUMAN_MANAGED_STATUS_LABELS)


def derive_stacked_label(base_branch_name: str) -> str | None:
    if base_branch_name in ALL_DEFAULT_BASE_BRANCH_NAMES:
        return None
    return STACKED_LABEL


def matches_test_path(changed_file_path: str) -> bool:
    return any(each_pattern.search(changed_file_path) for each_pattern in ALL_TEST_PATH_PATTERNS)


def strip_configured_path_prefix(changed_file_path: str, path_prefix_to_strip: str) -> str:
    if path_prefix_to_strip and changed_file_path.startswith(path_prefix_to_strip):
        return changed_file_path[len(path_prefix_to_strip) :]
    return changed_file_path


def area_labels_for_path(
    stripped_path: str, all_area_mappings: tuple[AreaMapping, ...]
) -> set[str]:
    """Every area-map entry whose prefix matches, plus the tests label for a test-shaped path.

    Args:
        stripped_path: The changed-file path with the repo's configured prefix removed.
        all_area_mappings: The area-map entries to match the path's prefix against.

    Returns:
        The set of area labels the path contributes to.
    """
    matched_area_labels = {
        each_mapping.area_label
        for each_mapping in all_area_mappings
        if stripped_path.startswith(each_mapping.path_prefix)
    }
    if matches_test_path(stripped_path):
        matched_area_labels.add(TESTS_AREA_LABEL)
    return matched_area_labels


def count_area_label_matches(
    all_changed_file_paths: Sequence[str], config: LabelerConfig
) -> tuple[dict[str, int], dict[str, int]]:
    """Count area-label matches across every changed path, and record first appearance.

    Args:
        all_changed_file_paths: Every path the pull request changed.
        config: The area map and path-prefix settings to match against.

    Returns:
        A pair of maps keyed by area label: match count, and the index of the
        first changed path that matched it.
    """
    match_count_by_area_label: dict[str, int] = {}
    first_seen_index_by_area_label: dict[str, int] = {}
    for each_file_index, each_changed_file_path in enumerate(all_changed_file_paths):
        stripped_path = strip_configured_path_prefix(
            each_changed_file_path, config.path_prefix_to_strip
        )
        for each_area_label in area_labels_for_path(stripped_path, config.area_mappings):
            match_count_by_area_label[each_area_label] = (
                match_count_by_area_label.get(each_area_label, 0) + 1
            )
            first_seen_index_by_area_label.setdefault(each_area_label, each_file_index)
    return match_count_by_area_label, first_seen_index_by_area_label


def derive_area_labels(all_changed_file_paths: Sequence[str], config: LabelerConfig) -> list[str]:
    """Up to MAXIMUM_AREA_LABELS labels, most-matched first, ties broken by first appearance.

    Args:
        all_changed_file_paths: Every path the pull request changed.
        config: The area map and path-prefix settings to match against.

    Returns:
        The ranked area labels, capped at the configured maximum.
    """
    match_count_by_area_label, first_seen_index_by_area_label = count_area_label_matches(
        all_changed_file_paths, config
    )
    ranked_area_labels = sorted(
        match_count_by_area_label,
        key=lambda each_label: (
            -match_count_by_area_label[each_label],
            first_seen_index_by_area_label[each_label],
        ),
    )
    return ranked_area_labels[:MAXIMUM_AREA_LABELS]


def area_label_universe(config: LabelerConfig) -> frozenset[str]:
    configured_labels = {each_mapping.area_label for each_mapping in config.area_mappings}
    return frozenset(configured_labels | {TESTS_AREA_LABEL})


def build_type_label_plan(pull_request_title: str) -> LabelPlan:
    maybe_type_label = derive_type_label(pull_request_title)
    desired_labels = frozenset({maybe_type_label}) if maybe_type_label else frozenset()
    return LabelPlan(desired_labels=desired_labels, removable_labels=ALL_TYPE_LABELS)


def build_size_label_plan(changed_line_count: int, size_thresholds: SizeThresholds) -> LabelPlan:
    size_label = derive_size_label(changed_line_count, size_thresholds)
    return LabelPlan(desired_labels=frozenset({size_label}), removable_labels=ALL_SIZE_LABELS)


def build_status_label_plan(
    is_pull_request_draft: bool, all_current_labels: frozenset[str]
) -> LabelPlan:
    """Build the status axis's plan, frozen once a human status label is present.

    Args:
        is_pull_request_draft: Whether the pull request is currently a draft.
        all_current_labels: Every label the pull request carries right now.

    Returns:
        A plan desiring draft/needs-review, or an empty plan when a human
        status label (changes-requested, needs-rebase, ready-to-merge) is set.
    """
    if has_human_managed_status_label(all_current_labels):
        return LabelPlan(desired_labels=frozenset(), removable_labels=frozenset())
    status_label = derive_status_label(is_pull_request_draft)
    return LabelPlan(
        desired_labels=frozenset({status_label}), removable_labels=ALL_AUTOMATED_STATUS_LABELS
    )


def build_area_label_plan(all_changed_file_paths: Sequence[str], config: LabelerConfig) -> LabelPlan:
    """Build the area axis's plan: the ranked area labels, capped at three.

    Args:
        all_changed_file_paths: Every path the pull request changed.
        config: The area map and path-prefix settings to match against.

    Returns:
        A plan desiring the ranked area labels and able to remove any label in
        the repo's configured area vocabulary.
    """
    area_labels = derive_area_labels(all_changed_file_paths, config)
    return LabelPlan(
        desired_labels=frozenset(area_labels), removable_labels=area_label_universe(config)
    )


def build_stacked_label_plan(base_branch_name: str) -> LabelPlan:
    maybe_stacked_label = derive_stacked_label(base_branch_name)
    desired_labels = frozenset({maybe_stacked_label}) if maybe_stacked_label else frozenset()
    return LabelPlan(desired_labels=desired_labels, removable_labels=frozenset({STACKED_LABEL}))


def diff_from_label_plans(
    all_current_labels: frozenset[str], all_label_plans: Sequence[LabelPlan]
) -> LabelDiff:
    """Union every axis plan's adds and removes into one label diff.

    ::

        ok:   desired not in current               -> added
        ok:   current in removable, not in desired  -> removed
        flag: current in a flag outside every axis  -> untouched (never removed)

    Args:
        all_current_labels: Every label the pull request carries right now.
        all_label_plans: One `LabelPlan` per axis (type, size, status, area, stacked).

    Returns:
        The combined `LabelDiff` across every axis.
    """
    all_labels_to_add: set[str] = set()
    all_labels_to_remove: set[str] = set()
    for each_plan in all_label_plans:
        all_labels_to_add |= each_plan.desired_labels - all_current_labels
        all_labels_to_remove |= (
            all_current_labels & each_plan.removable_labels
        ) - each_plan.desired_labels
    return LabelDiff(
        labels_to_add=frozenset(all_labels_to_add),
        labels_to_remove=frozenset(all_labels_to_remove),
    )


def compute_label_diff(snapshot: PullRequestSnapshot, config: LabelerConfig) -> LabelDiff:
    """Compute the full five-axis label diff for one pull request snapshot.

    Args:
        snapshot: The pull request's title, draft state, base branch, changed
            line count, changed paths, and current labels.
        config: The area map and size thresholds to derive labels against.

    Returns:
        The labels to add and the labels to remove across all five axes.
    """
    all_label_plans = [
        build_type_label_plan(snapshot.title),
        build_size_label_plan(snapshot.changed_line_count, config.size_thresholds),
        build_status_label_plan(snapshot.is_draft, snapshot.current_labels),
        build_area_label_plan(snapshot.changed_file_paths, config),
        build_stacked_label_plan(snapshot.base_branch_name),
    ]
    return diff_from_label_plans(snapshot.current_labels, all_label_plans)


def coerce_to_int(value: object) -> int:
    assert isinstance(value, int)
    return value


def load_size_thresholds(all_raw_thresholds: dict[str, object]) -> SizeThresholds:
    """Build typed size thresholds from the raw `size_thresholds` config mapping.

    Args:
        all_raw_thresholds: The parsed `size_thresholds` block from the YAML config.

    Returns:
        The typed `SizeThresholds` the raw mapping describes.
    """
    return SizeThresholds(
        extra_small_max_lines=coerce_to_int(all_raw_thresholds["xs_max"]),
        small_max_lines=coerce_to_int(all_raw_thresholds["s_max"]),
        medium_max_lines=coerce_to_int(all_raw_thresholds["m_max"]),
        large_max_lines=coerce_to_int(all_raw_thresholds["l_max"]),
    )


def load_area_mappings(all_raw_area_map: list[dict[str, object]]) -> tuple[AreaMapping, ...]:
    """Build typed area mappings from the raw `area_map` config list.

    Args:
        all_raw_area_map: The parsed `area_map` block from the YAML config.

    Returns:
        One `AreaMapping` per entry, in the config's declared order.
    """
    return tuple(
        AreaMapping(path_prefix=str(each_entry["path_prefix"]), area_label=str(each_entry["label"]))
        for each_entry in all_raw_area_map
    )


def load_labeler_config(config_path: Path) -> LabelerConfig:
    """Load and parse a `pr_labeler_config.yml` file into a typed `LabelerConfig`.

    Args:
        config_path: Path to the repo's `pr_labeler_config.yml`.

    Returns:
        The parsed `LabelerConfig`.
    """
    raw_config_text = config_path.read_text(encoding="utf-8")
    raw_config = yaml.safe_load(raw_config_text)
    return LabelerConfig(
        path_prefix_to_strip=str(raw_config.get("area_path_prefix_strip", "")),
        area_mappings=load_area_mappings(raw_config["area_map"]),
        size_thresholds=load_size_thresholds(raw_config["size_thresholds"]),
    )
