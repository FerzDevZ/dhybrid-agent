"""Prometheus-style metrics exporter (text exposition format).

Bersyarat opsional -- tidak jalankan HTTP server default. Cuma export REGISTRY ke
format yang bisa scraped oleh prometheus /metrics endpoint. Contoh:

    from dhybrid.efficiency.prometheus_exporter import export_metrics
    print(export_metrics())
"""
from __future__ import annotations

from dhybrid.efficiency.metrics import REGISTRY, Counter


def format_counter(c: Counter, name: str | None = None) -> str:
    """Format sebuah Counter ke prometheus text exposition format."""
    n = name or c.name
    desc = c.description or ""
    lines = [
        f"# HELP {n} {desc}",
        f"# TYPE {n} counter",
        f"{n} {c.value}",
    ]
    return "\n".join(lines)


def export_metrics() -> str:
    """Export seluruh REGISTRY ke prometheus text format (newline-separated)."""
    blocks = []
    for name in REGISTRY.names:
        item = REGISTRY.get(name)
        if isinstance(item, Counter):
            blocks.append(format_counter(item))
    return "\n\n".join(blocks)
