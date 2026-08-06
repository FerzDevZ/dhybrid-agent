"""Test sistem penilaian kualitas output — eksekusi nyata harus dominan."""

from __future__ import annotations

from dhybrid.agent.quality import score_output


def test_build_task_sukses_dengan_bahasa_natural_tidak_dihukum():
    """Bahasa Indonesia natural ("apakah kamu", "saya akan buat") TIDAK boleh
    menurunkan skor jika agent benar-benar bekerja (tools + file)."""
    text = (
        "Saya akan membuatkan login register untuk Anda. "
        "Apakah kamu mau saya tambahkan validasi?"
    )
    s = score_output(text, is_build=True, tools_used=5, files_created=2)
    assert s >= 60  # task sukses dengan file → minimal "cukup"


def test_build_task_file_nyata_minimal_60():
    s = score_output("File sudah dibuat ya. Bisa langsung dijalankan.", is_build=True, tools_used=3, files_created=1)
    assert s >= 60


def test_refusal_tanpa_kerja_skor_rendah():
    s = score_output("Saya tidak bisa mengakses file itu.", is_build=True, tools_used=0, files_created=0)
    assert s < 30


def test_diam_total_skor_nol():
    assert score_output("", is_build=True, tools_used=0, files_created=0) == 0


def test_confused_tanpa_kerja_skor_rendah():
    s = score_output("Bingung, mau yang mana?", is_build=True, tools_used=0, files_created=0)
    assert s < 30


def test_confused_tapi_kerja_tidak_dihukum():
    # sama seperti di atas tapi EKSEKUSI ada → tidak jatuh drastis
    s = score_output(
        "Mau yang mana? Tapi saya sudah buat keduanya biar aman.",
        is_build=True,
        tools_used=4,
        files_created=2,
    )
    assert s >= 60


def test_tools_used_meningkatkan_skor():
    base = score_output("Kerja.", is_build=True, tools_used=0, files_created=0)
    worked = score_output("Kerja.", is_build=True, tools_used=8, files_created=0)
    assert worked > base


def test_tests_passed_bonus():
    s = score_output("Beres.", is_build=True, tools_used=6, files_created=2, tests_passed=True)
    assert s >= 70


def test_skor_selalu_di_range():
    for text in ("a", "b" * 500, "Saya tidak bisa" * 20, ""):
        s = score_output(text, is_build=True, tools_used=10, files_created=3)
        assert 0 <= s <= 100
