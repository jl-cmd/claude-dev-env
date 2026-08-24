# PII redaction checklist

The PII pass runs on every closeout run, over every issue body and over the handoff prompt, before the confirmation gate. Repository visibility changes how aggressive the redaction is — public repos get the strictest pass — never whether the pass runs.

## The pass

Read each drafted body and the handoff prompt line by line. For every match below, swap the real value for the placeholder. When a value is load-bearing for the fix (a hook needs the exact path shape), keep the shape and drop the private part — `~/.claude/hooks/<hook>.py`, not the full home path.

| Category | What to catch | Swap |
|---|---|---|
| Email | Any address | `<email>` |
| Real name | A person's name in a path, log line, or account | `<name>` |
| Home path | A user home directory | `~/` or `<home>/` |
| Private host / IP | A LAN host, NAS name, private IP | `<host>` |
| SSH user / port | A login user or non-standard port | `<user>`, `<port>` |
| Account id | A store, cloud, app, or master-user id | `<account-id>` |
| Token / secret | An API key, token, or credential | `<redacted>` |
| Private repo name | An unpublished owner/repo | `<owner>/<repo>` |
| Sheet / DB / script id | A Neon, Sheet, or Apps Script id | `<id>` |

## Public versus private aggression

| Target repo | Aggression |
|---|---|
| Public (ships to a public host, open source) | Strictest: redact every category above, and any value a stranger could tie to a person or a private system. When in doubt, redact. |
| Private (internal, team-only) | Redact tokens, secrets, credentials, and emails without exception. Keep internal host and path shapes only when the fix needs them. |

## After the pass

- List every redaction made, so the confirmation gate shows the user what changed.
- When a redaction removes a value the fix needs, note it as an open question for the user in the gate — do not guess a replacement.
- A body that still holds a match after the pass does not reach the gate. Re-run the pass until every match is swapped.

## Why the pass is unconditional

An issue is a durable post on a shared server. A private value in an issue body outlives the session and the person who typed it. Running the pass on every body, public or private, keeps a leak from landing where it cannot be pulled back.
