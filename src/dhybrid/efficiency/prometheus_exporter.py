"""Prometheus-style metrics exporter (text exposition format).

Bersyarat opsional -- tidak jalankan HTTP server default. Cuma export REGISTRY ke
format yang bisa scraped oleh prometheus /metrics endpoint. Contoh:

    from dhybrid.efficiency.prometheus_exporter import export_metrics
    print(export_metrics())

Optional HTTP server untuk /metrics endpoint:

    from dhybrid.efficiency.prometheus_exporter import start_metrics_server
    server = start_metrics_server(port=9090)
    # ... server runs in background thread
    server.shutdown()
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from dhybrid.efficiency.metrics import REGISTRY, Counter, Histogram


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler untuk /metrics endpoint."""

    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(export_metrics().encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default log messages."""


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


def format_histogram(h: Histogram, name: str | None = None) -> str:
    """Format sebuah Histogram ke prometheus text exposition format."""
    n = name or h.name
    desc = h.description or ""
    lines = [
        f"# HELP {n} {desc}",
        f"# TYPE {n} histogram",
    ]
    # Bucket counts (cumulative)
    for boundary in sorted(h._bucket_counts.keys()):
        count = h._bucket_counts[boundary]
        if boundary == float("inf"):
            lines.append(f'{n}_bucket{{le="+Inf"}} {count}')
        else:
            lines.append(f'{n}_bucket{{le="{boundary}"}} {count}')
    # Count and sum
    lines.append(f"{n}_count {h.count}")
    lines.append(f"{n}_sum {h.sum}")
    return "\n".join(lines)


def export_metrics() -> str:
    """Export seluruh REGISTRY ke prometheus text format (newline-separated)."""
    blocks = []
    for name in REGISTRY.names:
        item = REGISTRY.get(name)
        if isinstance(item, Counter):
            blocks.append(format_counter(item))
        elif isinstance(item, Histogram):
            blocks.append(format_histogram(item))
    return "\n\n".join(blocks)


def start_metrics_server(port: int = 9090, host: str = "127.0.0.1") -> HTTPServer:
    """Start HTTP server untuk /metrics endpoint di background thread.

    Host default localhost (127.0.0.1) supaya endpoint /metrics tidak
    terekspos ke interface lain tanpa diminta. (bandit B104)

    Args:
        port: Port untuk bind (0 = random free port)
        host: Host interface

    Returns:
        HTTPServer instance (call .shutdown() untuk stop)
    """
    server = HTTPServer((host, port), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
