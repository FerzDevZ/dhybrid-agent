"""Test tool read_image — vision LLM (mock) & fallback OCR lokal."""

from types import SimpleNamespace as NS

import pytest

from dhybrid.llm.base import ChatMessage, ChatResponse, Usage
from dhybrid.tools import vision


@pytest.fixture
def img(tmp_path):
    """Gambar PNG kecil dengan teks (via PIL, sudah terinstall)."""
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", (400, 120), "white")
    d = ImageDraw.Draw(im)
    d.text((20, 40), "HELLO DHYBRID 2026", fill="black", font=ImageFont.load_default())
    p = tmp_path / "ss.png"
    im.save(p)
    return str(p)


class _FakeVision:
    def __init__(self, text: str):
        self.cfg = NS(model="agnes-2.5-flash")
        self.text = text

    def complete(self, messages, **kw):
        # pastikan pesan multimodal benar-benar terkirim (ada part gambar)
        assert isinstance(messages[0].content, list)
        assert any(p.get("type") == "image_url" for p in messages[0].content)
        return ChatResponse(
            message=ChatMessage(role="assistant", content=self.text),
            usage=Usage(1, 1),
            model="agnes-2.5-flash",
        )


def test_read_image_vision_path(img, monkeypatch):
    monkeypatch.setattr(vision, "_vision_client", lambda: _FakeVision("ada tombol Login"))
    out = vision.read_image(img)
    assert out.startswith("[vision agnes-2.5-flash]")
    assert "tombol Login" in out


def test_read_image_prompt_custom(img, monkeypatch):
    seen = {}

    def fake_client():
        class C:
            cfg = NS(model="m")
            def complete(self, messages, **kw):
                seen["prompt"] = messages[0].content[0]["text"]
                return ChatResponse(
                    message=ChatMessage(role="assistant", content="x"),
                    usage=Usage(1, 1), model="m",
                )
        return C()

    monkeypatch.setattr(vision, "_vision_client", fake_client)
    vision.read_image(img, prompt="Cuma transkripsi teksnya")
    assert seen["prompt"] == "Cuma transkripsi teksnya"


def test_read_image_fallback_ocr(img, monkeypatch):
    monkeypatch.setattr(vision, "_vision_client", lambda: None)  # tanpa key
    monkeypatch.setattr(vision, "_ocr_local", lambda p: "HELLO DHYBRID 2026")
    out = vision.read_image(img)
    assert out.startswith("[OCR lokal — tanpa API key]")
    assert "HELLO DHYBRID" in out


def test_read_image_vision_fail_then_ocr(img, monkeypatch):
    class _Boom:
        def complete(self, messages, **kw):
            raise RuntimeError("rate limit")
    monkeypatch.setattr(vision, "_vision_client", lambda: _Boom())
    monkeypatch.setattr(vision, "_ocr_local", lambda p: "teks dari OCR")
    out = vision.read_image(img)
    assert out.startswith("[OCR lokal — tanpa API key]")
    assert "vision gagal" in out


def test_read_image_no_key_no_ocr(img, monkeypatch):
    monkeypatch.setattr(vision, "_vision_client", lambda: None)
    monkeypatch.setattr(vision, "_ocr_local", lambda p: "")
    out = vision.read_image(img)
    assert out.startswith("ERROR")
    assert ".[vision]" in out


def test_read_image_missing_file():
    out = vision.read_image("/tmp/tidak-ada-xyz.png")
    assert out.startswith("ERROR")
    assert "tidak ditemukan" in out


def test_read_image_requires_path():
    out = vision.read_image("")
    assert "butuh path" in out
