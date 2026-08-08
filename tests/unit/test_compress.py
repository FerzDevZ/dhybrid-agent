"""Test compact: jalur sukses + provider error → None (tidak crash)."""

from __future__ import annotations

from dhybrid.efficiency.compress import compact_conversation
from dhybrid.llm.base import ChatMessage, ChatResponse, LLMClient, Usage


class _Ok(LLMClient):
    def complete(self, messages, **kw):
        return ChatResponse(
            message=ChatMessage(role="assistant", content="  ringkasan  "),
            usage=Usage(0, 0),
            model="echo",
        )

    def stream(self, messages, **kw):
        raise NotImplementedError


class _Broken(LLMClient):
    def complete(self, messages, **kw):
        raise RuntimeError("502 ResourceExhausted")

    def stream(self, messages, **kw):
        raise NotImplementedError


def test_compact_success():
    out = compact_conversation(_Ok(), [ChatMessage(role="user", content="hi")])
    assert out == "ringkasan"


def test_compact_provider_error_returns_none():
    out = compact_conversation(_Broken(), [ChatMessage(role="user", content="hi")])
    assert out is None