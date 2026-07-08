# NAS SSH Invocation Policy

**When this applies:** Any `ssh`, `scp`, or `sftp` command against the NAS at `192.168.1.100`.

## Rule

Reach the NAS through the Windows OpenSSH binary with batch mode on. Git Bash's MSYS `ssh` reads `~/.ssh/id_ed25519` as world-readable through its ACL mapping, rejects the key as bad permissions, offers no key, and falls back to an interactive password prompt. In an unattended session no one answers that prompt, so the session hangs. The `System32/OpenSSH` binary authenticates the same key without a prompt.

Use this form for every NAS ssh command:

```
"/c/Windows/System32/OpenSSH/ssh.exe" -o BatchMode=yes -o ConnectTimeout=10 -p 9222 jon@192.168.1.100 "<cmd>"
```

`scp` and `sftp` take the matching `System32/OpenSSH` binary, `-o BatchMode=yes`, and port `9222` (`-P` for `scp`).

`-o BatchMode=yes` is required, not optional: it turns a key-authentication failure into a loud non-zero exit rather than a silent password prompt, so an auth regression surfaces as an error you can read.

## Enforcement

`nas_ssh_binary_enforcer.py` (PreToolUse on Bash) denies a bare `ssh`/`scp`/`sftp` command word aimed at `192.168.1.100` and points at the full-binary form. It also denies the full `System32/OpenSSH` binary to that host when the command omits `-o BatchMode=yes`. Commands to any other host, and commands that mention the address without an ssh-family command word, pass.
