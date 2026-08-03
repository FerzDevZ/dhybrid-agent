import json

import httpx
import pytest

from dhybrid.config import ModelConfig
from dhybrid.llm.base import ChatMessage
from dhybrid.llm.providers import AnthropicClient, OpenAICompatClient, make_client


def _sse(data_list):
    body = "".join(f"data: {json.dumps(d)}\n\n" for d in data_list) + "data: [DONE]\n\n"
    return httpx.Response(200, text=body, request=httpx.Request("POST", "http://t"))


def test_stream_parses_deltas(monkeypatch):
    client = OpenAICompatClient(ModelConfig(provider="openai", model="m", base_url="http://t/v1"))
    chunks = [
        {"choices": [{"delta": {"content": "hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
    ]
    monkeypatch.setattr(client, "_post", lambda payload: _sse(chunks))
    texts = [e.text for e in client.stream([]) if e.kind == "delta"]
    assert texts == ["hel", "lo"]


def test_stream_tolerates_chunk_without_choices(monkeypatch):
    """Regresi: byNara dsb kirim chunk terakhir berisi usage TANPA choices.
    Dulu chunk['choices'][0] → IndexError. Harus dilewati tanpa crash."""
    client = OpenAICompatClient(ModelConfig(provider="openai", model="m", base_url="http://t/v1"))
    chunks = [
        {"choices": [{"delta": {"content": "hi"}}]},
        {"usage": {"prompt_tokens": 1, "completion_tokens": 1}, "choices": []},
    ]
    monkeypatch.setattr(client, "_post", lambda payload: _sse(chunks))
    events = list(client.stream([]))
    texts = [e.text for e in events if e.kind == "delta"]
    assert texts == ["hi"]
    done = [e for e in events if e.kind == "done"]
    assert done and done[0].usage is not None and done[0].usage.total == 2


def test_complete_tolerates_missing_choices(monkeypatch):
    client = OpenAICompatClient(ModelConfig(provider="openai", model="m", base_url="http://t/v1"))
    body = {"usage": {"prompt_tokens": 1, "completion_tokens": 1}}  # tanpa choices
    monkeypatch.setattr(client, "_post", lambda payload: httpx.Response(200, json=body, request=httpx.Request("POST", "http://t")))
    with pytest.raises(RuntimeError):
        client.complete([])


def test_stream_accumulates_tool_calls(monkeypatch):
    client = OpenAICompatClient(ModelConfig(provider="openai", model="m", base_url="http://t/v1"))
    chunks = [
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "t1", "function": {"name": "grep", "arguments": '{"pat'}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'tern": "x"}'}}]}}]},
    ]
    monkeypatch.setattr(client, "_post", lambda payload: _sse(chunks))
    calls = [e.tool_call for e in client.stream([]) if e.kind == "tool_call"]
    assert calls[0]["id"] == "t1"
    assert calls[0]["name"] == "grep"
    assert calls[0]["arguments"] == {"pattern": "x"}


def test_complete_parses_tool_calls(monkeypatch):
    client = OpenAICompatClient(ModelConfig(provider="openai", model="m", base_url="http://t/v1"))
    body = {
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": [{
                    "id": "t1", "type": "function",
                    "function": {"name": "grep", "arguments": json.dumps({"q": "x"})},
                }],
            }
        }],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7},
    }
    monkeypatch.setattr(client, "_post", lambda payload: httpx.Response(200, json=body, request=httpx.Request("POST", "http://t")))
    resp = client.complete([])
    assert resp.message.tool_calls[0]["name"] == "grep"
    assert resp.usage.total == 12


def test_anthropic_system_has_cache_control():
    c = AnthropicClient(ModelConfig(provider="anthropic", model="claude", api_key_env="ANTHROPIC_API_KEY"))
    out = c._to_anthropic([ChatMessage(role="system", content="SYS"), ChatMessage(role="user", content="hi")])
    assert out["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert out["messages"][0] == {"role": "user", "content": "hi"}


def test_anthropic_tool_result_conversion():
    c = AnthropicClient(ModelConfig(provider="anthropic", model="claude", api_key_env="ANTHROPIC_API_KEY"))
    msgs = [
        ChatMessage(role="assistant", content="", tool_calls=[{"id": "tu1", "name": "grep", "arguments": {"q": "x"}}]),
        ChatMessage(role="tool", content="hasil", tool_call_id="tu1"),
    ]
    out = c._to_anthropic(msgs)
    assert out["messages"][0]["content"][0]["type"] == "tool_use"
    assert out["messages"][1]["content"][0]["type"] == "tool_result"
    assert out["messages"][1]["content"][0]["tool_use_id"] == "tu1"


def test_make_client_unsupported():
    import pytest

    from dhybrid.config import ModelConfig

    with pytest.raises(ValueError):
        make_client(ModelConfig(provider="nope", model="x"))
