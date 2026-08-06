"""Tool files — baca dengan line-range (hemat token), tulis file baru."""

from __future__ import annotations

from pathlib import Path


def _fuzzy_resolve(path: str) -> Path | None:
    """Coba cari file nyata bila model menulis path tanpa ekstensi
    (mis. 'app.py' diketik 'app', 'requirements' tanpa '.txt').

    Aman: hanya mengembalikan path bila ada SATU kandidat unik, dan
    hanya untuk file yang sudah ADA (bukan untuk menulis file baru).
    """
    p = Path(path)
    if p.exists():
        return p
    candidates: list[Path] = []
    for ext in (
        ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".css",
        ".txt", ".md", ".yaml", ".yml", ".toml", ".sh", ".env", ".ini",
    ):
        cand = Path(str(p) + ext)
        if cand.exists():
            candidates.append(cand)
    # cari di parent dir: file yang startswith nama yang diketik
    parent = p.parent
    if parent.is_dir():
        try:
            candidates += [f for f in parent.iterdir() if f.is_file() and f.name.startswith(p.name)]
        except OSError:
            pass
    # unik & TIDAK ambigu
    unique = {str(c) for c in candidates}
    if len(unique) == 1:
        return Path(next(iter(unique)))
    return None


def read_file(path: str, offset: int = 1, limit: int = 100, max_chars: int = 8000) -> str:
    from dhybrid.tools.security import check_path_safe

    ok, reason = check_path_safe(path)
    if not ok:
        return f"ERROR: {reason}"
    p = _fuzzy_resolve(path)
    if p is None:
        return f"ERROR: file tidak ada: {path}"
    if str(p) != path:
        # kabari agent file mana yang sebenarnya dibaca
        path = str(p)
    try:
        lines = p.read_text(errors="replace").splitlines()
    except OSError as e:
        return f"ERROR: tidak bisa baca {path}: {e}"
    total = len(lines)
    start = max(offset - 1, 0)
    chunk = lines[start : start + limit]
    head = f"{path} ({total} baris, menampilkan {start + 1}-{start + len(chunk)})"
    body = "\n".join(f"{i + 1}|{ln}" for i, ln in enumerate(chunk, start=start))
    out = f"{head}\n{body}"
    return out[:max_chars] + ("\n[truncated]" if len(out) > max_chars else "")


def write_file(path: str, content: str) -> str:
    from dhybrid.tools.security import check_path_safe

    ok, reason = check_path_safe(path)
    if not ok:
        return f"ERROR: {reason}"
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"OK: {path} ditulis ({len(content)} chars)"


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "read_file",
        "Baca file dengan line range (offset, limit). JANGAN baca file penuh tanpa perlu — baca range kecil dulu.",
        {"path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
        lambda path, offset=1, limit=100: read_file(path, offset, limit, max_chars=max_chars),
    )
    reg.register(
        "write_file",
        "Tulis file BARU (untuk edit file lama gunakan apply_patch).",
        {"path": {"type": "string"}, "content": {"type": "string"}},
        lambda path, content: write_file(path, content),
    )
