from __future__ import annotations

from collections.abc import Iterable

from rich.console import Console
from rich.table import Table

console = Console()

def print_table(title: str, columns: list[str], rows: Iterable[Iterable[str]]):
    t = Table(title=title, show_lines=False)
    for c in columns:
        t.add_column(c)
    for r in rows:
        t.add_row(*[str(x) for x in r])
    console.print(t)
