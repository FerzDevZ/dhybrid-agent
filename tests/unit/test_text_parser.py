"""Test text_parser — parser kalimat natural → tool calls (model free).

Modul ini paling berisiko karena hasil parse dieksekusi langsung oleh loop
(auto-fire tool). Sebelumnya TIDAK ada test sama sekali — modul ini pernah
mengirim apply_patch dengan old_string placeholder yang dijamin gagal.
"""

from dhybrid.agent.text_parser import extract_tool_calls_from_text


def test_apply_patch_requires_real_old_string():
    # "ubah config.py menjadi X" tanpa old_string → jangan fire apply_patch
    calls = extract_tool_calls_from_text("ubah config.py menjadi versi baru", min_confidence=0.4)
    assert all(c["name"] != "apply_patch" for c in calls)


def test_apply_patch_with_old_and_new():
    calls = extract_tool_calls_from_text(
        "ganti 'debug=true' menjadi 'debug=false' di config.py"
    )
    patch = [c for c in calls if c["name"] == "apply_patch"]
    assert patch, "pola dua-sisi harus terdeteksi"
    assert patch[0]["arguments"] == {
        "path": "config.py",
        "old_string": "debug=true",
        "new_string": "debug=false",
    }
    assert "PLACEHOLDER" not in str(patch[0]["arguments"])


def test_future_tense_not_fired():
    # niat masa depan ≠ perintah eksekusi → write_file TIDAK boleh auto-fire
    calls = extract_tool_calls_from_text("Saya akan buat file app.py dengan isi print('hi')")
    assert all(c["name"] != "write_file" for c in calls)


def test_hedge_not_fired():
    calls = extract_tool_calls_from_text(
        "Sepertinya perlu buat file config.json untuk menyimpan pengaturan"
    )
    assert all(c["name"] != "write_file" for c in calls)


def test_explicit_command_fired():
    # perintah imperatif di awal kalimat → eksekusi jelas, tetap fire
    calls = extract_tool_calls_from_text("Buatkan file app.py dengan isi print('hi')")
    assert any(c["name"] == "write_file" for c in calls)


def test_polite_command_fired():
    calls = extract_tool_calls_from_text("tolong buat file test.py berisi print(1)")
    assert any(c["name"] == "write_file" for c in calls)


def test_read_file_still_fires():
    # baca file = read-only, aman → tetap jalan meski confidence sedang
    calls = extract_tool_calls_from_text("Baca file config.yaml")
    assert any(c["name"] == "read_file" for c in calls)


def test_legacy_tool_block_still_parsed():
    calls = extract_tool_calls_from_text(
        '```tool {"name": "grep", "arguments": {"q": "error"}} ```'
    )
    assert any(c["name"] == "grep" for c in calls)


def test_terminal_command_fired():
    calls = extract_tool_calls_from_text("Jalankan perintah python test.py")
    assert any(c["name"] == "terminal" for c in calls)
