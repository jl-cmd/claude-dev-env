"""Re-sort already-filed cert-failure theme folders after the unfixable patterns change.

Recomputes each theme's bucket from its HTML report using the production
FailureCategorizer decision helpers, then moves folders whose current bucket no
longer matches. Dry-run by default; pass --apply to move folders.
"""

import argparse
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from shared_utils.samsung_utils.cert_failure_processor.failure_categorizer import (
    FailureCategorizer,
)
from shared_utils.web_automation.config.account import (
    AccountType,
    account_folder_config,
)

logger = logging.getLogger("resort_cert_folders")


@dataclass(frozen=True)
class ResortConfig:
    """Naming and discovery constants for the re-sort pass."""

    report_glob: str = "*_Report.html"
    log_format: str = "%(message)s"


@dataclass(frozen=True)
class FolderMove:
    """A single planned move from a theme's current bucket to its computed bucket."""

    theme_folder: Path
    current_bucket: str
    computed_bucket: str


def compute_bucket(categorizer: FailureCategorizer, theme_folder: Path, resort_config: ResortConfig) -> str | None:
    """Compute the bucket a theme folder belongs in from its HTML report.

    Args:
        categorizer: The production categorizer holding the loaded unfixable patterns.
        theme_folder: The theme folder containing the cert-failure HTML report.
        resort_config: Discovery and logging constants for this pass.

    Returns:
        The computed bucket name, or None when no report is present or no bucket applies.
    """
    all_reports = list(theme_folder.glob(resort_config.report_glob))
    if not all_reports:
        logger.warning("No report for '%s' - skipping", theme_folder.name)
        return None
    html_content = all_reports[0].read_text(encoding="utf-8", errors="ignore")
    rejection_text = categorizer._parse_rejection_text(html_content)
    detector_category = categorizer._detect_category(html_content, rejection_text)
    classification = categorizer._classify_from_html(html_content)
    return categorizer._resolve_category_priority(detector_category, classification)


def plan_moves(account_root: Path, categorizer: FailureCategorizer, resort_config: ResortConfig) -> list[FolderMove]:
    """Plan every move needed to bring a day's account folder into line with the patterns.

    Args:
        account_root: The <base>/<Month>/<day>/<account_folder> directory to scan.
        categorizer: The production categorizer holding the loaded unfixable patterns.
        resort_config: Discovery and logging constants for this pass.

    Returns:
        One FolderMove per theme whose current bucket differs from its computed bucket.
    """
    planned_moves: list[FolderMove] = []
    for each_bucket_dir in sorted(path for path in account_root.iterdir() if path.is_dir()):
        current_bucket = each_bucket_dir.name
        for each_theme in sorted(path for path in each_bucket_dir.iterdir() if path.is_dir()):
            computed_bucket = compute_bucket(categorizer, each_theme, resort_config)
            if computed_bucket is not None and computed_bucket != current_bucket:
                planned_moves.append(
                    FolderMove(
                        theme_folder=each_theme,
                        current_bucket=current_bucket,
                        computed_bucket=computed_bucket,
                    )
                )
    return planned_moves


def apply_move(account_root: Path, folder_move: FolderMove) -> None:
    """Move one theme folder into its computed bucket directory.

    Args:
        account_root: The <base>/<Month>/<day>/<account_folder> directory.
        folder_move: The planned move to carry out.
    """
    target_dir = account_root / folder_move.computed_bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / folder_move.theme_folder.name
    if target_path.exists():
        logger.warning("Target exists for '%s' - skipping", folder_move.theme_folder.name)
        return
    shutil.move(str(folder_move.theme_folder), str(target_path))


def run_resort(base_path: str, month: str, day: str, account_label: str, should_apply: bool) -> None:
    """Plan and optionally apply a re-sort of one day's cert-failure folders.

    Args:
        base_path: The cert-failure base directory.
        month: The month folder name (for example "June").
        day: The day folder name (for example "18").
        account_label: "PRIMARY" or "SECONDARY".
        should_apply: When True, move folders; when False, only log the plan.
    """
    resort_config = ResortConfig()
    logging.basicConfig(level=logging.INFO, format=resort_config.log_format)
    account_type = AccountType[account_label]
    account_folder = account_folder_config.get_folder_name(account_type)
    account_root = Path(base_path) / month / day / account_folder
    categorizer = FailureCategorizer(base_path)
    planned_moves = plan_moves(account_root, categorizer, resort_config)
    if not planned_moves:
        logger.info("Nothing to re-sort in %s", account_root)
        return
    for each_move in planned_moves:
        logger.info(
            "%s: %s -> %s",
            each_move.theme_folder.name,
            each_move.current_bucket,
            each_move.computed_bucket,
        )
        if should_apply:
            apply_move(account_root, each_move)
    logger.info("%d folder(s) %s", len(planned_moves), "moved" if should_apply else "planned (dry run)")


def main() -> None:
    """Parse arguments and run the re-sort pass."""
    parser = argparse.ArgumentParser(description="Re-sort cert-failure folders after a pattern change.")
    parser.add_argument("base_path", help="Cert-failure base directory.")
    parser.add_argument("month", help='Month folder name, for example "June".')
    parser.add_argument("day", help='Day folder name, for example "18".')
    parser.add_argument("account", choices=["PRIMARY", "SECONDARY"], help="Account type.")
    parser.add_argument("--apply", action="store_true", help="Move folders instead of dry-running.")
    parsed_arguments = parser.parse_args()
    run_resort(
        parsed_arguments.base_path,
        parsed_arguments.month,
        parsed_arguments.day,
        parsed_arguments.account,
        parsed_arguments.apply,
    )


if __name__ == "__main__":
    main()
