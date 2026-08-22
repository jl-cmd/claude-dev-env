# Visual beats

Use one visual per reply, at most, sitting between beats in place
of the beat it explains.

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
