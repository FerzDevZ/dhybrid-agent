"""Tool mem_index/mem_search — memory kode proyek via sqlite-vec.

Model sering lupa konteks file yang sudah dibaca (token terbatas). Tool ini
meng-index chunk kode proyek jadi VECTOR char n-gram (tanpa GPU, tanpa model
embedding — cukup hash + hitung) lalu mencari chunk relevan dengan cosine
similarity via sqlite-vec. Cocok untuk: "di file mana fungsi login dibuat?"

Fallback otomatis: bila ekstensi sqlite-vec tidak bisa di-load, pencarian
tetap jalan via cosine Python (lebih lambat, hasil sama).

DB: <cwd>/.dhybrid/mem.sqlite (per proyek). Override: env DHYBRID_MEM_DB.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from pathlib import Path

_DIM = 256
_CHUNK_LINES = 40
_CHUNK_OVERLAP = 5
_READ_CAP = 1_000_000  # 1MB — file raksasa (vendor/bundle) tidak di-index


def _db_path() -> str:
    return os.environ.get("DHYBRID_MEM_DB") or str(Path.cwd() / ".dhybrid" / "mem.sqlite")


def _connect(db: str | None = None):
    conn = sqlite3.connect(db or _db_path())
    vec_ok = False
    try:
        conn.enable_load_extension(True)
        import sqlite_vec

        sqlite_vec.load(conn)
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[{_DIM}])"
        )
        vec_ok = True
    except Exception:  # noqa: BLE001,S110 — extension tak tersedia → fallback Python
        pass
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chunks ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "path TEXT NOT NULL, start_line INTEGER, end_line INTEGER,"
        "text TEXT, vec TEXT)"
    )
    conn.commit()
    return conn, vec_ok


def _vectorize(text: str) -> list[float]:
    """Char 3-gram hashed ke vektor 256-dim, L2-normalized. Deterministik."""
    t = re.sub(r"[^a-z0-9]+", " ", text.lower())
    t = re.sub(r"\s+", " ", t).strip()
    vec = [0.0] * _DIM
    for i in range(len(t) - 2):
        g = t[i : i + 3]
        h = int(hashlib.md5(g.encode("utf-8"), usedforsecurity=False).hexdigest(), 16) % _DIM
        vec[h] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _chunk_lines(lines: list[str]) -> list[tuple[int, int, str]]:
    """Potong file jadi chunk baris (dengan overlap kecil supaya fungsi yang
    lebih panjang dari satu chunk tetap ketemu)."""
    n = len(lines)
    chunks = []
    start = 0
    while start < n:
        end = min(start + _CHUNK_LINES, n)
        chunks.append((start + 1, end, "\n".join(lines[start:end])))
        if end >= n:
            break
        start = end - _CHUNK_OVERLAP
    return chunks


def mem_index(path: str) -> str:
    """Index satu file kode jadi chunk vektor (untuk pencarian semantic)."""
    p = Path(path)
    if not p.is_file():
        return f"ERROR: file tidak ditemukan: {path}"
    size = p.stat().st_size
    if size > _READ_CAP:
        return f"ERROR: file terlalu besar ({size // 1024}KB > {_READ_CAP // 1024}KB) — lewati"
    try:
        raw = p.read_bytes()
    except Exception as e:  # noqa: BLE001
        return f"ERROR baca {path}: {type(e).__name__}: {e}"
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        text = raw.decode("latin-1", errors="replace")
    lines = text.splitlines()
    chunks = _chunk_lines(lines)
    if not chunks:
        return f"mem_index: {path} kosong — 0 chunk"
    conn, _vec_ok = _connect()
    try:
        conn.execute("DELETE FROM chunks WHERE path = ?", (str(p),))
        for start, end, chunk_text in chunks:
            vec = _vectorize(chunk_text)
            cur = conn.execute(
                "INSERT INTO chunks (path, start_line, end_line, text, vec) VALUES (?, ?, ?, ?, ?)",
                (str(p), start, end, chunk_text, json.dumps(vec)),
            )
            rowid = cur.lastrowid
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                    (rowid, json.dumps(vec)),
                )
            except sqlite3.Error:  # vec0 gagal → chunks.vec fallback
                pass
        conn.commit()
    except sqlite3.Error as e:
        return f"ERROR mem_index: {e}"
    finally:
        conn.close()
    return f"mem_index: {path} — {len(chunks)} chunk di-index"


def mem_search(query: str, k: int = 5) -> str:
    """Cari chunk kode paling relevan dengan query (cosine, via sqlite-vec)."""
    if not query.strip():
        return "ERROR: query kosong"
    qvec = _vectorize(query)
    conn, vec_ok = _connect()
    try:
        if vec_ok:
            rows = conn.execute(
                "SELECT rowid, distance FROM vec_chunks WHERE embedding MATCH ? AND k = ?",
                (json.dumps(qvec), k),
            ).fetchall()
            ids = [r[0] for r in rows]
            dists = {r[0]: r[1] for r in rows}
            hits = []
            if ids:
                placeholders = ",".join("?" * len(ids))
                for row in conn.execute(
                    f"SELECT id, path, start_line, end_line, text FROM chunks "  # nosec B608
                    f"WHERE id IN ({placeholders})",
                    ids,
                ).fetchall():
                    hits.append((dists.get(row[0], 9e9), row[1], row[2], row[3], row[4]))
        else:
            rows = conn.execute("SELECT id, path, start_line, end_line, text, vec FROM chunks").fetchall()
            scored = []
            for rid, rpath, s, e, txt, vj in rows:
                try:
                    v = json.loads(vj)
                except Exception:  # noqa: BLE001,S112
                    continue
                scored.append((1.0 - _cosine(qvec, v), rpath, s, e, txt))
            hits = sorted(scored)[:k]
    except sqlite3.Error as e:
        return f"ERROR mem_search: {e}"
    finally:
        conn.close()
    if not hits:
        return f"mem_search: '{query}' — tidak ada chunk relevan (index dulu via mem_index)"
    out = [f"mem_search: '{query}' — top {len(hits)} chunk:"]
    for score, rpath, s, e, txt in hits:
        snippet = re.sub(r"\s+", " ", txt)[:300]
        out.append(f"  {rpath}:{s}-{e} (skor {score:.3f})\n    {snippet}")
    return "\n".join(out)


def mem_reset() -> str:
    """Hapus SEMUA chunk yang ter-index (fresh start)."""
    conn, _vec_ok = _connect()
    try:
        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM vec_chunks")
        conn.commit()
    except sqlite3.Error as e:
        return f"ERROR mem_reset: {e}"
    finally:
        conn.close()
    return "mem_reset: index proyek dikosongkan"


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "mem_index",
        "Index satu file kode jadi chunk vektor (sqlite-vec, tanpa GPU) untuk "
        "pencarian semantic — panggil untuk file penting yang sering dirujuk.",
        {"path": {"type": "string", "required": True}},
        mem_index,
    )
    reg.register(
        "mem_search",
        "Cari chunk kode ter-relevan dengan query (cosine similarity) — "
        "'di file mana fungsi login dibuat?' Misal: mem_search('route login')",
        {"query": {"type": "string", "required": True}, "k": {"type": "integer"}},
        lambda query, k=5: mem_search(query, k=k),
    )
    reg.register(
        "mem_reset",
        "Kosongkan index memori kode proyek (semua chunk dihapus).",
        {},
        mem_reset,
    )
