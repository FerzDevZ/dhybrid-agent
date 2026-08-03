import subprocess
import sys


def run_cli(*args, timeout=60, env=None):
    return subprocess.run(
        [sys.executable, "-m", "dhybrid", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def test_version():
    from dhybrid import __version__

    p = run_cli("--version")
    assert p.returncode == 0
    assert __version__ in p.stdout


def test_pyproject_version_matches_runtime():
    """Regresi: metadata packaging (pyproject.toml) harus sinkron dengan
    __version__ runtime — sebelumnya pyproject 0.1.0 tapi binary lapor 0.4.1."""
    import re
    from pathlib import Path

    from dhybrid import __version__

    root = Path(__file__).resolve().parents[2]  # repo root
    pyproject = (root / "pyproject.toml").read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert m, "versi tidak ditemukan di pyproject.toml"
    assert m.group(1) == __version__, f"pyproject {m.group(1)!r} != runtime {__version__!r}"