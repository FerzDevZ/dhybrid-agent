"""Test render — style() tidak boleh bocorkan ANSI ke non-tty / NO_COLOR."""

from dhybrid.ui.render import style


def test_style_non_tty_plain(monkeypatch):
    monkeypatch.setattr("dhybrid.ui.render.is_tty", lambda: False)
    assert style("halo", "31") == "halo"  # tanpa escape code


def test_style_tty_colored(monkeypatch):
    monkeypatch.setattr("dhybrid.ui.render.is_tty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    out = style("halo", "31")
    assert out == "\x1b[31mhalo\x1b[0m"


def test_style_no_color_env(monkeypatch):
    monkeypatch.setattr("dhybrid.ui.render.is_tty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "1")
    assert style("halo", "31") == "halo"  # NO_COLOR menang atas tty
