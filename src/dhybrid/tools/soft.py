"""Tool 'power' — dependency opsional (psutil/jinja2/duckdb/pypdf/openpyxl).

Soft-register: kalau dependency belum terpasang, tool terdaftar sebagai stub
yang memberi pesan install ramah (spec tetap tampil supaya model tahu tool
ADA, tapi kalau dipanggil → arahan install). Kalau terpasang, fn sungguhan
dipakai. Modul tool yang belum tersedia di-skip tanpa crash.
"""
from __future__ import annotations

import importlib

POWER_EXTRA = "pip install -e '.[power]'"  # atau: pip install dhybrid-agent[power]

# Modul tool power; yang belum tersedia dilewati diam-diam.
_POWER_MODULES = ["power_sys", "power_scaffold", "power_data", "power_pdf", "power_xlsx"]


def _import_any(mods: list[str]):
    """Import modul pertama yang tersedia; None bila tidak ada sama sekali."""
    for m in mods:
        try:
            return importlib.import_module(m)
        except ImportError:
            continue
    return None


def _need(reg, name: str, mods: list[str], description: str, parameters: dict, fn) -> None:
    """Daftarkan tool: fn sungguhan bila dep ada, stub pesan install bila tidak."""
    if _import_any(mods) is None:

        def _missing(**kw) -> str:
            return (
                f"ERROR: tool '{name}' butuh package: {', '.join(mods)} — "
                f"install: {POWER_EXTRA}"
            )

        reg.register(
            name, description + " (butuh package opsional)", parameters, _missing
        )
        return
    reg.register(name, description, parameters, fn)


def register(reg, max_chars: int = 8000) -> None:
    """Daftarkan semua tool power yang modulnya tersedia (soft-register)."""
    for mod_name in _POWER_MODULES:
        try:
            mod = importlib.import_module(f"dhybrid.tools.{mod_name}")
        except ImportError:
            continue  # modul belum ada → skip aman
        mod.register(reg, _need=_need, max_chars=max_chars)
