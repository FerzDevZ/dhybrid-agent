from dhybrid.agent.parsing import parse_tool_call, strip_tool_block


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
