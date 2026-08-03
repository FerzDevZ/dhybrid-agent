"""Task 6: tool pdf_ops — merge PDF via pypdf."""
from dhybrid.tools import power_pdf


def _mk_pdf(tmp_path, name):
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(200, 200)
    p = tmp_path / name
    with open(p, "wb") as fh:
        w.write(fh)
    return str(p)


def test_pdf_merge(tmp_path):
    out = power_pdf._pdf_merge(
        [_mk_pdf(tmp_path, "a.pdf"), _mk_pdf(tmp_path, "b.pdf")],
        str(tmp_path / "ab.pdf"),
    )
    assert "OK" in out and (tmp_path / "ab.pdf").exists()


def test_pdf_merge_blocks_missing_file(tmp_path):
    out = power_pdf._pdf_merge([str(tmp_path / "no.pdf")], str(tmp_path / "x.pdf"))
    assert "ERROR" in out


def test_pdf_merge_blocks_bad_pdf(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    out = power_pdf._pdf_merge([str(bad)], str(tmp_path / "x.pdf"))
    assert "ERROR" in out
