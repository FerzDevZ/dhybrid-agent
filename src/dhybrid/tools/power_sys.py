"""Tool power: sys_info — kesehatan sistem via psutil.

Soft-register via dhybrid.tools.soft: dep `psutil` opsional (extra power).
"""
from __future__ import annotations

import psutil


def _sys_info() -> str:
    vm = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage("/").percent
    except OSError:
        disk = -1.0
    lines = [
        f"CPU: {psutil.cpu_percent(interval=0.2)}% ({psutil.cpu_count()} core)",
        f"RAM: {vm.percent}% terpakai ({vm.available // (1 << 20)} MB bebas)",
        f"Disk: {disk}% terpakai",
        f"Proses: {len(psutil.pids())} berjalan",
    ]
    return "\n".join(lines)


def _default_need(reg, name, mods, description, parameters, fn) -> None:
    reg.register(name, description, parameters, fn)


def register(reg, _need=None, **kw) -> None:
    """Daftarkan sys_info; _need dipakai soft.py untuk soft-register."""
    (_need or _default_need)(
        reg,
        "sys_info",
        ["psutil"],
        "Cek kesehatan sistem: CPU, RAM, disk, jumlah proses (psutil)",
        {},
        _sys_info,
    )
