from dhybrid.updater import update_available


def test_update_available_false_when_same(monkeypatch):
    monkeypatch.setattr("dhybrid.updater._git_out", lambda args: "abc\n")
    assert update_available() is False


def test_update_available_true_when_diff(monkeypatch):
    def fake(args):
        if "HEAD" in args:
            return "abc\n"
        return "def\n"

    monkeypatch.setattr("dhybrid.updater._git_out", fake)
    assert update_available() is True


def test_update_available_safe_on_error(monkeypatch):
    def boom(args):
        raise RuntimeError("no git")

    monkeypatch.setattr("dhybrid.updater._git_out", boom)
    assert update_available() is False
