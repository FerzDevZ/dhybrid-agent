"""UI rich — panel & tabel profesional, hemat biaya: otomatis polos di
non-TTY (pipe/CI) dan saat NO_COLOR diset (standar no-color.org).

Semua helper punya fallback teks polos: kalau rich gagal import (env
minimal), UI tetap berfungsi.
"""

from __future__ import annotations

import io
import os

_NO_COLOR = bool(os.environ.get("NO_COLOR"))


def _console():
    from rich.console import Console

    return Console(no_color=_NO_COLOR)


def render_done(text: str) -> str:
    """Render blok DONE jadi Panel rich → string siap print (atau langsung
    pakai `print_done`). Polos saat non-TTY/NO_COLOR."""
    try:
        from rich import box
        from rich.console import Console
        from rich.panel import Panel

        buf = io.StringIO()
        Console(file=buf, no_color=_NO_COLOR).print(
            Panel(text, border_style="dim", box=box.ROUNDED, padding=(0, 1), title="[bold]DONE[/bold]")
        )
        return buf.getvalue().rstrip()
    except Exception:  # noqa: BLE001 — rich tak tersedia → teks polos
        return text


def print_done(text: str) -> None:
    """Print blok DONE: Panel rich di TTY, teks polos di non-TTY/NO_COLOR."""
    try:
        from rich import box
        from rich.panel import Panel

        _console().print(Panel(text, border_style="dim", box=box.ROUNDED, padding=(0, 1), title="[bold]DONE[/bold]"))
    except Exception:  # noqa: BLE001
        print(text)


def print_tokens(
    label: str,
    totals: dict,
    per_session: list[tuple[str, dict]] | None = None,
) -> None:
    """Dashboard /tokens: rich Table saat TTY; format teks polos sebaliknya."""
    tot_p, tot_c, tot_cached, cost = (
        totals.get("prompt", 0),
        totals.get("completion", 0),
        totals.get("cached", 0),
        totals.get("cost", 0.0),
    )
    try:
        from rich import box
        from rich.table import Table

        t = Table(
            title=f"penggunaan token ({label})",
            box=box.SIMPLE_HEAD,
            title_style="bold cyan",
            header_style="bold",
        )
        t.add_column("metrik")
        t.add_column("jumlah", justify="right")
        t.add_row("prompt", f"{tot_p:,}")
        t.add_row("completion", f"{tot_c:,}")
        t.add_row("cached", f"{tot_cached:,}")
        t.add_row("cache-hit", f"{(tot_cached / tot_p * 100) if tot_p else 0:.1f}%")
        t.add_row("estimasi", f"${cost:.4f}")
        _console().print(t)
        if per_session:
            t2 = Table(title="per sesi", box=box.SIMPLE_HEAD, title_style="bold cyan", header_style="bold")
            t2.add_column("sesi")
            t2.add_column("prompt", justify="right")
            t2.add_column("completion", justify="right")
            t2.add_column("cached", justify="right")
            t2.add_column("biaya", justify="right")
            for sid, b in per_session:
                t2.add_row(sid, f"{b['prompt']:,}", f"{b['completion']:,}", f"{b['cached']:,}", f"${b['cost']:.4f}")
            _console().print(t2)
    except Exception:  # noqa: BLE001 — rich tak tersedia → format polos
        print(f"penggunaan token ({label}):")
        print(f"  prompt       : {tot_p:>10,}")
        print(f"  completion   : {tot_c:>10,}")
        print(f"  cached       : {tot_cached:>10,}")
        print(f"  cache-hit    : {(tot_cached / tot_p * 100) if tot_p else 0:5.1f}%")
        print(f"  estimasi     : ${cost:.4f}")
        if per_session:
            print("\nper sesi:")
            for sid, b in per_session:
                print(f"  {sid}  p={b['prompt']:,} c={b['completion']:,} cached={b['cached']:,} ${b['cost']:.4f}")
