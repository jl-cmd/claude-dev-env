#!/usr/bin/env python3
"""Delete empty directories older than a configurable age under a given root.

Usage:
    python sweep_empty_dirs.py /path/to/watch
    python sweep_empty_dirs.py /path/to/watch --age 300
    python sweep_empty_dirs.py /path/to/watch --once
"""

from __future__ import annotations

import argparse
import errno
import logging
import os
import sys
import time

from config.timing import DEFAULT_AGE_SECONDS, DEFAULT_POLL_INTERVAL


def _positive_int(raw_argument: str) -> int:
    """Argparse type: require value >= 1."""
    try:
        parsed = int(raw_argument)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid integer value: {raw_argument!r}"
        )
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {raw_argument}")
    return parsed


def _log_walk_error(os_error: OSError) -> None:
    logging.warning("cannot scan %s -- %s", os_error.filename, os_error.strerror)


def sweep(root: str, min_age_seconds: int) -> list[str]:
    """Remove empty directories under *root* older than *min_age_seconds*.

    Walks bottom-up so nested empty directories are cleaned from the leaves
    inward.  Relies on os.rmdir to fail harmlessly for non-empty directories
    instead of checking snapshotted subdirectory lists.
    """

    all_removed: list[str] = []

    now = time.time()
    for each_directory_path, _, _ in os.walk(
        root, onerror=_log_walk_error, topdown=False
    ):
        if each_directory_path == root:
            continue
        try:
            raw_ctime = os.path.getctime(each_directory_path)
        except FileNotFoundError:
            continue
        except PermissionError:
            logging.warning("permission denied -- %s", each_directory_path)
            continue
        except OSError:
            continue
        ctime = min(raw_ctime, now)
        if now - ctime > min_age_seconds:
            try:
                os.rmdir(each_directory_path)
                logging.info("deleted: %s", each_directory_path)
                all_removed.append(each_directory_path)
            except FileNotFoundError:
                pass
            except OSError as e:
                if e.errno not in (errno.ENOTEMPTY, errno.EEXIST):
                    logging.warning(
                        "could not remove %s -- %s",
                        each_directory_path,
                        e,
                    )

    return all_removed


def _build_parser() -> argparse.ArgumentParser:
    default_age_seconds = DEFAULT_AGE_SECONDS
    default_poll_interval = DEFAULT_POLL_INTERVAL

    parser = argparse.ArgumentParser(
        description="Delete empty directories older than a given age.",
    )
    parser.add_argument("root", help="Root directory to scan")
    parser.add_argument(
        "--age",
        type=_positive_int,
        default=default_age_seconds,
        help=f"Minimum age in seconds (default: {default_age_seconds})",
    )
    parser.add_argument(
        "--once", dest="is_once",
        action="store_true",
        help="Single pass and exit instead of watching in a loop",
    )
    parser.add_argument(
        "--interval",
        type=_positive_int,
        default=default_poll_interval,
        help=f"Poll interval in seconds when looping (default: {default_poll_interval})",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not os.path.isdir(arguments.root):
        print(f"error: not a directory: {arguments.root}", file=sys.stderr)
        sys.exit(1)

    if arguments.is_once:
        sweep(arguments.root, arguments.age)
        return

    print(
        f"watching {arguments.root} every {arguments.interval}s"
        f" (age threshold: {arguments.age}s)"
    )
    try:
        while True:
            sweep(arguments.root, arguments.age)
            time.sleep(arguments.interval)
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
