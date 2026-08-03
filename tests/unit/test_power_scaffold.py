"""Task 4: tool scaffold — generate file dari template jinja2 (aman traversal)."""
from dhybrid.tools import power_scaffold


def test_scaffold_renders_template(tmp_path):
    src = tmp_path / "tmpl"
    src.mkdir()
    (src / "hello.txt.j2").write_text("Halo {{ nama }}!")
    out = power_scaffold._scaffold(str(src), str(tmp_path / "out"), {"nama": "Dunia"})
    assert "1 file" in out
    assert (tmp_path / "out" / "hello.txt").read_text() == "Halo Dunia!"


def test_scaffold_renders_nested(tmp_path):
    src = tmp_path / "tmpl"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "a.txt.j2").write_text("x={{ x }}")
    power_scaffold._scaffold(str(src), str(tmp_path / "out"), {"x": 1})
    assert (tmp_path / "out" / "sub" / "a.txt").exists()


def test_scaffold_blocks_path_traversal(tmp_path):
    # symlink template menunjuk keluar dari template dir → harus diblokir
    src = tmp_path / "tmpl"
    src.mkdir()
    evil = tmp_path / "evil.txt"
    evil.write_text("x")
    (src / "link.j2").symlink_to(evil)
    out = power_scaffold._scaffold(str(src), str(tmp_path / "out"), {})
    assert "ERROR" in out


def test_scaffold_blocks_missing_dir(tmp_path):
    out = power_scaffold._scaffold(str(tmp_path / "none"), str(tmp_path / "out"), {})
    assert "ERROR" in out
