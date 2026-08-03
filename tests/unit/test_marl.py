"""Test MARL: kualitas output, verifier, scoreboard."""

from dhybrid.agent.quality import score_output
from dhybrid.agent.scoreboard import Scoreboard
from dhybrid.agent.verify import (
    count_created_files,
    snapshot_files,
    verify_build,
)
from dhybrid.agent.verify import tests_info as _tests_info


def test_score_output_cases():
    assert score_output("") == 0
    assert score_output("Saya tidak bisa melakukan itu") < 40
    assert score_output("Mau pakai stack apa?", is_build=True, files_created=0) < 30
    assert score_output("Selesai, 3 file dibuat", is_build=True, files_created=3, tests_passed=True) >= 50
    assert score_output("jawaban normal") >= 40


def test_score_output_confused_and_promise():
    """Deteksi model bingung (bertanya berulang) & janji tanpa eksekusi."""
    # Bertanya bingung di build request → skor rendah
    assert score_output("Mau pakai stack apa?", is_build=True, files_created=0) < 20
    assert score_output("Bagaimana sebaiknya ya?", is_build=True, files_created=0) < 20
    # Janji tanpa eksekusi file → skor rendah
    assert score_output("Saya akan buatkan untukmu", is_build=True, files_created=0, tools_used=0) < 30
    # File dibuat → skor tinggi
    assert score_output("Selesai, 3 file dibuat", is_build=True, files_created=3) > 60
    # Tests passed → bonus
    assert score_output("ok", tests_passed=True) > 50


def test_score_output_repeated_question_tracking():
    """Model yang bertanya berulang → skor turun karena confused hints."""
    text = "Maaf, mau pakai stack apa dulu?"
    s = score_output(text, is_build=True, files_created=0, tools_used=0)
    assert s < 30  # sangat rendah: bertanya + confusion hint


def test_verify_snapshot_and_created(tmp_path):
    (tmp_path / "a.py").write_text("x")
    before = snapshot_files(str(tmp_path))
    assert "a.py" in before
    (tmp_path / "b.py").write_text("y")
    after = snapshot_files(str(tmp_path))
    assert count_created_files(before, after) == 1
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("z")
    assert ".git/config" not in snapshot_files(str(tmp_path))


def test_verify_tests_info():
    events = [
        {"name": "run_tests", "output": "2 passed in 0.1s"},
        {"name": "terminal", "output": "ls"},
    ]
    passed, count = _tests_info(events)
    assert passed is True and count == 1
    events2 = [{"name": "run_tests", "output": "1 failed, 2 passed"}]
    assert _tests_info(events2)[0] is False


def test_verify_build_summary(tmp_path):
    before = snapshot_files(str(tmp_path))
    (tmp_path / "x.py").write_text("x")
    after = snapshot_files(str(tmp_path))
    v = verify_build(str(tmp_path), before, after, [{"name": "run_tests", "output": "1 passed"}])
    assert v["files_created"] == 1 and v["tests_passed"] is True


def test_verify_snapshot_prunes_dependency_dirs(tmp_path):
    """Folder dependensi (vendor/, node_modules/) tidak boleh ikut dihitung
    sebagai 'file dibuat' — kalau ikut, angka absurd seperti '17624 file' muncul."""
    app = tmp_path / "app" / "views"
    app.mkdir(parents=True)
    (app / "home.blade.php").write_text("x")

    vendor = tmp_path / "vendor" / "autoload.php"
    vendor.parent.mkdir(parents=True)
    vendor.write_text("<?php")

    nm = tmp_path / "node_modules" / "lib" / "i.js"
    nm.parent.mkdir(parents=True)
    nm.write_text("x")

    snap = snapshot_files(str(tmp_path))
    assert "app/views/home.blade.php" in snap
    assert not any(p.startswith("vendor/") for p in snap)
    assert not any(p.startswith("node_modules/") for p in snap)


def test_count_created_ignores_dependency_dirs(tmp_path):
    """Menciptakan file vendor/node_modules tidak boleh menaikkan files_created."""
    before = snapshot_files(str(tmp_path))
    dep = tmp_path / "vendor" / "autoload.php"
    dep.parent.mkdir(parents=True)
    dep.write_text("<?php")
    nm = tmp_path / "node_modules" / "pkg" / "i.js"
    nm.parent.mkdir(parents=True)
    nm.write_text("x")
    after = snapshot_files(str(tmp_path))
    assert count_created_files(before, after) == 0


def test_scoreboard_roundtrip(tmp_path):
    sb = Scoreboard(tmp_path / "sb.sqlite")
    sb.record("model-a", 80)
    sb.record("model-a", 60)
    sb.record("model-b", 30)
    rows = sb.table()
    assert rows[0][0] == "model-a" and rows[0][1] == 70.0
    assert sb.best_available(["model-b", "model-a"]) == "model-a"
    assert sb.best_available(["model-x"]) is None
    assert sb.best_available([]) is None
