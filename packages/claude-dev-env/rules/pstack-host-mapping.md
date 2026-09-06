# Pstack host mapping

Pstack skills ship with one host's tool names and paths written into their steps. The
active host supplies the real ones. Read a pstack step for the shape of the work, and take
the tool name, the skill home, and the transcript location from the host you run on.

[`pstack-models.md`](pstack-models.md) covers the model choice for each role. This rule
covers everything else a pstack step names.

## What each host supplies

| A pstack step names | Take from the host |
|---|---|
| A subagent tool | The native subagent tool this session exposes, with its own agent-type field |
| A skills directory | The skills home this host reads |
| A transcript directory | The session transcript location this host writes |
| A model identifier | The identifiers the native subagent tool accepts today |

A pstack step that names one host's directory means "the matching directory here". Resolve
it before the search, and search only inside the active workspace.

## The final message is the whole report

On a host where a subagent returns one message to its parent, that message is all the
parent receives. Working notes, tool output, and text the child printed along the way do
not travel.

So every pstack prompt that asks a child for a list, a set of findings, or a verdict also
asks for the whole thing, word for word, in the final message. A prompt without that line
gets back a summary such as "findings reported above", and the findings are gone. The
parent then reruns the child, which costs the full run a second time.

## Panel spawns

Panel size and model diversity follow `pstack-models.md`. Two host limits shape a spawn
beyond that:

- A spawn gate can refuse a model tier. Read the denial, take the tier it names as
  allowed, and spawn again.
- A host may accept fewer distinct models than a panel asks for. A panel that requires
  distinct models stops; a panel that treats diversity as optional runs with repeats.

## Editing pstack

Pstack installs as a plugin. A plugin update overwrites its files, so an edit inside a
pstack skill lasts until the next update. Durable changes belong in a rule beside this
one. The installer copies this package's rules into the managed rules directory and
generates the Cursor copy from the same source.
