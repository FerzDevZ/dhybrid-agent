"""Tool power: data_query — SQL read-only ke CSV/JSONL/Parquet via duckdb.

Query tulis (CREATE/INSERT/UPDATE/DELETE/DROP/dst) diblokir di level kode,
bukan hanya imbauan prompt. Hasil dipotong (hemat token).
"""
from __future__ import annotations

import duckdb

_FORBIDDEN = (
    "create",
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "attach",
    "copy",
    "export",
    "pragma",
)


def _is_write_query(sql: str) -> bool:
    low = " ".join(sql.lower().split())
    for k in _FORBIDDEN:
        if low.startswith(k) or f" {k} " in low:
            return True
    return False


def _data_query(sql: str, max_rows: int = 20) -> str:
    if _is_write_query(sql):
        return "ERROR: data_query read-only — query tulis (CREATE/INSERT/UPDATE/DELETE/dst) ditolak"
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(sql).fetchmany(max_rows + 1)
        cols = [d[0] for d in con.description or []]
    except Exception as e:  # noqa: BLE001 — error SQL apa pun jadi pesan bersih
        return f"ERROR: {e}"
    lines = ["\t".join(map(str, cols))]
    lines += ["\t".join(str(c) for c in r) for r in rows[:max_rows]]
    if len(rows) > max_rows:
        lines.append(f"... (potong {max_rows} baris)")
    return "\n".join(lines)


def _default_need(reg, name, mods, description, parameters, fn) -> None:
    reg.register(name, description, parameters, fn)


def register(reg, _need=None, max_chars: int = 8000, **kw) -> None:
    """Daftarkan data_query; _need dipakai soft.py untuk soft-register."""
    (_need or _default_need)(
        reg,
        "data_query",
        ["duckdb"],
        "Jalankan SQL read-only ke file CSV/JSONL/Parquet (analisis data tanpa Python; query tulis diblokir)",
        {
            "sql": {"type": "string"},
            "max_rows": {"type": "integer"},
        },
        _data_query,
    )
