from dhybrid.tools.patch import apply_patch


def test_replace_line(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\nprint(x)\n")
    out = apply_patch("--- a.py\n-x = 1\n+x = 2\n", base_dir=str(tmp_path))
    assert "OK" in out
    assert f.read_text() == "x = 2\nprint(x)\n"


def test_insert_with_context(tmp_path):
    f = tmp_path / "b.py"
    f.write_text("def a():\n    pass\n\ndef b():\n    pass\n")
    out = apply_patch(
        "--- b.py\n def b():\n+    return 42\n",
        base_dir=str(tmp_path),
    )
    assert "OK" in out
    assert "return 42" in f.read_text()


def test_delete_line(tmp_path):
    f = tmp_path / "c.py"
    f.write_text("keep\nremove\nkeep2\n")
    out = apply_patch("--- c.py\n-remove\n", base_dir=str(tmp_path))
    assert "OK" in out
    assert f.read_text() == "keep\nkeep2\n"


def test_patch_missing_target(tmp_path):
    out = apply_patch("--- nope.py\n-x\n+y\n", base_dir=str(tmp_path))
    assert "tidak ada" in out


def test_patch_conflict_error_keeps_file(tmp_path):
    f = tmp_path / "d.py"
    f.write_text("aaa\n")
    out = apply_patch("--- d.py\n-zzz\n+yyy\n", base_dir=str(tmp_path))
    assert "ERROR" in out
    assert f.read_text() == "aaa\n"


def test_patch_requires_header(tmp_path):
    out = apply_patch("-x\n+y\n", base_dir=str(tmp_path))
    assert "ERROR" in out
