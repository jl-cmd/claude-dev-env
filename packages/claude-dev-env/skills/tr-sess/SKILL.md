---
name: tr-sess
description: >-
  Copy one Claude Code session from a source profile into a destination profile so it
  appears in that profile's session list and resumes there.
  Triggers: /tr-sess, transfer session, move a chat to another profile, copy a session
  between profiles, transfer chat between Claude clients, make a session resumable in
  another profile.
---

# tr-sess

Copies a session between profiles under the per-user profiles root.

**Announce at start:** "Transferring the session."

## Arguments

`/tr-sess <source> <destination>`

Both name profile directories under the profiles root. Name the session with
`--session-id`. To choose one, run `--list` against the source and let the user pick.

## What a session is on disk

Four pieces. The session list is exactly the transcripts on disk plus the config entry,
so copying these four completes the transfer:

| Piece | Path |
|---|---|
| Transcript | `<profile>/projects/<project-key>/<session-id>.jsonl` |
| Session directory | `<profile>/projects/<project-key>/<session-id>/` |
| Task and env state | `<profile>/tasks/<session-id>`, `<profile>/session-env/<session-id>` |
| Trust entry | the session's working directory as a key in `<profile>/.claude.json` |

## Steps

1. List candidates when the user has yet to name a session:

   ```
   python scripts/transfer_session.py --source <source> --destination <dest> --list
   ```

   Show the id, title, project key, and size. Ask which one.

2. Copy it:

   ```
   python scripts/transfer_session.py --source <source> --destination <dest> --session-id <uuid>
   ```

3. Read the JSON result. Confirm `hashMatch` is `true`. Report the copied byte and line
   counts and the config action.

4. The destination client reads its session list at startup, so a restart surfaces the
   copied session. Ask through `AskUserQuestion` whether to restart it for them:

   | Option | Meaning |
   |---|---|
   | Restart it for me | Relaunch the destination client, then confirm the session is listed |
   | I'll restart it myself | Report the session id and title so the user finds it |

   On "restart it for me", relaunch through the destination profile's own launcher and
   confirm the session appears. Otherwise report the session id and title.

## Flags

| Flag | Effect |
|---|---|
| `--list` | List sessions in the source profile |
| `--session-id <uuid>` | The session to copy |
| `--profiles-root <path>` | Profiles root; defaults to the per-user root |
| `--force` | Overwrite a destination transcript that carries extra work |

## The divergence guard

A live session keeps appending to its transcript, so the copy stops at the last
complete line and is verified against the same-length prefix of the source.

When the destination transcript is larger than the source, the destination holds turns
of its own — work done after an earlier copy. The script keeps that work and exits `3`.
Pass `--force` to replace it with the source copy.

Re-running a copy refreshes the destination and is safe to repeat.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Copied, or listed |
| `2` | Usage error: unknown profile, unknown session, one profile named twice, missing session id |
| `3` | Destination carries extra work; pass `--force` to replace it |

## Scope

The source stays as it is, and transcript content transfers verbatim.
