"""Test tool read_document (markitdown) — baca PDF/DOCX/HTML & file teks."""

from dhybrid.tools.documents import _read_document
from dhybrid.tools.registry import ToolRegistry


def test_read_document_markdown_passthrough(tmp_path):
    f = tmp_path / "catatan.md"
    f.write_text("## Judul\n\nisi catatan penting")
    out = _read_document(str(f))
    assert "catatan.md" in out
    assert "isi catatan penting" in out


def test_read_document_html_via_markitdown(tmp_path):
    f = tmp_path / "laporan.html"
    f.write_text("<html><body><h1>Laporan Tahunan</h1><p>Keuntungan naik <b>20%</b>.</p></body></html>")
    out = _read_document(str(f))
    assert "Laporan Tahunan" in out
    assert "20%" in out


def test_read_document_missing_file():
    out = _read_document("/tmp/tidak-ada-file-xyz.pdf")
    assert out.startswith("ERROR")


def test_read_document_directory(tmp_path):
    out = _read_document(str(tmp_path))
    assert out.startswith("ERROR")


def test_read_document_truncated(tmp_path):
    f = tmp_path / "panjang.txt"
    f.write_text("x" * 5000)
    out = _read_document(str(f), max_chars=100)
    assert "truncated" in out
    assert len(out) <= 120


def test_read_document_registered():
    from dhybrid.tools.documents import register

    reg = ToolRegistry(allowlist=None)
    register(reg)
    names = [s["name"] for s in reg.specs()]
    assert "read_document" in names
