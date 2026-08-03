from dhybrid.agent.parsing import (
    parse_bare_json_calls,
    parse_tool_call,
    parse_tool_calls,
    strip_tool_block,
)

T = chr(96) * 3

# helpers untuk menghindari literal penutup XML/backtick di source test
def o(n):  # open tag <n>
    return chr(60) + n + chr(62)
def c(n):  # close tag </n>
    return chr(60) + "/" + n + chr(62)


def test_parse_and_strip():
    block = '{"name": "grep", "arguments": {"pattern": "def main"}}'
    t = "Saya cari dulu." + T + "tool\n" + block + "\n" + T
    call = parse_tool_call(t)
    assert call and call["name"] == "grep"
    assert call["arguments"]["pattern"] == "def main"
    assert strip_tool_block(t) == "Saya cari dulu."


def test_no_tool():
    assert parse_tool_call("jawaban biasa") is None


def test_invalid_json():
    assert parse_tool_call(T + "tool\n{not json}\n" + T) is None


def test_parse_index_aliased_call():
    text = '{0: "terminal", 1: {"command": "php artisan migrate"}}'
    calls = parse_tool_calls(text)
    assert len(calls) == 1 and calls[0]["name"] == "terminal"
    assert calls[0]["arguments"]["command"] == "php artisan migrate"


def test_parse_index_quoted_key_call():
    text = '{"0": "terminal", "1": {"command": "pwd"}}'
    calls = parse_tool_calls(text)
    assert len(calls) == 1 and calls[0]["arguments"]["command"] == "pwd"


def test_parse_array_call():
    text = '["terminal", {"command": "ls -la"}]'
    calls = parse_tool_calls(text)
    assert len(calls) == 1 and calls[0]["arguments"]["command"] == "ls -la"


def test_parse_arguments_hidden_under_key_1():
    calls = parse_bare_json_calls('{"name": "write_file", "1": {"path": "a.txt", "content": "x"}}')
    assert calls and calls[0]["arguments"]["path"] == "a.txt"


def test_parse_function_tag_format():
    AK = "arg_key"
    AV = "arg_value"
    text = (o("function=terminal") + "\n" + o(AK) + "command" + c(AK) + "\n"
            + o(AV) + "cd /home/p && php artisan serve" + c(AV) + "\n"
            + c("function") + "\n")
    calls = parse_tool_calls(text)
    assert len(calls) == 1 and calls[0]["name"] == "terminal"
    assert calls[0]["arguments"]["command"] == "cd /home/p && php artisan serve"


def test_strip_function_tag_block():
    AK = "arg_key"
    AV = "arg_value"
    text = ("Penasaran.\n" + o("function=terminal") + "\n" + o(AK) + "command"
            + c(AK) + "\n" + o(AV) + "pwd" + c(AV) + "\n" + c("function")
            + "\n" + "Selesai cek.")
    out = strip_tool_block(text)
    assert "function" not in out and "pwd" not in out
    assert "Penasaran." in out and "Selesai cek." in out


def test_parse_invoke_claude_format():
    text = o('invoke name="terminal"') + '{"command": "ls -la"}' + c("invoke")
    calls = parse_tool_calls(text)
    assert len(calls) == 1 and calls[0]["name"] == "terminal"
    assert calls[0]["arguments"]["command"] == "ls -la"


def test_parse_multiple_tool_blocks_dedupe():
    block = '{"name": "grep", "arguments": {"pattern": "x"}}'
    text = T + "tool\n" + block + "\n" + T + "\n" + T + "tool\n" + block + "\n" + T
    calls = parse_tool_calls(text)
    assert len(calls) == 1  # duplikat dibuang oleh dedupe


def test_strip_mixed_blocks_left_clean():
    text = ("Thx " + o("invoke name=\"grep\"") + '{"pattern":"x"}' + c("invoke")
            + " done " + T + "tool\n" + '{"name":"grep","arguments":{"pattern":"x"}}' + "\n" + T)
    out = strip_tool_block(text)
    assert "tool" not in out.lower()
    assert "invoke" not in out.lower()
    assert "Thx" in out and "done" in out
