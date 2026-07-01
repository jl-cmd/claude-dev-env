"""Copilot premium-request quota pre-check.

Run this before any Copilot review step spawns. It reads a configured GitHub
account's remaining premium-interaction quota and decides whether Copilot has
quota to run. An account already out of quota skips the Copilot step instead of
wasting a whole review cycle on it.

Account resolution order: the ``--account`` flag, then the
``COPILOT_QUOTA_ACCOUNT`` environment variable, then that same key parsed from a
git-ignored ``.env`` file. The account's ``gh`` token is resolved with
``gh auth token -u <account>`` and the quota is read from
``gh api copilot_internal/user``. The config file names the account only and
stores no secret.

The exit code tells the caller what to do. Exit 0 means run Copilot. A non-zero
exit means skip it: the account is out of quota (scenario A), the quota API or
account access is down (scenario B), or no account is configured (scenario C).
Every path prints one line: the run line to stdout, each skip line to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from pr_loop_shared_constants.copilot_quota_constants import (
    COPILOT_INTERNAL_USER_API_PATH,
    COPILOT_QUOTA_ACCOUNT_ENV_VAR_NAME,
    COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH,
    EXIT_CODE_NO_ACCOUNT_CONFIGURED,
    EXIT_CODE_OUT_OF_QUOTA,
    EXIT_CODE_QUOTA_API_DOWN,
    EXIT_CODE_QUOTA_AVAILABLE,
    GH_TOKEN_ENV_VAR_NAME,
    PREMIUM_ENTITLEMENT_FIELD_NAME,
    PREMIUM_INTERACTIONS_FIELD_NAME,
    PREMIUM_OVERAGE_PERMITTED_FIELD_NAME,
    PREMIUM_PERCENT_REMAINING_FIELD_NAME,
    PREMIUM_REMAINING_FIELD_NAME,
    PREMIUM_UNLIMITED_FIELD_NAME,
    QUOTA_SNAPSHOTS_FIELD_NAME,
)


@dataclass(frozen=True)
class QuotaDecision:
    """One quota pre-check outcome: the exit code and the single log line.

    The exit code tells the caller what to do, where 0 runs Copilot and any
    non-zero skips it. The CLI prints the message on one line, to stdout on a
    run and to stderr on a skip.
    """

    exit_code: int
    message: str


def _run_gh(
    all_command_arguments: list[str],
    all_environment_overrides: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run a ``gh`` subprocess and return its exit code and stdout.

    Args:
        all_command_arguments: Arguments after the ``gh`` program name, for
            example ``["api", "copilot_internal/user"]``.
        all_environment_overrides: Environment entries to overlay on the current
            environment for this call, or None to inherit it unchanged.

    Returns:
        The subprocess exit code paired with its captured stdout.
    """
    process_environment = dict(os.environ)
    if all_environment_overrides:
        process_environment.update(all_environment_overrides)
    completed_process = subprocess.run(
        ["gh", *all_command_arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=process_environment,
    )
    return completed_process.returncode, completed_process.stdout


def _read_account_from_env_file(env_file_path: Path) -> str | None:
    """Read the configured account from a git-ignored ``.env`` file.

    Args:
        env_file_path: Path to the ``.env`` file that may carry a
            ``COPILOT_QUOTA_ACCOUNT=<login>`` line.

    Returns:
        The configured account login, or None when the file is absent,
        unreadable, or carries no non-empty account line.
    """
    try:
        file_text = env_file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for each_line in file_text.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        key_text, separator, raw_account = stripped_line.partition("=")
        if not separator or key_text.strip() != COPILOT_QUOTA_ACCOUNT_ENV_VAR_NAME:
            continue
        resolved_login = raw_account.strip().strip('"').strip("'")
        if resolved_login:
            return resolved_login
    return None


def _resolve_account(cli_account: str | None, env_file_path: Path) -> str | None:
    """Resolve the account whose Copilot quota to check.

    Args:
        cli_account: The ``--account`` value, or None when the flag is absent.
        env_file_path: The ``.env`` file consulted when neither the flag nor
            the environment variable names an account.

    Returns:
        The resolved account login from the flag, then the
        ``COPILOT_QUOTA_ACCOUNT`` environment variable, then the ``.env``
        file, or None when none of the three names an account.
    """
    if cli_account and cli_account.strip():
        return cli_account.strip()
    environment_account = os.environ.get(COPILOT_QUOTA_ACCOUNT_ENV_VAR_NAME, "").strip()
    if environment_account:
        return environment_account
    return _read_account_from_env_file(env_file_path)


def _resolve_gh_token(account_login: str) -> str | None:
    """Resolve the account's gh token via ``gh auth token -u <account>``.

    Args:
        account_login: The GitHub login to resolve a token for.

    Returns:
        The token string, or None when ``gh`` exits non-zero or prints no
        token, so an account that is not ``gh auth login``-ed reads as down.
    """
    returncode, stdout = _run_gh(["auth", "token", "-u", account_login])
    if returncode != 0:
        return None
    token = stdout.strip()
    return token or None


def _fetch_copilot_user(token: str) -> dict[str, object] | None:
    """Read the ``copilot_internal/user`` payload for a resolved token.

    Args:
        token: A gh token authorized for the account under check.

    Returns:
        The parsed response object, or None when ``gh`` exits non-zero or
        returns a body that is not a JSON object.
    """
    returncode, stdout = _run_gh(
        ["api", COPILOT_INTERNAL_USER_API_PATH],
        {GH_TOKEN_ENV_VAR_NAME: token},
    )
    if returncode != 0:
        return None
    try:
        parsed_payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_payload, dict):
        return None
    return parsed_payload


def _extract_premium_snapshot(
    all_user_fields: dict[str, object],
) -> dict[str, object] | None:
    """Pull the ``premium_interactions`` quota snapshot from the user payload.

    Args:
        all_user_fields: The parsed ``copilot_internal/user`` response object.

    Returns:
        The ``quota_snapshots.premium_interactions`` object, or None when
        either level is missing or is not an object.
    """
    quota_snapshots = all_user_fields.get(QUOTA_SNAPSHOTS_FIELD_NAME)
    if not isinstance(quota_snapshots, dict):
        return None
    premium_snapshot = quota_snapshots.get(PREMIUM_INTERACTIONS_FIELD_NAME)
    if not isinstance(premium_snapshot, dict):
        return None
    return premium_snapshot


def _is_premium_quota_exhausted(all_premium_fields: dict[str, object]) -> bool:
    """Report whether the premium-interaction quota is exhausted.

    The quota counts as exhausted when it is not unlimited, its remaining count
    has reached zero, and overage is not permitted. That is the one state in
    which a Copilot review request cannot be served. Any missing or malformed
    gating field leaves the quota reported as not exhausted, so the caller runs
    Copilot rather than skipping on an unreadable snapshot.

    Args:
        all_premium_fields: The ``premium_interactions`` quota snapshot object.

    Returns:
        True when unlimited is False, remaining is at or below zero, and overage
        is not permitted.
    """
    is_unlimited = all_premium_fields.get(PREMIUM_UNLIMITED_FIELD_NAME)
    is_overage_permitted = all_premium_fields.get(PREMIUM_OVERAGE_PERMITTED_FIELD_NAME)
    remaining = all_premium_fields.get(PREMIUM_REMAINING_FIELD_NAME)
    if not isinstance(is_unlimited, bool) or not isinstance(is_overage_permitted, bool):
        return False
    if isinstance(remaining, bool) or not isinstance(remaining, (int, float)):
        return False
    return is_unlimited is False and remaining <= 0 and is_overage_permitted is False


def _describe_quota_amount(all_premium_fields: dict[str, object]) -> str:
    """Render the remaining/entitlement/percent fragment for a snapshot.

    Args:
        all_premium_fields: The ``premium_interactions`` quota snapshot object.

    Returns:
        A fragment naming the remaining count over the entitlement with the
        percent remaining, built from the snapshot's remaining, entitlement,
        and percent-remaining fields.
    """
    remaining = all_premium_fields.get(PREMIUM_REMAINING_FIELD_NAME)
    entitlement = all_premium_fields.get(PREMIUM_ENTITLEMENT_FIELD_NAME)
    percent_remaining = all_premium_fields.get(PREMIUM_PERCENT_REMAINING_FIELD_NAME)
    return f"{remaining}/{entitlement} remaining ({percent_remaining}%)"


def evaluate_copilot_quota(
    cli_account: str | None, env_file_path: Path
) -> QuotaDecision:
    """Decide whether Copilot has premium quota to run for a configured account.

    Resolves the account, reads its remaining ``premium_interactions`` quota via
    ``gh``, and maps the result to one of four outcomes: premium quota available
    (run Copilot), out of quota, quota API or account access down, and no
    account configured.

    Args:
        cli_account: The ``--account`` value, or None when the flag is absent.
        env_file_path: The ``.env`` file consulted for the account when neither
            the flag nor the environment variable names one.

    Returns:
        A QuotaDecision carrying the exit code and the single log line for the
        resolved outcome.
    """
    account_login = _resolve_account(cli_account, env_file_path)
    if account_login is None:
        return QuotaDecision(
            EXIT_CODE_NO_ACCOUNT_CONFIGURED,
            f"copilot-quota: no account configured — set "
            f"{COPILOT_QUOTA_ACCOUNT_ENV_VAR_NAME}=<login> in {env_file_path} "
            f"(or pass --account). Skipping Copilot (scenario C).",
        )
    token = _resolve_gh_token(account_login)
    if token is None:
        return QuotaDecision(
            EXIT_CODE_QUOTA_API_DOWN,
            f"copilot-quota: could not resolve a gh token for '{account_login}' "
            f"(is it gh auth login-ed?) — skipping Copilot (scenario B).",
        )
    all_user_fields = _fetch_copilot_user(token)
    if all_user_fields is None:
        return QuotaDecision(
            EXIT_CODE_QUOTA_API_DOWN,
            f"copilot-quota: gh api {COPILOT_INTERNAL_USER_API_PATH} failed or "
            f"returned non-JSON for '{account_login}' — skipping Copilot "
            f"(scenario B).",
        )
    premium_snapshot = _extract_premium_snapshot(all_user_fields)
    if premium_snapshot is None:
        return QuotaDecision(
            EXIT_CODE_QUOTA_API_DOWN,
            f"copilot-quota: the {COPILOT_INTERNAL_USER_API_PATH} response for "
            f"'{account_login}' carried no "
            f"{QUOTA_SNAPSHOTS_FIELD_NAME}.{PREMIUM_INTERACTIONS_FIELD_NAME} — "
            f"skipping Copilot (scenario B).",
        )
    if _is_premium_quota_exhausted(premium_snapshot):
        return QuotaDecision(
            EXIT_CODE_OUT_OF_QUOTA,
            f"copilot-quota: {account_login} is out of premium-interaction "
            f"quota — {_describe_quota_amount(premium_snapshot)}, overage not "
            f"permitted — skipping Copilot (scenario A).",
        )
    return QuotaDecision(
        EXIT_CODE_QUOTA_AVAILABLE,
        f"copilot-quota: {account_login} — premium interactions "
        f"{_describe_quota_amount(premium_snapshot)} — running Copilot.",
    )


def _parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the quota pre-check.

    Args:
        all_argv: Argument list excluding the program name, typically
            ``sys.argv[1:]``.

    Returns:
        Namespace exposing an ``account`` attribute holding the ``--account``
        value, or None when the flag is absent.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account",
        default=None,
        help=(
            "GitHub login whose Copilot premium-request quota to check; "
            "overrides COPILOT_QUOTA_ACCOUNT and the .env file"
        ),
    )
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Run the quota pre-check end-to-end and print its one-line decision.

    Args:
        all_arguments: Argument list excluding the program name.

    Returns:
        The pre-check exit code: 0 to run Copilot, or a non-zero skip code for
        out-of-quota (scenario A), quota API or access down (scenario B), and no
        account configured (scenario C).
    """
    arguments = _parse_arguments(all_arguments)
    decision = evaluate_copilot_quota(
        cli_account=arguments.account,
        env_file_path=COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH,
    )
    message_stream = (
        sys.stdout if decision.exit_code == EXIT_CODE_QUOTA_AVAILABLE else sys.stderr
    )
    print(decision.message, file=message_stream)
    return decision.exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
