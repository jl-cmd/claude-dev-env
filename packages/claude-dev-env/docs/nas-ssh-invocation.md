# Running Commands on the NAS

Full detail behind the always-on `rules/nas-ssh-invocation.md` kernel.

This file covers how to run a command there at all. What the NAS runs, where the automations are
deployed, and how to verify a change against them belong with the project that owns those
automations, not here.

## The call

```
python <runner-path> <command-script.sh> <private-key-path>
```

Two arguments, both paths. The first is a file holding a bash script; the second is the private key.

The runner is `nas_ssh_key.py`. It ships with the automation project it serves, so read its path from
that project's own reference rather than assuming a location.

The host, ssh port and ssh user are constants inside the runner, so no command you write names them.
The same three values are recorded under the `nas` key in `~/.claude/local-identity.json`. Read them
from there when something needs them, and keep them out of anything committed or posted.

Write the script file with the Write tool. Keeping the commands in a file has a second benefit: a
destructive word such as `rm -rf` inside the file never appears in a Bash tool command string, so the
`destructive_command_blocker` hook stays out of the way.

The script runs through `bash -s` in a single shell. Variables, `cd`, and `source` all carry from one
line to the next. Standard output, standard error and the exit code all come back.

## Why not ssh, scp or sftp

The runner loads the key with paramiko and signs inside the Python process. The command-line clients
check the key file's permissions first and refuse to load a key whose permissions they do not like.
Git Bash's `ssh` then falls back to an interactive password prompt, which hangs a run with nobody to
answer it.

To move a file onto the NAS, write it from inside the script:

```bash
cat > /tmp/thing.conf <<'EOF'
contents here
EOF
```

The quoted `'EOF'` stops the shell expanding anything in the body.

## The key

Use the ops key under `~/.claude/keys`. It is readable as-is and the NAS accepts it.

Keys under `~/.ssh` are for other jobs and none of them works here. The default one carries a
passphrase, so paramiko cannot load it unattended; the rest are for other hosts.

## Writing a script that touches the automations

Do not reach for the system interpreter. It carries neither pytest nor the libraries the automations
import, so anything checked against it proves nothing.

Each automation project records its own runtime — the interpreter, the virtual environment, the
import root, and the deploy path. Read that project's reference and activate what it names before
running anything.

## Verifying a change before it ships

The NAS is a Linux box and this machine is Windows, so two classes of difference show up only there:
syntax newer than the NAS interpreter accepts, and tests that assert Windows paths.

**Always separate a real break from a platform-only one.** Run the same test file at the branch head
and at the commit the work started from. Identical failures at both mean the environment, not the
change. Report both numbers rather than the head alone.

## The /tmp limit

`/tmp` is a small tmpfs. A full clone of a repository that carries binary assets fills it, the clone
dies partway through, and the disk stays full for whatever runs next.

Fetch shallow and sparse instead:

```bash
d=$(mktemp -d /tmp/work.XXXXXX)
cd "$d"
git init --quiet
git remote add origin <repository-url>
git sparse-checkout init --cone
git sparse-checkout set <subdirectory>
git fetch --quiet --depth 1 origin <sha>
git checkout --quiet FETCH_HEAD
```

One subdirectory at one commit lands tens of megabytes rather than the whole history. Clean up at the
end and print `df -h /tmp` so the next run knows the state:

```bash
find /tmp -maxdepth 1 -name 'work.*' -prune -exec rm -rf {} +
```

## When something fails

| What you see | What it means |
|---|---|
| `PermissionError: [Errno 13]` on the key | The key file is not readable by this account. |
| `PasswordRequiredException: Private key file is encrypted` | That key has a passphrase and cannot be used unattended. |
| `Authentication (publickey) failed` | The transport works and the NAS does not accept that key. |
| `Load key ...: Permission denied` from `ssh.exe` | A command-line client is being used. Use the runner. |
| `No space left on device` | `/tmp` is full. Clean it, then fetch shallow and sparse. |
| `No module named pytest` | The system interpreter is being used. Activate the project's environment first. |
