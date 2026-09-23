# Second Claude account

A second Claude subscription runs agents on the same machine as the main account. The profile sync shares the main Claude home with the second account's profile. The picker reads both accounts' usage meters and names the account a job runs on. [The second account guide](../../../../packages/claude-dev-env/docs/second-claude-account.md) states the design.

## Sub-features

- Profile sync. `scripts/claude_account_profile.py` links each shared entry of the main home into `~/.claude-profiles/ev`, moves a stale copy into `.replaced/<time>/`, and removes a link whose main entry is gone.
- Per-account state. Sign-in, `.claude.json`, history, and the state folders in `claude_account_constants.py` stay in each profile and are never linked.
- Launcher. The sync writes `claude-ev.cmd`, which sets `CLAUDE_CONFIG_DIR` to the profile and passes every argument to `claude`.
- Account picker. `scripts/claude_account_choice.py` prints one JSON object with `account`, `config_dir`, `reason`, and both accounts' `meters`.
- Chain usage. `scripts/claude_chain_usage.py` prints the weekly remaining percent for each account in `claude-chain.json`. The picker reads its meters through the same probe.

## How to get to it (user POV)

A user runs the profile sync once, then signs the second account in with `claude-ev auth login`. A runner job calls the picker before it starts Claude, and runs under the `config_dir` the picker prints.

## Driving it with Python

Run the unit tests from the repository root:

```powershell
python -m pytest packages/claude-dev-env/scripts/test_claude_account_profile.py packages/claude-dev-env/scripts/test_claude_account_choice.py packages/claude-dev-env/scripts/test_claude_chain_usage.py -q
```

Drive the sync against a disposable home. Pass all three paths, so the run writes nothing under the user home:

```powershell
python packages/claude-dev-env/scripts/claude_account_profile.py --main-home <tmp>/main --profile-home <tmp>/profiles/ev --launcher-directory <tmp>/bin
```

The first run lists each shared entry under `linked`. A second run prints empty `linked`, `moved_aside`, and `unlinked` lists. A plain folder in the profile under a shared name moves to `.replaced/<time>/` and reports under `moved_aside`. An entry removed from the main home reports under `unlinked`. A per-account name such as `.credentials.json` never appears in `linked`.

Drive the picker with two config folders that hold no sign-in:

```powershell
python packages/claude-dev-env/scripts/claude_account_choice.py --main-config-dir <tmp>/main --second-config-dir <tmp>/profiles/ev
```

It exits 0 and prints `"account": "second"`, the unreadable-meter reason, and `null` for both meters. That run sends no network request.

Drive the chain report with a missing config:

```powershell
python packages/claude-dev-env/scripts/claude_chain_usage.py --config-path <tmp>/missing.json
```

It exits 3 and names the missing file on stderr.

## Live meters

A picker run that reads live meters needs both accounts signed in. Run it as a job on the machine that holds the sign-ins, from a pinned commit of this repository. Read the printed `account` and `meters`. An account whose stored token has expired prints `stored access token is expired; probe unavailable` on stderr and shows `null` meters until its next Claude run refreshes the sign-in. A `wait` answer carries the next reset time in `reason`. Keep the job's output out of this repository, since it names local paths.

## Gotchas

- Never read, print, or copy a `.credentials.json` file. A credential file that holds a token makes the picker call the usage endpoint, so a disposable run keeps its config folders free of one.
- An unread main meter never picks main.
- On Windows a shared directory links as a junction. On other systems it links as a symbolic link. A shared file links as a symbolic link, or as a hard link when the system refuses a symbolic link.
- The launcher is a Windows command file. On other systems the proof reads its text and does not run it.
