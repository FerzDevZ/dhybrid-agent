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


def test_bare_dhybrid_launches_repl_with_menu():
    """`dhybrid` tanpa subcommand → langsung menu lengkap + REPL siap pakai."""
    p = subprocess.run(
        [sys.executable, "-m", "dhybrid", "--cwd", "/tmp"],
        input="/quit\n",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert p.returncode == 0
    assert "dhybrid-agent" in p.stdout          # banner
    assert "MENU" in p.stdout                   # menu utama
    assert "/settings" in p.stdout              # satu pintu semua pengaturan
    assert "dhybrid>" in p.stdout               # prompt siap pakai


def test_bare_dhybrid_with_model_flag():
    """`dhybrid --model X` (tanpa subcommand) → REPL dengan model terganti."""
    p = subprocess.run(
        [sys.executable, "-m", "dhybrid", "--model", "openrouter-big", "--cwd", "/tmp"],
        input="/quit\n",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert p.returncode == 0
    assert "claude-sonnet" in p.stdout


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
    """Tanpa key + model yang butuh auth (openai-fast) → error API yang jelas, bukan traceback.
    (Catatan: model default kecil sekarang route zen gratis — bisa jalan tanpa key.)"""
    import os

    env = dict(os.environ)
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(k, None)
    p = subprocess.run(
        [sys.executable, "-m", "dhybrid", "run", "desain ulang arsitektur modul ini dan jelaskan alasannya",
         "--model", "openai-fast", "--cwd", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        env=env,
    )
    # prompt "desain..." dirutekan ke model BESAR (openai-fast, tanpa key):
    # tanpa network → ConnectError; dengan network → 401. Dua-duanya error API yang ramah.
    assert "[error API]" in p.stdout or "[error API]" in p.stderr
    assert "Traceback" not in p.stdout + p.stderr
