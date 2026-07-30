---
name: beat-sheet
description: "Formats a reply as single-line beats. Use for '/beat-sheet', 'beat sheet this', 'give me the beats', or 'write this as beats'."
---

# beat-sheet

Write in single-line beats. Every line is one complete thought,
under 12 words. Blank line between every line. Never write a
paragraph. Ten lines at most. Never repeat a point. Order:
situation, problem, fix, how it works. Put any command in its own
code fence. Start with one short bold title line. Use plain
everyday words a tired reader can skim.

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
