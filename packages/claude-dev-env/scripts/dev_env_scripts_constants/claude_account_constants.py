"""Named constants for the second Claude account: its profile, launcher, and picker.

The profile sync links the main Claude home into a second account's profile
directory. The launcher points Claude at that profile. The picker reads both
accounts' usage meters and names the account a job runs on, protecting the
main account so its owner never runs out.
"""

from __future__ import annotations

from datetime import timedelta

MAIN_CLAUDE_HOME_DIRECTORY_NAME: str = ".claude"
"""Directory under the user home that holds the main account's Claude home."""

PROFILES_ROOT_DIRECTORY_NAME: str = ".claude-profiles"
"""Directory under the user home that holds named Claude profiles."""

PROFILES_ROOT_ENVIRONMENT_VARIABLE: str = "LLM_SETTINGS_PROFILES_ROOT"
"""Environment variable that relocates the profiles root."""

SECOND_ACCOUNT_PROFILE_NAME: str = "ev"
"""Profile directory name the second account signs in under."""

ALL_LAUNCHER_DIRECTORY_RELATIVE_PARTS: tuple[str, ...] = (".local", "bin")
"""Path parts under the user home of the directory on PATH that holds the launcher."""

LAUNCHER_FILE_NAME: str = "claude-ev.cmd"
"""File name of the launcher that runs Claude under the second account."""

LAUNCHER_TEXT_TEMPLATE: str = (
    "@echo off\r\n"
    "setlocal\r\n"
    'set "CLAUDE_CONFIG_DIR={profile_home}"\r\n'
    "claude %*\r\n"
    "exit /b %ERRORLEVEL%\r\n"
)
"""Launcher body: point Claude at the profile and pass every argument through."""

LAUNCHER_REPLACED_SUFFIX: str = ".replaced-"
"""Suffix, before the run time, of an older launcher the sync moved aside."""

ALL_WINDOWS_JUNCTION_COMMAND_PREFIX: tuple[str, ...] = ("cmd", "/c", "mklink", "/J")
"""Command that links a directory as a junction on Windows, before link and target."""

CREDENTIALS_FILE_NAME: str = ".credentials.json"
"""File in a Claude home that holds that account's sign-in."""

ALL_ACCOUNT_LOCAL_NAMES: frozenset[str] = frozenset(
    {
        ".credentials.json",
        "projects",
        "sessions",
        "session-env",
        "shell-snapshots",
        "todos",
        "statsig",
        "file-history",
        "history.jsonl",
        "ide",
        "debug",
        "telemetry",
        "logs",
        "tasks",
        "plans",
        "backups",
        "cache",
        "paste-cache",
        "stats-cache.json",
    }
)
"""Top-level Claude home entries that belong to one account and are never linked."""

ALL_ACCOUNT_LOCAL_NAME_PREFIXES: tuple[str, ...] = (".claude.json",)
"""Name prefixes of per-account state files, covering the global config and its backups."""

REPLACED_DIRECTORY_NAME: str = ".replaced"
"""Profile subdirectory that holds entries the sync moved aside, one folder per run."""

REPLACED_STAMP_FORMAT: str = "%Y%m%dT%H%M%SZ"
"""UTC time format naming each run's folder under the replaced directory."""

WINDOWS_EXTENDED_PATH_PREFIX: str = "\\\\?\\"
"""Prefix Windows puts on a junction target that the link comparison strips."""

WINDOWS_OS_NAME: str = "nt"
"""Value of ``os.name`` on Windows, where directories link as junctions."""

TEXT_ENCODING: str = "utf-8"
"""Encoding for the launcher file and the JSON reports."""

MAIN_SPEND_WINDOW: timedelta = timedelta(hours=24)
"""Main takes jobs only when its weekly window resets within this span."""

MAIN_WEEKLY_USED_CEILING_PERCENT: float = 90.0
"""Main takes jobs only while its weekly use is under this percent."""

MAIN_SESSION_USED_CEILING_PERCENT: float = 50.0
"""Main takes jobs only while its 5-hour use is under this percent."""

SECOND_WEEKLY_USED_CEILING_PERCENT: float = 95.0
"""The second account takes jobs while its weekly use is under this percent."""

SECOND_SESSION_USED_CEILING_PERCENT: float = 90.0
"""The second account takes jobs while its 5-hour use is under this percent."""

FULL_PERCENT: float = 100.0
"""Percent scale ceiling, so remaining is this minus used."""

SECONDS_PER_HOUR: int = 3600
"""Seconds in one hour, for reason text that names hours until a reset."""

CHOICE_MAIN: str = "main"
"""Picker answer: run the job on the main account."""

CHOICE_SECOND: str = "second"
"""Picker answer: run the job on the second account."""

CHOICE_WAIT: str = "wait"
"""Picker answer: neither account has room, so the job waits."""

REASON_MAIN_EXPIRING_TEMPLATE: str = (
    "main week resets in {hours_until_reset} hours with {remaining_percent:.0f}% left"
)
"""Reason when main spends leftover usage that expires soon."""

REASON_SECOND_HAS_ROOM_TEMPLATE: str = (
    "second account has {weekly_remaining_percent:.0f}% of its week"
    " and {session_remaining_percent:.0f}% of its 5-hour window left"
)
"""Reason when the second account takes the job."""

REASON_SECOND_UNREAD: str = (
    "second account meter unreadable; its own run refreshes the sign-in"
)
"""Reason when the second account's meter cannot be read and it takes the job anyway."""

REASON_WAIT_TEMPLATE: str = (
    "second account is at {weekly_used_percent:.0f}% of its week"
    " and {session_used_percent:.0f}% of its 5-hour window; next reset {next_reset}"
)
"""Reason when neither account has room."""

UNKNOWN_RESET_TEXT: str = "unknown"
"""Reset text when the blocking meter carries no reset time."""

JSON_ACCOUNT_KEY: str = "account"
"""Picker JSON key naming the chosen account."""

JSON_CONFIG_DIRECTORY_KEY: str = "config_dir"
"""Picker JSON key naming the Claude home the chosen account runs under."""

JSON_REASON_KEY: str = "reason"
"""Picker JSON key carrying the plain-words reason for the choice."""

JSON_LINKED_KEY: str = "linked"
"""Sync JSON key listing entries the run linked."""

JSON_MOVED_ASIDE_KEY: str = "moved_aside"
"""Sync JSON key listing entries the run moved into the replaced directory."""

JSON_UNLINKED_KEY: str = "unlinked"
"""Sync JSON key listing links the run removed because main no longer has the entry."""

JSON_LAUNCHER_KEY: str = "launcher"
"""Sync JSON key naming the launcher file the run wrote or confirmed."""
