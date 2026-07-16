# NAS SSH Invocation Policy

Full detail behind the always-on `rules/nas-ssh-invocation.md` kernel. It applies to any `ssh`, `scp`, or `sftp` command against the NAS.

## Why the Windows OpenSSH binary

Git Bash's MSYS `ssh` reads `~/.ssh/id_ed25519` as world-readable through its ACL mapping, rejects the key as bad permissions, offers no key, and falls back to an interactive password prompt. In an unattended session no one answers that prompt, so the session hangs. The `System32/OpenSSH` binary authenticates the same key without a prompt.

## The form to use

```
"/c/Windows/System32/OpenSSH/ssh.exe" -o BatchMode=yes -o ConnectTimeout=10 -p 22 operator@nas.example.local "<cmd>"
```

`scp` and `sftp` take the matching `System32/OpenSSH` binary, `-o BatchMode=yes`, and the same port (`-P` for `scp`).

The host, ssh user, and port come from the `CLAUDE_NAS_*` environment variables or `~/.claude/local-identity.json`; the committed examples show placeholders (`nas.example.local`, `operator`, `22`).

`-o BatchMode=yes` is required, not optional: it turns a key-authentication failure into a loud non-zero exit rather than a silent password prompt, so an auth regression surfaces as an error you can read.

## Enforcement

`nas_ssh_binary_enforcer.py` (PreToolUse on Bash) denies a bare `ssh`/`scp`/`sftp` command word aimed at the NAS host and points at the full-binary form. It also denies the full `System32/OpenSSH` binary to that host when the command omits `-o BatchMode=yes`. Commands to any other host, and commands that mention the address without an ssh-family command word, pass.
