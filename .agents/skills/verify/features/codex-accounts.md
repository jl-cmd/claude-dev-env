# Codex accounts

The codex_account_choice picker reads the rate-limit windows of up to four Codex accounts, each signed in under its own Codex home, and names the account and tier a job runs on. [The guide](../../../../packages/claude-dev-env/docs/codex-accounts.md) states the design.

## Sub-features

- Home sync. `scripts/codex_account_choice.py sync` links the shared entries of `~/.codex` into `~/.codex-profiles/codex-1` through `codex-4`.
- Per-account state. Every entry outside `ALL_SHARED_CODEX_HOME_NAMES` stays in each home and is never linked.
- Meter read. `scripts/codex_account_meters.py` starts `codex app-server` with `CODEX_HOME` set, sends the handshake and `account/rateLimits/read`, and keeps standard input open until the reply lands.
- Picker. `choose` prints `tier`, `account`, `codex_home`, `percent_left`, `stop_below_percent`, `reason`, and every account's reading.
- Luna stop. `check <account> --floor 1` exits 0 above the floor and 3 at or below it.
- Luna 5-hour floor. An account that reports a 5-hour window takes `luna` only with at least 20% of that window left.

## How to get to it (user POV)

A user runs `sync` once, then signs each account in with `CODEX_HOME` set to its home and `codex login`. A runner job calls `choose` before it starts Codex, and runs under the `codex_home` it prints.

## Driving it with Python

Run the unit tests from the repository root:

```powershell
python -m pytest packages/claude-dev-env/scripts/test_codex_account_choice.py packages/claude-dev-env/scripts/test_codex_account_meters.py -q
```

Drive the picker against an empty profiles root:

```powershell
python packages/claude-dev-env/scripts/codex_account_choice.py --profiles-root <tmp>/profiles choose
```

It exits 0 and prints `"tier": "wait"`, the reason `no account meter could be read`, and `not signed in` for all four accounts. That run starts no Codex process.

Drive the sync against a disposable home:

```powershell
python packages/claude-dev-env/scripts/codex_account_choice.py --profiles-root <tmp>/profiles sync --main-home <tmp>/main
```

Each account lists its shared entries under `linked`. A second run prints empty lists.

## Live meters

A live `choose` needs the accounts signed in on the machine that runs the job. Run it there from a pinned commit of this repository. Each signed-in account shows `percent_left` and its windows, with the 5-hour window at 300 minutes and the week at 10080. Keep the job's output out of this repository, since it names local paths.

## Gotchas

- Never read, print, or copy an `auth.json` file.
- The server exits without answering once its standard input closes, so the reader holds input open until the reply arrives or 30 seconds pass.
- An unread meter never takes a job. A `wait` with every account unread names no reset.
