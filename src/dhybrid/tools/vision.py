"""Tool read_image — baca gambar (screenshot/paste) jadi teks.

Dua jalur, tidak bergantung penuh pada API key:

1. VISION LLM (utama): default byNara (OpenAI-compatible, router.bynara.id/v1,
   key BYNARA_API_KEY) — paham layout, kode, error, UI, konteks.
   Override env:
     DHYBRID_VISION_PROVIDER   (default: openai)
     DHYBRID_VISION_MODEL      (default: model utama config; kosong → pakai
                                model utama yang sedang aktif)
     DHYBRID_VISION_BASE_URL   (default: https://router.bynara.id/v1)
     DHYBRID_VISION_API_KEY_ENV (default: BYNARA_API_KEY)
2. OCR LOKAL (tanpa API key sama sekali): rapidocr-onnxruntime →
   pytesseract → pesan ramah. Pasang dengan: pip install -e '.[vision]'
"""

from __future__ import annotations

import os
from pathlib import Path

from dhybrid.llm.base import ChatMessage, image_part, text_part

_DEFAULT_PROMPT = (
    "Jelaskan isi gambar ini secara detail: semua teks yang terlihat "
    "(transkripsikan persis, termasuk kode/error), struktur/tata letak, dan "
    "konteksnya. Kalau ada pesan error atau log, kutip baris pentingnya."
)


def _main_model_name() -> str:
    try:
        from dhybrid.config import Config

        return Config.load().model.model or ""
    except Exception:  # noqa: BLE001 — config gagal dimuat → model kosong
        return ""


def _vision_client():
    """Client vision dari env; None bila key tidak terisi."""
    key_env = os.environ.get("DHYBRID_VISION_API_KEY_ENV", "BYNARA_API_KEY")
    if not os.environ.get(key_env):
        return None
    model = os.environ.get("DHYBRID_VISION_MODEL", "") or _main_model_name()
    if not model:
        return None
    from dhybrid.config import ModelConfig
    from dhybrid.llm.providers import make_client

    cfg = ModelConfig(
        provider=os.environ.get("DHYBRID_VISION_PROVIDER", "openai"),
        model=model,
        base_url=os.environ.get("DHYBRID_VISION_BASE_URL", "https://router.bynara.id/v1"),
        api_key_env=key_env,
        max_tokens=1500,
        temperature=0.1,
    )
    try:
        return make_client(cfg)
    except Exception:  # noqa: BLE001 — provider tak dikenal → None
        return None


def _is_image_bytes(data: bytes) -> bool:
    """True bila bytes benar-benar gambar (PNG/JPEG) — magic bytes dulu,
    lalu python-magic (extra power) bila tersedia."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:2] == b"\xff\xd8":
        return True
    try:
        import magic  # python-magic (extra power, opsional)

        return (magic.from_buffer(data, mime=True) or "").startswith("image/")
    except (ImportError, Exception):  # noqa: BLE001 — magic tak ada/error → False
        return False


def _ocr_local(path: str) -> str:
    """OCR offline tanpa API key. rapidocr-onnxruntime (ONNX, tanpa torch) →
    pytesseract → "" (tidak tersedia)."""
    try:
        from rapidocr_onnxruntime import RapidOCR

        result, _ = RapidOCR()(path)
        if result:
            return "\n".join(str(line[1]) for line in result)
        return "(OCR: tidak ada teks terdeteksi)"
    except ImportError:
        pass
    try:
        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(path)).strip()
    except ImportError:
        return ""


def read_image(path: str = "", prompt: str = "") -> str:
    """Baca gambar (PNG/JPG) jadi teks: jalur vision LLM, fallback OCR lokal.

    path   — file gambar (mis. hasil /shot atau capture)
    prompt — instruksi opsional (default: transkripsi + deskripsi detail)
    """
    if not path:
        return "ERROR: read_image butuh path gambar (mis. hasil /shot di REPL)"
    p = Path(path).expanduser()
    if not p.exists():
        return f"ERROR: file tidak ditemukan: {path}"
    if not p.is_file():
        return f"ERROR: bukan file: {path}"
    if p.stat().st_size > 15 * 1024 * 1024:
        return f"ERROR: gambar terlalu besar ({p.stat().st_size // 1024 // 1024}MB, maks 15MB)"
    if not _is_image_bytes(p.read_bytes()[:4096]):
        return f"ERROR: {path} bukan gambar (magic bytes tidak cocok PNG/JPEG)"

    prompt = (prompt or _DEFAULT_PROMPT).strip()
    note = ""

    # jalur 1: model vision (byNara default)
    client = _vision_client()
    if client is not None:
        try:
            msgs = [
                ChatMessage(role="user", content=[text_part(prompt), image_part(p)])
            ]
            resp = client.complete(msgs)
            content = resp.message.content
            text = content.strip() if isinstance(content, str) else ""
            if text:
                cfg = getattr(client, "cfg", None)
                label = getattr(cfg, "model", "vision") if cfg is not None else "vision"
                return f"[vision {label}]\n{text}"
        except Exception as e:  # noqa: BLE001 — vision gagal → turun ke OCR
            note = f" (vision gagal: {type(e).__name__}: {e})"

    # jalur 2: OCR lokal — tetap jalan tanpa API key
    ocr = _ocr_local(str(p))
    if ocr:
        return f"[OCR lokal — tanpa API key]{note}\n{ocr}"

    return (
        "ERROR: tidak ada model vision (set BYNARA_API_KEY atau DHYBRID_VISION_*) "
        "dan OCR lokal belum terinstall. Pasang: pip install -e '.[vision]'"
    )


def register(reg) -> None:
    reg.register(
        "read_image",
        "Baca gambar/screenshot jadi teks: vision LLM (byNara default), fallback OCR lokal tanpa API key.",
        {
            "path": {"type": "string", "required": True},
            "prompt": {"type": "string"},
        },
        read_image,
    )
