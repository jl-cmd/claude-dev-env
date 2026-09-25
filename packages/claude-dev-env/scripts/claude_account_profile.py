#!/usr/bin/env python3
"""Keep a named extra Claude profile linked to the main Claude home.

Each profile keeps its own sign-in and history while sharing the main home's
skills, rules, plugins, settings, and docs. Stale shared copies move into
``.replaced/<time>/``. A second run with the same name changes nothing. The
launcher is named ``claude-<profile-name>.cmd``.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dev_env_scripts_constants.claude_account_constants import (
    ALL_ACCOUNT_LOCAL_NAME_PREFIXES,
    ALL_ACCOUNT_LOCAL_NAMES,
    ALL_WINDOWS_RESERVED_PROFILE_NAMES,
    ALL_WINDOWS_JUNCTION_COMMAND_PREFIX,
    CHOICE_MAIN,
    CHOICE_WAIT,
    JSON_LAUNCHER_KEY,
    JSON_LINKED_KEY,
    JSON_MOVED_ASIDE_KEY,
    JSON_UNLINKED_KEY,
    ALL_LAUNCHER_DIRECTORY_RELATIVE_PARTS,
    LAUNCHER_FILE_NAME_TEMPLATE,
    LAUNCHER_REPLACED_SUFFIX,
    LAUNCHER_TEXT_TEMPLATE,
    MAIN_CLAUDE_HOME_DIRECTORY_NAME,
    PROFILES_ROOT_DIRECTORY_NAME,
    PROFILES_ROOT_ENVIRONMENT_VARIABLE,
    PROFILE_NAME_PATTERN,
    REPLACED_DIRECTORY_NAME,
    REPLACED_STAMP_FORMAT,
    SECOND_ACCOUNT_PROFILE_NAME,
    TEXT_ENCODING,
    WINDOWS_EXTENDED_PATH_PREFIX,
    WINDOWS_OS_NAME,
)


@dataclass(frozen=True)
class ProfileSyncReport:
    """What one sync run changed, by top-level entry name."""

    all_linked: tuple[str, ...]
    all_moved_aside: tuple[str, ...]
    all_unlinked: tuple[str, ...]


def validate_profile_name(profile_name: str) -> str:
    """Accept a profile name safe for a directory and command launcher."""
    reserved_names = ALL_WINDOWS_RESERVED_PROFILE_NAMES | {CHOICE_MAIN, CHOICE_WAIT}
    if (
        re.fullmatch(PROFILE_NAME_PATTERN, profile_name) is None
        or profile_name.casefold() in reserved_names
    ):
        raise ValueError("profile name must use letters, digits, hyphens, or underscores")
    return profile_name


def default_profile_home(profile_name: str = SECOND_ACCOUNT_PROFILE_NAME) -> Path:
    """Locate a named extra account's profile directory.

    Returns:
        The profile under the profiles root the environment names, else under
        the default profiles root in the user home.
    """
    profiles_root = os.environ.get(PROFILES_ROOT_ENVIRONMENT_VARIABLE)
    root = (
        Path(profiles_root)
        if profiles_root
        else Path.home() / PROFILES_ROOT_DIRECTORY_NAME
    )
    return root / validate_profile_name(profile_name)


def is_account_local(entry_name: str) -> bool:
    """Tell whether a Claude home entry belongs to one account only.

    ::

        ".credentials.json", "projects", ".claude.json.backup" -> True
        ".credentials.json.bak"                                 -> True
        "skills", "CLAUDE.md", "settings.json"                  -> False

    Args:
        entry_name: A top-level entry name in a Claude home.

    Returns:
        True when the entry holds one account's sign-in, state, or history.
    """
    return entry_name in ALL_ACCOUNT_LOCAL_NAMES or entry_name.startswith(
        ALL_ACCOUNT_LOCAL_NAME_PREFIXES
    )


def _is_link(entry_path: Path) -> bool:
    try:
        os.readlink(entry_path)
    except OSError:
        return False
    return True


def _comparable_path(path_text: str) -> str:
    return os.path.normcase(
        os.path.abspath(path_text.removeprefix(WINDOWS_EXTENDED_PATH_PREFIX))
    )


def _link_target_text(link_path: Path) -> str:
    target_text = os.readlink(link_path)
    if os.path.isabs(target_text.removeprefix(WINDOWS_EXTENDED_PATH_PREFIX)):
        return target_text
    return os.path.join(os.path.dirname(link_path), target_text)


def links_to(link_path: Path, source_path: Path) -> bool:
    """Tell whether a profile entry already resolves to its main-home source.

    ::

        profile/rules -> main/rules      (link or junction)  -> True
        profile/CLAUDE.md, hard link to main/CLAUDE.md        -> True
        profile/rules -> old-shared/rules                     -> False
        profile/CLAUDE.md, a separate copy                    -> False

    Args:
        link_path: The entry in the profile home.
        source_path: The entry in the main home it should resolve to.

    Returns:
        True when the entry is a link to the source or the same file on disk.
    """
    if _is_link(link_path):
        return _comparable_path(_link_target_text(link_path)) == _comparable_path(
            str(source_path)
        )
    if link_path.is_file() and source_path.is_file():
        return os.path.samefile(link_path, source_path)
    return False


def _link_directory(source_path: Path, link_path: Path) -> None:
    if os.name == WINDOWS_OS_NAME:
        subprocess.run(
            [*ALL_WINDOWS_JUNCTION_COMMAND_PREFIX, str(link_path), str(source_path)],
            check=True,
            capture_output=True,
        )
        return
    os.symlink(source_path, link_path, target_is_directory=True)


def _link_file(source_path: Path, link_path: Path) -> None:
    try:
        os.symlink(source_path, link_path)
    except OSError:
        os.link(source_path, link_path)


def _create_link(source_path: Path, link_path: Path) -> None:
    if source_path.is_dir():
        _link_directory(source_path, link_path)
        return
    _link_file(source_path, link_path)


def _remove_link(link_path: Path) -> None:
    try:
        os.rmdir(link_path)
    except NotADirectoryError:
        os.unlink(link_path)


def _is_same_content_copy(entry_path: Path, source_path: Path) -> bool:
    return (
        not _is_link(entry_path)
        and entry_path.is_file()
        and source_path.is_file()
        and filecmp.cmp(entry_path, source_path, shallow=False)
    )


def _stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime(REPLACED_STAMP_FORMAT)


def _is_inside(candidate_text: str, directory: Path) -> bool:
    comparable_directory = _comparable_path(str(directory))
    return _comparable_path(candidate_text).startswith(comparable_directory + os.sep)


def _unlink_orphaned_links(main_home: Path, profile_home: Path) -> tuple[str, ...]:
    all_unlinked: list[str] = []
    for each_entry in sorted(profile_home.iterdir()):
        if not _is_link(each_entry) or each_entry.exists():
            continue
        if not _is_inside(_link_target_text(each_entry), main_home):
            continue
        _remove_link(each_entry)
        all_unlinked.append(each_entry.name)
    return tuple(all_unlinked)


def _unlink_local_names_linked_to_main(
    main_home: Path, profile_home: Path, is_local: Callable[[str], bool]
) -> tuple[str, ...]:
    all_unlinked: list[str] = []
    for each_entry in sorted(profile_home.iterdir()):
        if not is_local(each_entry.name):
            continue
        if not links_to(each_entry, main_home / each_entry.name):
            continue
        _remove_link(each_entry)
        all_unlinked.append(each_entry.name)
    return tuple(all_unlinked)


def _clear_entry(entry_path: Path, source_path: Path, replaced_directory: Path) -> bool:
    if _is_same_content_copy(entry_path, source_path):
        entry_path.unlink()
        return False
    replaced_directory.mkdir(parents=True, exist_ok=True)
    os.replace(entry_path, replaced_directory / entry_path.name)
    return True


def _link_shared_entries(
    main_home: Path,
    profile_home: Path,
    replaced_directory: Path,
    is_local: Callable[[str], bool],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    all_linked: list[str] = []
    all_moved_aside: list[str] = []
    for each_source in sorted(main_home.iterdir()):
        entry_path = profile_home / each_source.name
        if is_local(each_source.name) or links_to(entry_path, each_source):
            continue
        if os.path.lexists(entry_path) and _clear_entry(
            entry_path, each_source, replaced_directory
        ):
            all_moved_aside.append(each_source.name)
        _create_link(each_source, entry_path)
        all_linked.append(each_source.name)
    return tuple(all_linked), tuple(all_moved_aside)


def sync_profile(
    *,
    main_home: Path,
    profile_home: Path,
    now: datetime,
    is_local: Callable[[str], bool] = is_account_local,
) -> ProfileSyncReport:
    """Link every shared main-home entry into the profile home.

    Args:
        main_home: The main account's home.
        profile_home: The profile account's home.
        now: The run time that names the folder stale entries move into.
        is_local: Tells whether a top-level entry belongs to one account only.

    Returns:
        The entries the run linked, moved aside, and unlinked.
    """
    profile_home.mkdir(parents=True, exist_ok=True)
    all_unlinked = tuple(
        sorted(
            _unlink_orphaned_links(main_home, profile_home)
            + _unlink_local_names_linked_to_main(main_home, profile_home, is_local)
        )
    )
    all_linked, all_moved_aside = _link_shared_entries(
        main_home,
        profile_home,
        profile_home / REPLACED_DIRECTORY_NAME / _stamp(now),
        is_local,
    )
    return ProfileSyncReport(
        all_linked=all_linked,
        all_moved_aside=all_moved_aside,
        all_unlinked=all_unlinked,
    )


def _moved_launcher_name(launcher_file_name: str, now: datetime) -> str:
    return f"{launcher_file_name}{LAUNCHER_REPLACED_SUFFIX}{_stamp(now)}"


def write_launcher(
    *,
    launcher_directory: Path,
    profile_home: Path,
    now: datetime,
    profile_name: str = SECOND_ACCOUNT_PROFILE_NAME,
) -> Path:
    """Write the launcher that runs Claude under a named profile.

    ::

        claude-NAME -p "fix the test"
        -> CLAUDE_CONFIG_DIR=<profile home>, then claude -p "fix the test"
        an older claude-NAME.cmd -> claude-NAME.cmd.replaced-<time>

    Args:
        launcher_directory: The directory on PATH that holds the launcher.
        profile_home: The named account's Claude home.
        now: The run time that names a moved older launcher.
        profile_name: The name used in the launcher file name.

    Returns:
        The launcher path.
    """
    launcher_file_name = LAUNCHER_FILE_NAME_TEMPLATE.format(
        profile_name=validate_profile_name(profile_name)
    )
    launcher_path = launcher_directory / launcher_file_name
    launcher_text = LAUNCHER_TEXT_TEMPLATE.format(profile_home=profile_home)
    launcher_bytes = launcher_text.encode(TEXT_ENCODING)
    if launcher_path.is_file() and launcher_path.read_bytes() == launcher_bytes:
        return launcher_path
    if launcher_path.is_file():
        os.replace(
            launcher_path,
            launcher_path.with_name(_moved_launcher_name(launcher_file_name, now)),
        )
    launcher_directory.mkdir(parents=True, exist_ok=True)
    launcher_path.write_bytes(launcher_bytes)
    return launcher_path


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Link the main Claude home into the second account's profile."
    )
    parser.add_argument(
        "--main-home", type=Path, default=Path.home() / MAIN_CLAUDE_HOME_DIRECTORY_NAME
    )
    parser.add_argument("--profile-name", default=SECOND_ACCOUNT_PROFILE_NAME)
    parser.add_argument("--profile-home", type=Path)
    parser.add_argument(
        "--launcher-directory",
        type=Path,
        default=Path.home().joinpath(*ALL_LAUNCHER_DIRECTORY_RELATIVE_PARTS),
    )
    return parser


def main(all_command_arguments: list[str]) -> int:
    """Sync the profile, write the launcher, and print what changed as JSON.

    Args:
        all_command_arguments: Command-line arguments after the program name.

    Returns:
        Zero once the profile and launcher match the main home.
    """
    parser = _build_argument_parser()
    arguments = parser.parse_args(all_command_arguments)
    try:
        validate_profile_name(arguments.profile_name)
    except ValueError as error:
        parser.error(str(error))
    profile_home = arguments.profile_home or default_profile_home(arguments.profile_name)
    now = datetime.now(timezone.utc)
    report = sync_profile(
        main_home=arguments.main_home, profile_home=profile_home, now=now
    )
    launcher_path = write_launcher(
        launcher_directory=arguments.launcher_directory,
        profile_home=profile_home,
        now=now,
        profile_name=arguments.profile_name,
    )
    print(
        json.dumps(
            {
                JSON_LINKED_KEY: list(report.all_linked),
                JSON_MOVED_ASIDE_KEY: list(report.all_moved_aside),
                JSON_UNLINKED_KEY: list(report.all_unlinked),
                JSON_LAUNCHER_KEY: str(launcher_path),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
