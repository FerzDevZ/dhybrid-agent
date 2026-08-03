"""Task 8: deteksi MIME gambar — magic bytes PNG/JPEG + python-magic opsional."""
from dhybrid.tools import vision


def test_is_image_png_bytes():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    assert vision._is_image_bytes(png) is True


def test_is_image_jpeg_bytes():
    jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 8
    assert vision._is_image_bytes(jpg) is True


def test_is_image_rejects_text_bytes():
    assert vision._is_image_bytes(b"not an image at all") is False


def test_read_image_rejects_non_image_file(tmp_path):
    f = tmp_path / "fake.png"
    f.write_text("ini teks, bukan gambar")
    out = vision.read_image(str(f))
    assert "ERROR" in out and "bukan gambar" in out


def test_read_image_rejects_unknown_ext(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"\x00\x01\x02\x03")
    out = vision.read_image(str(f))
    assert "ERROR" in out
