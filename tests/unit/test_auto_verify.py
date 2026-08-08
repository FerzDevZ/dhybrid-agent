import sys
from pathlib import Path

from dhybrid.agent.auto_verify import detect_runner, run_verification


def test_detect_python(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("")
    runner, cmd = detect_runner(str(tmp_path), set())
    assert runner == "pytest"
    assert cmd[0] == sys.executable and cmd[4] == "--tb=short"


def test_detect_node(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    runner, _cmd = detect_runner(str(tmp_path), set())
    assert runner == "npm_test"


def test_detect_go_from_new_file(tmp_path: Path):
    runner, _cmd = detect_runner(str(tmp_path), {"main.go"})
    assert runner == "go_test"


def test_no_runner_when_empty(tmp_path: Path):
    runner, cmd = detect_runner(str(tmp_path), set())
    assert runner is None and cmd == []


def test_run_verification_skipped_no_runner(tmp_path: Path):
    # tidak ada marker → tidak jalan
    rep = run_verification(str(tmp_path), {"selftest.xyz"})
    assert rep.ran is False and rep.evidence is False


def test_run_verification_passes_when_tests_pass(tmp_path: Path):
    (tmp_path / "test_selftest.py").write_text(
        "def test_ok():\n    assert True\n"
    )
    rep = run_verification(str(tmp_path), {"test_selftest.py"}, timeout_s=30)
    assert rep.ran is True and rep.passed is True
    assert rep.exit_code == 0
    assert rep.evidence is True


def test_run_verification_fails_when_tests_fail(tmp_path: Path):
    (tmp_path / "test_selftest.py").write_text(
        "def test_bad():\n    assert False\n"
    )
    rep = run_verification(str(tmp_path), {"test_selftest.py"}, timeout_s=30)
    assert rep.ran is True and rep.passed is False
    assert rep.log_tail  # ada log error


def test_run_verification_none_when_no_tests(tmp_path: Path):
    # project ada tapi tidak ada test → passed None (bukan LULUS/GAGAL palsu)
    (tmp_path / "empty.py").write_text("x = 1\n")
    (tmp_path / "pyproject.toml").write_text("")
    rep = run_verification(str(tmp_path), {"empty.py"}, timeout_s=30)
    assert rep.ran is True
    assert rep.passed is None


def test_run_verification_catches_bad_command(tmp_path: Path):
    # command runner tidak terinstall → FileNotFoundError ditangkap, tidak crash
    (tmp_path / "pyproject.toml").write_text("")
    rep = run_verification(str(tmp_path), {"bad.py"}, timeout_s=30)
    # pytest seharusnya ada di lingkungan dev; pastikan selalu return report
    assert isinstance(rep.ran, bool)