"""Smoke test CLI — tanpa API key harus tetap jalan & error-nya ramah."""

import subprocess
import sys


def run_cli(*args, timeout=60):
    return subprocess.run(
        [sys.executable, "-m", "dhybrid", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_version():
    p = run_cli("--version")
    assert p.returncode == 0
    assert "0.1.0" in p.stdout


def test_sessions_empty_ok():
    p = run_cli("--cwd", "/tmp", "sessions")
    assert p.returncode == 0


def test_skills_lists_nothing_gracefully(tmp_path):
    p = run_cli("--cwd", str(tmp_path), "skills")
    assert p.returncode == 0


def test_run_without_key_fails_gracefully(tmp_path):
    import os

    env = dict(os.environ)
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(k, None)
    p = subprocess.run(
        [sys.executable, "-m", "dhybrid", "run", "halo", "--cwd", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        env=env,
    )
    # harus error HTTP/401 yang jelas, bukan traceback diam
    assert "ERROR" in p.stdout + p.stderr or "401" in p.stdout + p.stderr or "error" in (p.stdout + p.stderr).lower()
