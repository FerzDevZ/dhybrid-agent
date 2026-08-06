"""Test perbaikan tools/files.py — fuzzy path resolution."""

from __future__ import annotations

from dhybrid.tools.files import _fuzzy_resolve, read_file


def test_fuzzy_resolve_path_lengkap(tmp_path):
    p = tmp_path / "app.py"
    p.write_text("print(1)\n")
    assert _fuzzy_resolve(str(p)) == p


def test_fuzzy_resolve_tanpa_ekstensi(tmp_path):
    (tmp_path / "app.py").write_text("print(1)\n")
    got = _fuzzy_resolve(str(tmp_path / "app"))
    assert got is not None
    assert got.name == "app.py"


def test_fuzzy_resolve_requirements_tanpa_ext(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask\n")
    got = _fuzzy_resolve(str(tmp_path / "requirements"))
    assert got is not None
    assert got.name == "requirements.txt"


def test_fuzzy_resolve_ambigu_dua_kandidat(tmp_path):
    # dua file startswith sama → TIDAK boleh memilih sembarangan
    (tmp_path / "data.py").write_text("a")
    (tmp_path / "data.json").write_text("{}")
    assert _fuzzy_resolve(str(tmp_path / "data")) is None


def test_fuzzy_resolve_file_tidak_ada(tmp_path):
    assert _fuzzy_resolve(str(tmp_path / "xyz")) is None


def test_read_file_tanpa_ekstensi_membaca_file_benar(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')\n")
    out = read_file(str(tmp_path / "app"))
    assert "print('hello')" in out
    # head harus menunjukkan path asli yang dibaca (dengan ekstensi)
    assert "app.py" in out


def test_read_file_path_lengkap_tetap_normal(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')\n")
    out = read_file(str(tmp_path / "app.py"))
    assert "print('hi')" in out
