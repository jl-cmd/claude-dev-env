# Codex accounts

The codex_account_choice picker spreads agent work across up to four Codex
accounts on one machine. Each account signs in under
its own Codex home, and every home shares the same Codex setup: config, rules,
skills, plugins and prompts. A job asks the picker which account to use.

## Pieces

| File | What it does |
|---|---|
| `scripts/codex_account_choice.py` | `choose` names the account and tier a job runs on, `check` tells a running job whether its account is still above a floor, `sync` links the shared setup into every account's home |
| `scripts/codex_account_meters.py` | Reads one account's rate-limit windows through `codex app-server` with `CODEX_HOME` set to that account's home |
| `scripts/dev_env_scripts_constants/codex_account_constants.py` | The account names in try order, the shared entry names, the 10% bar and the 1% Luna stop |

## Names and order

The accounts are `codex-1`, `codex-2`, `codex-3` and `codex-4`. Their homes are
`~/.codex-profiles/codex-1` and so on, or under `CODEX_PROFILES_ROOT` when set.
Jobs try them in that order. The names say nothing about a plan, so a plan change
keeps every name. To change the order, sign the accounts into different folders.

## Sign in once

```
python packages/claude-dev-env/scripts/codex_account_choice.py sync
```

Then, for each account, sign in with that account's home:

```
$env:CODEX_HOME = "$HOME\.codex-profiles\codex-1"; codex login
```

The sign-in lives in that folder's `auth.json`. Only the entries in
`ALL_SHARED_CODEX_HOME_NAMES` link to `~/.codex`. Sign-in, sessions, history,
logs and state files stay per account.

## Which account a job uses

Room is the smaller of an account's two windows: the 5-hour window and the week.

| Condition | Answer |
|---|---|
| First account in order with more than 10% left | `normal` on that account |
| No account over 10%, one or more over 1% | `luna` on the account with the most room, `stop_below_percent` 1 |
| No account over 1% | `wait`, naming the account whose blocking windows reset first |
| Account not signed in, or its meter unread | skipped, with the reason in `accounts` |

```
python packages/claude-dev-env/scripts/codex_account_choice.py choose
{"tier": "normal", "account": "codex-1", "codex_home": "...\\codex-1", "percent_left": 62.0,
 "stop_below_percent": null, "reason": "codex-1 has 62% left", "accounts": [...]}
```

A job runs Codex with `CODEX_HOME` set to `codex_home`. On `luna`, the job runs
Luna and polls `check` between steps:

```
python packages/claude-dev-env/scripts/codex_account_choice.py check codex-2 --floor 1
```

`check` exits 0 while the account has more than the floor left, and 3 once it has
not or its meter is unread. The job stops on 3.

Pass `--codex-path` when `codex` is off PATH. Without it the picker also tries
the desktop install path under the user home.
