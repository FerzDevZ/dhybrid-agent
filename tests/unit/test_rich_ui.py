"""Test rich UI — panel DONE & tabel /tokens; fallback polos di non-TTY/NO_COLOR."""


from dhybrid.ui.rich_ui import print_tokens, render_done


def test_render_done_contains_content():
    out = render_done("DONE — 1,000 token · $0.0000 · kualitas 50/100")
    assert "DONE" in out
    assert "1,000 token" in out


def test_render_done_plain_when_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    # import ulang supaya _NO_COLOR terbaca (modul membaca env saat import)
    import importlib

    from dhybrid.ui import rich_ui

    importlib.reload(rich_ui)
    try:
        out = rich_ui.render_done("DONE — polos")
        assert "\x1b[" not in out  # tanpa escape ANSI
        assert "DONE" in out
    finally:
        importlib.reload(rich_ui)  # balikin state modul


def test_print_tokens_fallback_without_rich(monkeypatch, capsys):
    """rich gagal (mis. env minimal) → format teks polos tetap keluar."""
    import builtins

    real_import = builtins.__import__

    def _block_rich(name, *a, **kw):
        if name == "rich" or name.startswith("rich."):
            raise ImportError("rich sengaja diblokir")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _block_rich)
    print_tokens(
        "semua sesi",
        {"prompt": 100, "completion": 50, "cached": 20, "cost": 0.01},
        [("s1", {"prompt": 100, "completion": 50, "cached": 20, "cost": 0.01})],
    )
    out = capsys.readouterr().out
    assert "penggunaan token (semua sesi)" in out
    assert "prompt" in out and "100" in out
    assert "s1" in out
