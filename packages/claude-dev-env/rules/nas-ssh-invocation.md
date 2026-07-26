# Running Commands on the NAS

Reach the NAS through the `nas_ssh_key.py` runner, never through `ssh`, `scp` or `sftp`:

```
python <runner-path> <command-script.sh> <private-key-path>
```

The first argument is a **path to a file** holding a bash script, not a command string. Write that
file with the Write tool. The whole script runs in one shell, so variables, `cd` and `source` carry
from line to line.

The runner ships with the automation project it serves; read its path from that project's own
reference. Use the ops key under `~/.claude/keys` — keys under `~/.ssh` either carry a passphrase,
which cannot be answered unattended, or belong to other hosts.

The runner loads the key with paramiko and signs in the same process. The command-line clients check
the key file's permissions first and refuse it, and Git Bash's `ssh` then falls back to a password
prompt that hangs an unattended run. `nas_ssh_binary_enforcer.py` (PreToolUse on Bash) denies a bare
ssh-family word aimed at the NAS, and denies the full `System32/OpenSSH` binary when
`-o BatchMode=yes` is missing.

Host, ssh port and ssh user are constants inside the runner and are also under the `nas` key in
`~/.claude/local-identity.json`. Keep all three out of anything committed or posted.

To copy a file, write it inside the script with a quoted heredoc rather than reaching for `scp`.

The `/tmp` size limit, how to tell a real break from a platform-only one, and a failure-to-cause
table: `@~/.claude/docs/nas-ssh-invocation.md`.
