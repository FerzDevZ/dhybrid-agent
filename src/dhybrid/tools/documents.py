"""Tool dokumen — baca PDF/DOCX/XLSX/PPTX/HTML → markdown (via markitdown).

Menutup gap: agent dulu hanya bisa baca file teks polos. Sekarang bisa
membaca laporan kantor & dokumen untuk diproses (ringkas, cari, ekstrak).
"""

from __future__ import annotations

from pathlib import Path

# Ekstensi yang langsung dibaca sebagai teks (tanpa konversi)
TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".toml", ".csv", ".xml", ".html", ".htm", ".css", ".sql", ".sh", ".log",
    ".ini", ".cfg", ".conf",
}


def _read_document(path: str, max_chars: int = 8000) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"ERROR: file tidak ditemukan: {path}"
    if p.is_dir():
        return f"ERROR: {path} adalah direktori, bukan file"
    try:
        if p.suffix.lower() in TEXT_EXTS:
            text = p.read_text(errors="replace")
        else:
            # markitdown: pdf/docx/xlsx/pptx/odt/epub/audio dll → markdown
            try:
                from markitdown import MarkItDown
            except ImportError:
                return (
                    f"ERROR: butuh markitdown untuk baca {p.suffix} — "
                    "install: pip install markitdown"
                )
            result = MarkItDown().convert(str(p))
            text = result.text_content or ""
        text = text.strip()
        if not text:
            return f"ERROR: tidak ada teks yang bisa dibaca dari {path}"
        head = f"# {p.name}\n\n{text}"
        if len(head) > max_chars:
            return head[:max_chars] + "\n[truncated]"
        return head
    except Exception as e:  # noqa: BLE001
        return f"ERROR baca {path}: {type(e).__name__}: {e}"


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "read_document",
        "baca dokumen: pdf/docx/xlsx/pptx/html (via markitdown) atau file teks",
        {"path": {"type": "string"}},
        lambda path: _read_document(str(path), max_chars),
    )
