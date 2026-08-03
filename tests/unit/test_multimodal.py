"""Test multimodal ChatMessage — image_part/data URI, to_api passthrough,
konversi blok Anthropic, dan command REPL /shot & /paste."""

from types import SimpleNamespace as NS

from dhybrid.llm.base import ChatMessage, image_part, text_part
from dhybrid.llm.providers import _to_anthropic_content


def test_image_part_data_uri(tmp_path):
    import base64

    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\nfake-bytes")
    part = image_part(p)
    assert part["type"] == "image_url"
    url = part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    raw = base64.b64decode(url.split(",", 1)[1])
    assert b"\x89PNG" in raw and b"fake-bytes" in raw  # round-trip utuh


def test_to_api_passthrough_list():
    m = ChatMessage(role="user", content=[text_part("a"), {"type": "image_url", "image_url": {"url": "data:image/png;base64,QQ=="}}])
    api = m.to_api()
    assert api["role"] == "user"
    assert isinstance(api["content"], list)
    assert api["content"][0] == {"type": "text", "text": "a"}


def test_to_api_string_unchanged():
    m = ChatMessage(role="user", content="teks biasa")
    assert m.to_api()["content"] == "teks biasa"


def test_anthropic_conversion():
    content = [
        text_part("lihat ini"),
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}},
    ]
    blocks = _to_anthropic_content(content)
    assert blocks[0] == {"type": "text", "text": "lihat ini"}
    assert blocks[1] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"},
    }


def test_anthropic_conversion_string_passthrough():
    assert _to_anthropic_content("polos") == "polos"


def test_cmd_paste_saves_and_pushes(tmp_path, monkeypatch):
    import builtins

    from dhybrid.ui import commands

    monkeypatch.setattr(commands.Path, "home", staticmethod(lambda: tmp_path))
    pushed: list = []

    class _Ctx:
        def push(self, m):
            pushed.append(m)

    lines = iter(["baris satu", "baris dua", "."])
    monkeypatch.setattr(builtins, "input", lambda *a: next(lines))
    commands.cmd_paste(_Ctx(), "hasil")
    saved = tmp_path / ".dhybrid" / "pastes" / "hasil.txt"
    assert saved.exists()
    assert "baris satu\nbaris dua" in saved.read_text()
    assert len(pushed) == 1
    assert "[PASTE USER" in pushed[0].content


def test_cmd_paste_empty_not_saved(tmp_path, monkeypatch):
    import builtins

    from dhybrid.ui import commands

    monkeypatch.setattr(commands.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(builtins, "input", lambda *a: (_ for _ in ()).throw(EOFError()))
    commands.cmd_paste(NS(), "kosong")
    assert not (tmp_path / ".dhybrid" / "pastes" / "kosong.txt").exists()


def test_cmd_pasteshot_saves_clipboard(tmp_path, monkeypatch):
    from dhybrid.ui import commands

    monkeypatch.setattr(commands.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(commands, "_clipboard_image_bytes", lambda: b"\x89PNG\r\nclipdata")
    commands.cmd_pasteshot(NS(), "ss")
    out = tmp_path / ".dhybrid" / "captures" / "ss.png"
    assert out.exists()
    assert out.read_bytes() == b"\x89PNG\r\nclipdata"


def test_cmd_pasteshot_empty_clipboard(tmp_path, monkeypatch):
    from dhybrid.ui import commands

    monkeypatch.setattr(commands.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(commands, "_clipboard_image_bytes", lambda: None)
    commands.cmd_pasteshot(NS(), "ss")
    assert not (tmp_path / ".dhybrid" / "captures" / "ss.png").exists()
