"""Tool apply_patch — edit file dengan diff minimal (penghemat token terbesar).

Format (lebih ringkas dari unified diff standar):

    --- path/relatif.py
    @@ konteks opsional (diabaikan)
    -baris lama
    +baris baru
    baris konteks (opsional, untuk penempatan)

Kasus: replace (ada - dan +), delete (hanya -), insert (hanya +, butuh konteks).
"""

from __future__ import annotations

from pathlib import Path


def _find_contiguous(old: list[str], seq: list[str]) -> int | None:
    if not seq:
        return None
    n, m = len(old), len(seq)
    for i in range(n - m + 1):
        if old[i : i + m] == seq:
            return i
    return None


def _parse(patch_text: str) -> tuple[str, list[str], list[str], list[str]]:
    """Return (path, removals, additions, contexts)."""
    lines = patch_text.splitlines()
    if not lines or not lines[0].startswith("--- "):
        raise ValueError("patch harus dimulai dengan '--- path'")
    path = lines[0][4:].strip()
    removals, additions, contexts = [], [], []
    for ln in lines[1:]:
        if ln.startswith("@@") or not ln.strip():
            continue
        if ln.startswith("-"):
            removals.append(ln[1:])
        elif ln.startswith("+"):
            additions.append(ln[1:])
        elif ln.startswith(" "):
            contexts.append(ln[1:])
        else:
            # baris tanpa prefix = konteks
            contexts.append(ln)
    return path, removals, additions, contexts


def apply_patch(patch_text: str, base_dir: str = ".") -> str:
    from dhybrid.tools.security import check_path_safe

    try:
        path, removals, additions, contexts = _parse(patch_text)
    except ValueError as e:
        return f"ERROR: {e}"
    ok, reason = check_path_safe(path, base=Path(base_dir))
    if not ok:
        return f"ERROR: {reason}"
    target = Path(base_dir) / path
    if not target.exists():
        return f"ERROR: target tidak ada: {path}"
    old = target.read_text(errors="replace").splitlines()

    if removals or additions:
        old_seq = contexts + removals
        new_seq = additions
    else:
        return "ERROR: patch kosong (tidak ada baris - atau +)"

    idx = _find_contiguous(old, old_seq) if old_seq else None

    if idx is None and contexts:
        # fallback: cari hanya blok konteks
        idx = _find_contiguous(old, contexts)
        if idx is not None and removals:
            return (
                f"ERROR: konteks cocok tapi baris '-{removals[0]}...' tidak cocok di {path} — "
                "baca file dulu (read_file) lalu patch ulang"
            )
        if idx is not None and not removals:
            idx += len(contexts)  # sisipkan setelah konteks
    elif idx is None and not contexts:
        return f"ERROR: tidak ada konteks yang cocok di {path} — baca file dulu (read_file) lalu patch ulang"

    if idx is None:
        return f"ERROR: konteks tidak cocok di {path} — baca file dulu (read_file) lalu patch ulang"

    new = old[:idx] + new_seq + old[idx + len(old_seq) :]
    target.write_text("\n".join(new) + ("\n" if new else ""))
    return f"OK: {path} di-patch ({len(removals)} hapus, {len(additions)} tambah)"


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "apply_patch",
        "Edit file dengan diff minimal (format: '--- path' lalu baris -/+). WAJIB untuk mengubah file yang sudah ada.",
        {"patch": {"type": "string"}, "base_dir": {"type": "string"}},
        lambda patch, base_dir=".": apply_patch(patch, base_dir),
    )
