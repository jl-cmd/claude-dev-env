# NAS SSH Invocation Policy

Reach the NAS through the Windows `System32/OpenSSH` binary with `-o BatchMode=yes` on every `ssh`, `scp`, or `sftp` command:

```
"/c/Windows/System32/OpenSSH/ssh.exe" -o BatchMode=yes -o ConnectTimeout=10 -p 22 operator@nas.example.local "<cmd>"
```

Git Bash's MSYS `ssh` falls back to an interactive password prompt that hangs an unattended session; the `System32/OpenSSH` binary authenticates the key without a prompt, and `-o BatchMode=yes` turns an auth failure into a loud non-zero exit. `nas_ssh_binary_enforcer.py` (PreToolUse on Bash) enforces this: it denies a bare ssh-family word aimed at the NAS, and denies the full binary when `-o BatchMode=yes` is absent.

Host, user, and port config, the `scp`/`sftp` forms, and the full rationale: `@~/.claude/docs/nas-ssh-invocation.md`.
