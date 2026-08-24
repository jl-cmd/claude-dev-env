"""Pending-sidecar discovery and cleanup for hook state."""

from pathlib import Path


def pending_sidecar_paths(
    main_file: Path, pending_marker: str, pending_suffix: str
) -> tuple[Path, ...]:
    """Return pending sidecars for one main state file.

    Args:
        main_file: The primary state file.
        pending_marker: The marker before the unique sidecar token.
        pending_suffix: The sidecar filename suffix.

    Returns:
        The matching pending sidecar paths.
    """
    pending_pattern = f"{main_file.name}{pending_marker}*{pending_suffix}"
    return tuple(main_file.parent.glob(pending_pattern))


def remove_pending_sidecars(all_pending_files: tuple[Path, ...]) -> None:
    """Remove a captured pending-sidecar set.

    Args:
        all_pending_files: The exact sidecars already merged or consumed.
    """
    for each_pending_file in all_pending_files:
        try:
            each_pending_file.unlink(missing_ok=True)
        except OSError:
            continue
