"""Loader .env minimal (stdlib) — tanpa dependensi python-dotenv.

Mendukung: simpan key (untuk /key & /setup) dan muat dari beberapa lokasi
(cwd → direktori install → ~/.dhybrid).
"""

from __future__ import annotations

import os
from pathlib import Path


def install_dir() -> Path:
    """Direktori tempat dhybrid-agent terpasang (tempat .env hasil installer)."""
    return Path(__file__).resolve().parents[2]


def load_dotenv(path: str | Path = ".env") -> None:
    """Muat KEY=VALUE ke os.environ bila belum ada."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def load_standard_dotenvs() -> None:
    """Muat .env dari: cwd → direktori install → ~/.dhybrid (cwd menang)."""
    for p in (Path.cwd() / ".env", install_dir() / ".env", Path.home() / ".dhybrid" / ".env"):
        load_dotenv(p)


def default_env_path() -> Path:
    """Tempat menyimpan key: .env di cwd bila ada, selain itu di direktori install."""
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return cwd_env
    return install_dir() / ".env"


def set_env_key(key: str, value: str, path: str | Path | None = None) -> Path:
    """Simpan/ubah satu key di .env (menambah atau mengganti baris KEY=...)."""
    p = Path(path) if path else default_env_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = p.read_text().splitlines() if p.exists() else []
    out: list[str] = []
    found = False
    for ln in lines:
        if ln.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={value}")
    p.write_text("\n".join(out) + "\n")
    os.environ[key] = value  # berlaku langsung di sesi ini
    return p
