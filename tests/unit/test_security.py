"""Test keamanan: path traversal, lokasi sensitif, perintah berbahaya."""

from pathlib import Path

from dhybrid.tools.files import read_file, write_file
from dhybrid.tools.patch import apply_patch
from dhybrid.tools.security import check_path_safe, is_dangerous
from dhybrid.tools.terminal import run_command


def test_write_traversal_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # cwd = tmp_path
    out = write_file("../evil.txt", "x")
    assert "diblokir" in out
    assert not (tmp_path.parent / "evil.txt").exists()


def test_write_system_root_blocked():
    out = write_file("/etc/evil-test-xyz", "x")
    assert "diblokir" in out


def test_write_sensitive_dir_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = write_file(str(Path.home() / ".ssh" / "authorized_keys"), "x")
    assert "diblokir" in out


def test_write_dotenv_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = write_file(".env", "OPENAI_API_KEY=x")
    assert "diblokir" in out


def test_read_system_root_blocked():
    assert "diblokir" in read_file("/etc/passwd")


def test_patch_traversal_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = apply_patch("--- ../evil.py\n-x\n+y\n", base_dir=".")
    assert "diblokir" in out
    assert not (tmp_path.parent / "evil.py").exists()


def test_patch_normal_still_works(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\n")
    out = apply_patch("--- a.py\n-x = 1\n+x = 2\n", base_dir=str(tmp_path))
    assert "OK" in out and f.read_text() == "x = 2\n"


def test_write_normal_still_works(tmp_path):
    f = tmp_path / "ok.txt"
    assert "OK" in write_file(str(f), "halo")
    assert f.read_text() == "halo"


def test_dangerous_variants():
    # bypass klasik: flag dipisah
    assert is_dangerous("rm -rf /tmp/x")
    assert is_dangerous("rm -r -f /tmp/x")
    assert is_dangerous("rm -f -r /tmp/x")
    assert is_dangerous("rm -fr /tmp/x")
    assert is_dangerous("rm --recursive --force /tmp/x")
    assert is_dangerous("  rm   -rf   /tmp/x")  # spasi berlebihan
    assert is_dangerous("git push --force origin main")
    assert not is_dangerous("git status")
    assert not is_dangerous("rm file.txt")  # tanpa flag berbahaya
    assert not is_dangerous("ls -la")


def test_dangerous_confirmation_flow(tmp_path, monkeypatch):
    """Perintah berbahaya tanpa konfirmasi aktif → ditolak otomatis."""
    from dhybrid.tools import terminal

    monkeypatch.setattr(terminal, "confirm_fn", None)
    out = run_command("rm -rf /tmp/x")
    assert "ditolak" in out


def test_check_path_safe_basic():
    ok, _ = check_path_safe("file.py")
    assert ok
    ok, reason = check_path_safe("/etc/hosts")
    assert not ok and "sistem" in reason
    ok, reason = check_path_safe(str(Path.home() / ".bashrc"))
    assert not ok and "sensitif" in reason
