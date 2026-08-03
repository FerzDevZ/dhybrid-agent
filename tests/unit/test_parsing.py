from dhybrid.agent.parsing import (
    parse_bare_json_calls,
    parse_tool_call,
    parse_tool_calls,
    strip_tool_block,
)


def test_parse_and_strip():
    t = 'Saya cari dulu.\n```tool\n{"name": "grep", "arguments": {"pattern": "def main"}}\n```'
    call = parse_tool_call(t)
    assert call["name"] == "grep"
    assert call["arguments"]["pattern"] == "def main"
    assert strip_tool_block(t) == "Saya cari dulu."


def test_no_tool():
    assert parse_tool_call("jawaban biasa") is None


def test_invalid_json():
    assert parse_tool_call("```tool\n{not json}\n```") is None


# ---- Regresi dari sesi nyata: model free memakai <tool_call> + kunci INDEKS {0,1} ----


def test_parse_index_aliased_call():
    """Format {0: nama, 1: args} (meniru array) harus dipetakan ke name/arguments,
    bukan dibuang diam-diam — penyebab 'agent macet/tidak ada respon'."""
    text = '<tool_call>\n{0: "terminal", 1: {"command": "php artisan migrate"}}\n</tool_call>'
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "terminal"
    assert calls[0]["arguments"]["command"] == "php artisan migrate"


def test_parse_multiple_index_aliased_calls():
    text = (
        '<tool_call>\n{0: "terminal", 1: {"command": "pwd"}}\n'
        '{0: "web_fetch", 1: {"url": "http://localhost:8000"}}\n'
        '<tool_call>\n'
    )
    calls = parse_tool_calls(text)
    names = {c["name"] for c in calls}
    assert names == {"terminal", "web_fetch"}


def test_parse_arguments_hidden_under_key_1():
    """Bila name ada tapi arguments disembunyikan di kunci '1', tetap tertangkap."""
    calls = parse_bare_json_calls('{"name": "write_file", "1": {"path": "a.txt", "content": "x"}}')
    assert calls and calls[0]["arguments"]["path"] == "a.txt"


def test_strip_tool_call_tags_and_index_lines():
    t = ("Selesai.\n<tool_call>\n"
         '{0: "terminal", 1: {"command": "pwd"}}\n'
         "</anteThinking>\n<tool_call>\nresponse\n")
    # prosa yang tersisa setelah markup dibersihkan
    assert strip_tool_block(t) == "Selesai."
