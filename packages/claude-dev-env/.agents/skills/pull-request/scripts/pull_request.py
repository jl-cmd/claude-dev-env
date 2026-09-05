"""Run validated GitHub pull request actions with process-local account selection."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from github_pr_command_constants.config.constants import (
    ACCOUNT_LOOKUP_EMPTY_MESSAGE,
    ACCOUNT_LOOKUP_FAILED_MESSAGE,
    ACCOUNT_LOOKUP_FAILURE_EXIT_CODE,
    ACTION_COMMENT,
    ACTION_CREATE,
    ACTION_EDIT,
    ACTION_FAILED_MESSAGE,
    ACTION_REVIEW,
    ALL_DURABLE_POST_LINTER_RELATIVE_PATH_PARTS,
    ALL_GITHUB_AUTHORIZATION_ENVIRONMENT_KEYS,
    ALL_LINTER_ACTIONS_BY_COMMAND,
    ALL_REVIEW_FLAGS_BY_EVENT,
    CONFIG_DIR_OVERRIDE_ENVIRONMENT_KEY,
    DEFAULT_MANAGED_ROOT_DIRECTORY_NAME,
    GH_TOKEN_ENVIRONMENT_KEY,
    GITHUB_TOKEN_ENVIRONMENT_KEY,
    PACKAGE_ROOT_PARENT_INDEX,
    REVIEW_EVENT_COMMENT,
    SELECTED_ACCOUNT_ENVIRONMENT_KEY,
)

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    all_actions = parser.add_subparsers(dest="action", required=True)
    create = all_actions.add_parser(ACTION_CREATE, allow_abbrev=False)
    create.add_argument("--repo", required=True)
    create.add_argument("--base", required=True)
    create.add_argument("--head", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--body-file", required=True, type=Path)
    edit = all_actions.add_parser(ACTION_EDIT, allow_abbrev=False)
    edit.add_argument("--repo", required=True)
    edit.add_argument("--number", required=True)
    edit.add_argument("--title")
    edit.add_argument("--body-file", type=Path)
    comment = all_actions.add_parser(ACTION_COMMENT, allow_abbrev=False)
    comment.add_argument("--repo", required=True)
    comment.add_argument("--number", required=True)
    comment.add_argument("--body-file", required=True, type=Path)
    review = all_actions.add_parser(ACTION_REVIEW, allow_abbrev=False)
    review.add_argument("--repo", required=True)
    review.add_argument("--number", required=True)
    review.add_argument("--body-file", required=True, type=Path)
    review.add_argument(
        "--event",
        choices=tuple(ALL_REVIEW_FLAGS_BY_EVENT),
        default=REVIEW_EVENT_COMMENT,
    )
    return parser


def _configured_managed_root(all_environment: Mapping[str, str]) -> Path:
    configured_root_text = all_environment.get(CONFIG_DIR_OVERRIDE_ENVIRONMENT_KEY, "").strip()
    if not configured_root_text:
        return Path.home() / DEFAULT_MANAGED_ROOT_DIRECTORY_NAME
    configured_root = Path(configured_root_text).expanduser()
    if configured_root.is_absolute():
        return configured_root
    return Path.home() / configured_root


def _linter_path(all_environment: Mapping[str, str]) -> Path:
    source_candidate = Path(__file__).resolve().parents[PACKAGE_ROOT_PARENT_INDEX].joinpath(
        *ALL_DURABLE_POST_LINTER_RELATIVE_PATH_PARTS
    )
    if source_candidate.is_file():
        return source_candidate
    return _configured_managed_root(all_environment).joinpath(
        *ALL_DURABLE_POST_LINTER_RELATIVE_PATH_PARTS
    )


def _linter_arguments(
    arguments: argparse.Namespace, all_environment: Mapping[str, str]
) -> list[str]:
    all_arguments = [
        sys.executable,
        str(_linter_path(all_environment)),
        "--action",
        ALL_LINTER_ACTIONS_BY_COMMAND[arguments.action],
    ]
    if getattr(arguments, "title", None) is not None:
        all_arguments.extend(["--title", arguments.title])
    if getattr(arguments, "body_file", None) is not None:
        all_arguments.extend(["--body-file", str(arguments.body_file)])
    return all_arguments


def _create_arguments(arguments: argparse.Namespace) -> list[str]:
    return [
        "gh",
        "pr",
        "create",
        "--draft",
        "--repo",
        arguments.repo,
        "--base",
        arguments.base,
        "--head",
        arguments.head,
        "--title",
        arguments.title,
        "--body-file",
        str(arguments.body_file),
    ]


def _edit_arguments(arguments: argparse.Namespace) -> list[str]:
    all_arguments = ["gh", "pr", "edit", arguments.number, "--repo", arguments.repo]
    if arguments.title is not None:
        all_arguments.extend(["--title", arguments.title])
    if arguments.body_file is not None:
        all_arguments.extend(["--body-file", str(arguments.body_file)])
    return all_arguments


def _post_arguments(arguments: argparse.Namespace) -> list[str]:
    if arguments.action == ACTION_CREATE:
        return _create_arguments(arguments)
    if arguments.action == ACTION_EDIT:
        return _edit_arguments(arguments)
    if arguments.action == ACTION_COMMENT:
        return [
            "gh",
            "pr",
            "comment",
            arguments.number,
            "--repo",
            arguments.repo,
            "--body-file",
            str(arguments.body_file),
        ]
    return [
        "gh",
        "pr",
        "review",
        arguments.number,
        "--repo",
        arguments.repo,
        ALL_REVIEW_FLAGS_BY_EVENT[arguments.event],
        "--body-file",
        str(arguments.body_file),
    ]


def _lookup_environment(all_environment: Mapping[str, str]) -> dict[str, str]:
    lookup_environment = dict(all_environment)
    for each_name in ALL_GITHUB_AUTHORIZATION_ENVIRONMENT_KEYS:
        lookup_environment.pop(each_name, None)
    return lookup_environment


def _lookup_account_authorization(
    selected_account: str,
    all_environment: Mapping[str, str],
    command_runner: CommandRunner,
) -> str | None:
    try:
        completed_lookup = command_runner(
            ["gh", "auth", "token", "--user", selected_account],
            capture_output=True,
            check=False,
            env=_lookup_environment(all_environment),
            shell=False,
            text=True,
        )
    except OSError:
        sys.stderr.write(ACCOUNT_LOOKUP_FAILED_MESSAGE)
        return None
    if completed_lookup.returncode != 0:
        sys.stderr.write(ACCOUNT_LOOKUP_FAILED_MESSAGE)
        return None
    account_authorization = completed_lookup.stdout.strip()
    if not account_authorization:
        sys.stderr.write(ACCOUNT_LOOKUP_EMPTY_MESSAGE)
        return None
    return account_authorization


def _action_environment(
    all_environment: Mapping[str, str],
    command_runner: CommandRunner,
) -> dict[str, str] | None:
    selected_account = all_environment.get(SELECTED_ACCOUNT_ENVIRONMENT_KEY)
    if not selected_account:
        return dict(all_environment)
    account_authorization = _lookup_account_authorization(
        selected_account, all_environment, command_runner
    )
    if account_authorization is None:
        return None
    action_environment = dict(all_environment)
    action_environment.pop(GITHUB_TOKEN_ENVIRONMENT_KEY, None)
    action_environment[GH_TOKEN_ENVIRONMENT_KEY] = account_authorization
    return action_environment


def _run_post_action(
    arguments: argparse.Namespace,
    all_action_environment: Mapping[str, str],
    command_runner: CommandRunner,
) -> int:
    try:
        completed_action = command_runner(
            _post_arguments(arguments),
            check=False,
            env=all_action_environment,
            shell=False,
        )
    except OSError:
        sys.stderr.write(ACTION_FAILED_MESSAGE)
        return ACCOUNT_LOOKUP_FAILURE_EXIT_CODE
    return completed_action.returncode


def _run_action(
    arguments: argparse.Namespace,
    all_environment: Mapping[str, str],
    command_runner: CommandRunner,
) -> int:
    action_environment = _action_environment(all_environment, command_runner)
    if action_environment is None:
        return ACCOUNT_LOOKUP_FAILURE_EXIT_CODE
    return _run_post_action(arguments, action_environment, command_runner)


def main(
    all_arguments: Sequence[str],
    *,
    all_environment: Mapping[str, str],
    command_runner: CommandRunner,
) -> int:
    """Run one validated pull request action."""
    arguments = _build_parser().parse_args(list(all_arguments))
    completed_lint = command_runner(
        _linter_arguments(arguments, all_environment), check=False, shell=False
    )
    if completed_lint.returncode != 0:
        return completed_lint.returncode
    return _run_action(arguments, all_environment, command_runner)


if __name__ == "__main__":
    raise SystemExit(
        main(
            sys.argv[1:],
            all_environment=os.environ,
            command_runner=subprocess.run,
        )
    )
