"""Tool power: pdf_ops — merge PDF via pypdf.

Melengkapi tools/documents.py (baca PDF → markdown) dengan operasi tulis.
"""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter


def _pdf_merge(sources: list[str], target: str) -> str:
    writer = PdfWriter()
    for s in sources:
        p = Path(s)
        if not p.exists():
            return f"ERROR: file tidak ada: {s}"
        try:
            writer.append(str(p))
        except Exception as e:  # noqa: BLE001 — PDF korup → pesan bersih
            return f"ERROR: gagal baca {s}: {e}"
    t = Path(target)
    t.parent.mkdir(parents=True, exist_ok=True)
    with open(t, "wb") as fh:
        writer.write(fh)
    return f"OK: {len(sources)} pdf digabung → {target}"


def _default_need(reg, name, mods, description, parameters, fn) -> None:
    reg.register(name, description, parameters, fn)


def register(reg, _need=None, **kw) -> None:
    """Daftarkan pdf_ops; _need dipakai soft.py untuk soft-register."""
    (_need or _default_need)(
        reg,
        "pdf_ops",
        ["pypdf"],
        "Gabungkan (merge) beberapa file PDF menjadi satu (pypdf)",
        {
            "sources": {"type": "array"},
            "target": {"type": "string"},
        },
        _pdf_merge,
    )
