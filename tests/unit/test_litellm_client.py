"""Test adapter litellm — stream (delta + tool_calls fragment) & complete.

Litellm dimock (SimpleNamespace) — tidak ada panggilan jaringan nyata."""

from types import SimpleNamespace as NS

import pytest

from dhybrid.config import ModelConfig
from dhybrid.llm.base import ChatMessage
from dhybrid.llm.litellm_client import LiteLLMClient
from dhybrid.llm.providers import make_client


def _cfg(**kw) -> ModelConfig:
    c = ModelConfig(provider="litellm", model="openai/gpt-4o", api_key_env="TEST_LITELLM_KEY")
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _chunk(content=None, tool_calls=None, usage=None):
    delta = {}
    if content:
        delta["content"] = content
    if tool_calls:
        delta["tool_calls"] = tool_calls
    return NS(choices=[NS(delta=NS(**delta))], usage=usage)


def _tool_slot(index, tc_id="", name="", arguments=""):
    fn = NS(name=name, arguments=arguments)
    return NS(index=index, id=tc_id, function=fn)


class _FakeLiteLLM:
    def __init__(self, chunks=None, resp=None):
        self._chunks = chunks or []
        self._resp = resp
        self.drop_params = False

    def completion(self, **kw):
        if self._chunks:
            return iter(self._chunks)
        return self._resp


@pytest.fixture
def fake_litellm(monkeypatch):
    fake = _FakeLiteLLM()

    def _patch(chunks=None, resp=None):
        fake._chunks = chunks or []
        fake._resp = resp
        monkeypatch.setitem(__import__("sys").modules, "litellm", fake)

    return fake, _patch


def test_make_client_returns_litellm_adapter():
    assert isinstance(make_client(_cfg()), LiteLLMClient)


def test_stream_delta_and_tool_calls(fake_litellm):
    _, patch = fake_litellm
    patch(
        chunks=[
            _chunk(content="Halo"),
            _chunk(content=" dunia"),
            _chunk(
                tool_calls=[
                    _tool_slot(0, tc_id="call_1", name="term", arguments='{"com'),
                    _tool_slot(1, name="grep"),
                ]
            ),
            _chunk(tool_calls=[_tool_slot(0, arguments='mand": "ls"}')]),
            _chunk(tool_calls=[_tool_slot(1, arguments='{"pattern": "x"')]),
            _chunk(tool_calls=[_tool_slot(1, arguments='}')]),
            NS(choices=[], usage=NS(prompt_tokens=10, completion_tokens=5)),
        ]
    )
    client = LiteLLMClient(_cfg())
    events = list(client.stream([ChatMessage(role="user", content="halo")]))
    kinds = [e.kind for e in events]
    assert kinds == ["delta", "delta", "tool_call", "tool_call", "done"]
    assert "".join(e.text for e in events if e.kind == "delta") == "Halo dunia"
    tcs = [e.tool_call for e in events if e.kind == "tool_call" and e.tool_call is not None]
    assert tcs[0]["name"] == "term"
    assert tcs[0]["arguments"] == {"command": "ls"}
    assert tcs[0]["id"] == "call_1"
    assert tcs[1]["name"] == "grep"
    assert tcs[1]["arguments"] == {"pattern": "x"}
    done = events[-1]
    assert done.usage is not None and done.usage.prompt_tokens == 10


def test_complete_with_tool_calls(fake_litellm):
    _, patch = fake_litellm
    msg = NS(
        content="",
        tool_calls=[
            NS(id="c1", function=NS(name="read_file", arguments='{"path": "a.py"}')),
        ],
    )
    resp = NS(choices=[NS(message=msg)], usage=NS(prompt_tokens=7, completion_tokens=3), model="openai/gpt-4o")
    patch(resp=resp)
    client = LiteLLMClient(_cfg())
    out = client.complete([ChatMessage(role="user", content="baca")])
    tcs = out.message.tool_calls
    assert tcs is not None and tcs[0]["name"] == "read_file"
    assert tcs[0]["arguments"] == {"path": "a.py"}
    assert out.usage.prompt_tokens == 7
    assert out.model == "openai/gpt-4o"
