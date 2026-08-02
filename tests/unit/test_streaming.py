from dhybrid.agent.parsing import dedupe_tool_calls, parse_tool_call, parse_tool_calls
from dhybrid.agent.streaming import ToolBlockFilter


def test_parse_multiple_tool_blocks():
    t = (
        "Aksi 1:\n```tool\n{\"name\": \"terminal\", \"arguments\": {\"command\": \"ls\"}}\n```\n"
        "Aksi 2:\n```tool\n{\"name\": \"grep\", \"arguments\": {\"pattern\": \"x\"}}\n```\n"
        "Selesai."
    )
    calls = parse_tool_calls(t)
    assert len(calls) == 2
    assert calls[0]["name"] == "terminal"
    assert calls[1]["name"] == "grep"
    assert calls[0]["id"].startswith("gen")
    # parse_tool_call (backward-compat) ambil yang pertama
    assert parse_tool_call(t)["name"] == "terminal"


def test_parse_skips_invalid_blocks():
    t = "```tool\n{not json}\n```\n```tool\n{\"name\": \"grep\", \"arguments\": {}}\n```"
    calls = parse_tool_calls(t)
    assert len(calls) == 1
    assert calls[0]["name"] == "grep"


def test_dedupe_identical_calls():
    calls = [
        {"id": "gen0", "name": "terminal", "arguments": {"command": "ls"}},
        {"id": "gen1", "name": "terminal", "arguments": {"command": "ls"}},
        {"id": "gen2", "name": "grep", "arguments": {"pattern": "x"}},
    ]
    out = dedupe_tool_calls(calls)
    assert len(out) == 2


def test_filter_hides_tool_block_keeps_text():
    out = []
    filt = ToolBlockFilter(out.append)
    filt.feed("Saya lihat dulu.\n```tool\n{\"name\": \"terminal\", ")
    filt.feed("\"arguments\": {\"command\": \"ls\"}}\n```\n")
    filt.feed("Selesai memeriksa.")
    filt.flush()
    joined = "".join(out)
    assert "```tool" not in joined
    assert "terminal" not in joined
    assert "Saya lihat dulu." in joined
    assert "Selesai memeriksa." in joined


def test_filter_tiny_chunks_like_real_stream():
    """Delta zen datang per-2-4 karakter — marker terpecah lintas chunk.
    Ini bug nyata yang ditemukan saat uji live (filter mem-flush sebelum marker utuh)."""
    full = 'Baik.\n```tool\n{"name": "terminal", "arguments": {"command": "ls"}}\n```\nSelesai.'
    out = []
    filt = ToolBlockFilter(out.append)
    for i in range(0, len(full), 3):  # chunk 3 karakter
        filt.feed(full[i:i + 3])
    filt.flush()
    joined = "".join(out)
    assert "```tool" not in joined
    assert "terminal" not in joined
    assert "Baik." in joined and "Selesai." in joined


def test_filter_toolcalls_wrapper_chunks():
    full = '<tool_calls>\n<invoke name="terminal">ls</invoke>\n</tool_calls>\nLanjut.'
    out = []
    filt = ToolBlockFilter(out.append)
    for i in range(0, len(full), 4):
        filt.feed(full[i:i + 4])
    filt.flush()
    joined = "".join(out)
    assert "<tool_calls>" not in joined
    assert "<invoke" not in joined
    assert "Lanjut." in joined


def test_filter_unterminated_block_dropped():
    out = []
    filt = ToolBlockFilter(out.append)
    filt.feed("teks\n```tool\n{\"name\": \"x\"}")
    filt.flush()
    assert "".join(out) == "teks\n"


def test_filter_hides_invoke_blocks():
    out = []
    filt = ToolBlockFilter(out.append)
    filt.feed("Saya jalankan.\n<invoke name=\"terminal\">ls -la</invoke>\nSelesai.")
    filt.flush()
    joined = "".join(out)
    assert "<invoke" not in joined
    assert "ls -la" not in joined
    assert "Saya jalankan." in joined and "Selesai." in joined


def test_parse_invoke_format():
    from dhybrid.agent.parsing import parse_tool_calls

    t = 'Saya cek.\n<invoke name="terminal">ls -la</invoke>\n<invoke name="grep">{"pattern": "x"}</invoke>'
    calls = parse_tool_calls(t)
    assert calls[0]["name"] == "terminal"
    assert calls[0]["arguments"] == {"command": "ls -la"}
    assert calls[1]["name"] == "grep"
    assert calls[1]["arguments"] == {"pattern": "x"}


def test_parse_mixed_formats_dedupes():
    from dhybrid.agent.parsing import dedupe_tool_calls, parse_tool_calls

    t = '```tool\n{"name": "grep", "arguments": {"pattern": "x"}}\n```\n<invoke name="grep">{"pattern": "x"}</invoke>'
    calls = dedupe_tool_calls(parse_tool_calls(t))
    assert len(calls) == 1


def test_parse_bare_json_calls():
    """Tool call JSON TELANJANG (tanpa fenced) — format yang sering dipakai model zen."""
    from dhybrid.agent.parsing import parse_tool_calls

    t = (
        'Rencana:\n{"name": "write_file", "arguments": {"path": "app.py", "content": "print(1)"}}\n'
        '{"name": "terminal", "arguments": {"command": "python3 app.py"}}\nSelesai.'
    )
    calls = parse_tool_calls(t)
    names = [c["name"] for c in calls]
    assert "write_file" in names and "terminal" in names
    wf = next(c for c in calls if c["name"] == "write_file")
    assert wf["arguments"]["path"] == "app.py"


def test_parse_bare_json_skips_prose():
    """JSON biasa dalam prosa (bukan tool call) tidak ikut dieksekusi."""
    from dhybrid.agent.parsing import parse_tool_calls

    t = 'Jawaban saya: {"data": [1,2,3]} dan itu saja.'
    assert parse_tool_calls(t) == []


def test_filter_hides_bare_json_block():
    full = 'Saya buat file:\n{"name": "write_file", "arguments": {"path": "a.py", "content": "x"}}\nSelesai.'
    out = []
    filt = ToolBlockFilter(out.append)
    for i in range(0, len(full), 3):
        filt.feed(full[i:i + 3])
    filt.flush()
    joined = "".join(out)
    assert '"name"' not in joined
    assert "Saya buat file:" in joined and "Selesai." in joined
