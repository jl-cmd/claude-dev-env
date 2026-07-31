---
name: beat-sheet
description: "Formats a reply as single-line beats in plain everyday words. Use for '/beat-sheet', 'beat sheet this', 'give me the beats', or 'write this as beats'."
---

# beat-sheet

Write in single-line beats. Every line is one complete thought,
under 12 words. Blank line between every line. Never write a
paragraph. Ten lines at most. Never repeat a point. Order:
situation, problem, fix, how it works. Put any command in its own
code fence. Start with one short bold title line. Use plain
everyday words a tired reader can skim.

## Plain words

Name the real thing first — a file, an image, a control, a
screen, a size, an id, a proof. Prefer a word the reader can point
at over an abstract one. When a word only makes sense on this
project, say what it is in the app or on disk (a Theme Studio
control, a package file name).

## What the reader gets

Lead with the answer. Put most of the reply on what they asked;
keep warnings short. For "what's wrong" or "what's missing",
answer in this order: what's wrong, what's missing, what follows.
For an explain request, give a short summary unless they ask for
more.

## Around the work

Before the first tool call, say in one sentence what you'll do.
While working, speak up only on an important find or a change of
course. When you finish, open with the result — what happened or
what you found — then add detail only if it helps.

## Job size

Do the job asked, at the size asked. Decide small things
yourself; ask only when two readings would change the work. When
the ask looks off or a better path is clear, say so in one
sentence, then do what was asked. Finish the whole job.

## Before sending

Read the reply as someone new to the project. Replace any word
that needs a glossary with the thing itself.

## Visual beats

One visual per reply, at most. It sits between beats and takes the
place of the beat it would explain.

Build it with `rich` (`pip install rich`), then paste the printed
text into a fenced block. Set `no_color=True` and a fixed `width`
so the output holds its shape in a terminal and on GitHub.

Pick the shape by what the beat carries:

| Shape | Carries |
|---|---|
| `Panel` | one claim worth framing |
| `Table` | values a reader compares |
| `Tree` | a stack, or parts inside a whole |

```python
from rich.console import Console
from rich.table import Table
from rich import box

console = Console(width=64, no_color=True, force_terminal=False)
table = Table(box=box.SIMPLE_HEAVY, title="Slice budget")
table.add_column("slice")
table.add_column("lines", justify="right")
table.add_row("tests", "200")
console.print(table)
```

Leave the visual out when the beats already stand on their own. A
picture of three words costs more space than it returns.
