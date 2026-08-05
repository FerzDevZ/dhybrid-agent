"""Smoke coverage tools/files.py (19% → jalur utama tertutup).

File ini safety-critical: dipanggil agent tiap hari untuk baca/tulis.
Sebelumnya coverage ~19% (hanya tertutup lewat test tidak langsung).
"""
import tempfile
from pathlib import Path

from dhybrid.tools import files


def test_read_file_baris_dengan_offset_limit(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("satu\ndua\ntiga\nempat\n")

    out = files.read_file(str(p), offset=2, limit=2)
    assert "2|dua" in out
    assert "3|tiga" in out
    assert "1|satu" not in out
    assert "(4 baris" in out


def test_read_file_truncate_max_chars():
    p = tempfile.mktemp(suffix=".txt")
    Path(p).write_text("x" * 100)
    try:
        out = files.read_file(p, limit=100, max_chars=50)
        assert out.endswith("[truncated]")
    finally:
        Path(p).unlink(missing_ok=True)


def test_read_file_error_path_tidak_ada():
    out = files.read_file("/tmp/tidak_ada_xyz_123.txt")
    assert out.startswith("ERROR:")


def test_read_file_menolak_traversal():
    out = files.read_file("../../etc/passwd")
    assert out.startswith("ERROR:")


def test_write_file_membuat_parent_dir(tmp_path):
    target = tmp_path / "sub" / "dir" / "f.txt"
    out = files.write_file(str(target), "konten baru")
    assert out.startswith("OK:")
    assert target.read_text() == "konten baru"


def test_write_file_menolak_traversal():
    out = files.write_file("../../evil.txt", "x")
    assert out.startswith("ERROR:")
    assert not Path("../../evil.txt").resolve().exists()


def test_register_mendaftarkan_read_dan_write():
    class Reg:
        def __init__(self):
            self.items = []

        def register(self, name, desc, schema, fn):
            self.items.append(name)

    reg = Reg()
    files.register(reg, max_chars=100)
    assert reg.items == ["read_file", "write_file"]
