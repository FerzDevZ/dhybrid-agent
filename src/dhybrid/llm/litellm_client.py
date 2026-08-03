"""Adaptor LLM via litellm — satu SDK untuk 100+ provider (opsional).

Provider "litellm" dipilih lewat config; default path (openai/anthropic)
TIDAK berubah. Model string litellm, mis.:
  - "openai/gpt-4o", "anthropic/claude-3-5-sonnet-20241022"
  - "gemini/gemini-2.0-flash", "groq/llama-3.3-70b-versatile"
  - "ollama/llama3.2" (lokal — di laptop lemah tidak disarankan)
"""

from __future__ import annotations

from collections.abc import Iterator

from dhybrid.config import ModelConfig
from dhybrid.llm.base import (
    ChatMessage,
    ChatResponse,
    LLMClient,
    StreamEvent,
    Usage,
    _parse_arguments,
)


class LiteLLMClient(LLMClient):
    def __init__(self, cfg: ModelConfig):
        self.cfg = cfg
        self.model = cfg.model
        self.api_key = cfg.api_key()
        self.base_url = cfg.base_url

    def _opts(self) -> dict:
        opts: dict = {}
        if self.api_key:
            opts["api_key"] = self.api_key
        if self.base_url:
            opts["api_base"] = self.base_url
        return opts

    @staticmethod
    def _drop_params() -> None:
        import litellm  # import lambat: paket opsional

        litellm.drop_params = True  # provider lain mungkin tolak param ekstra

    def stream(self, messages: list[ChatMessage], **kw) -> Iterator[StreamEvent]:
        self._drop_params()
        import litellm

        payload: dict = {
            "model": self.model,
            "messages": [m.to_api() for m in messages],
            "stream": True,
        }
        if kw.get("max_tokens"):
            payload["max_tokens"] = kw["max_tokens"]
        if kw.get("temperature") is not None:
            payload["temperature"] = kw["temperature"]
        if kw.get("stop"):
            payload["stop"] = kw["stop"]

        acc: dict[int, dict] = {}
        usage: Usage | None = None
        for chunk in litellm.completion(**payload, **self._opts()):
            u = getattr(chunk, "usage", None)
            if u is not None:
                details = getattr(u, "prompt_tokens_details", None) or {}
                usage = Usage(
                    prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(u, "completion_tokens", 0) or 0,
                    cached_tokens=getattr(details, "cached_tokens", 0)
                    if details
                    else 0,
                )
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue
            content = getattr(delta, "content", None)
            if content:
                yield StreamEvent(kind="delta", text=content)
            for tc in getattr(delta, "tool_calls", None) or []:
                idx = getattr(tc, "index", 0)
                slot = acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if getattr(tc, "id", None):
                    slot["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        slot["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        slot["arguments"] += fn.arguments
        for idx in sorted(acc):
            slot = acc[idx]
            yield StreamEvent(
                kind="tool_call",
                tool_call={
                    "id": slot["id"] or f"call_{idx}",
                    "name": slot["name"],
                    "arguments": _parse_arguments(slot["arguments"]),
                },
            )
        yield StreamEvent(kind="done", usage=usage)

    def complete(self, messages: list[ChatMessage], **kw) -> ChatResponse:
        self._drop_params()
        import litellm

        resp = litellm.completion(
            model=self.model,
            messages=[m.to_api() for m in messages],
            **self._opts(),
        )
        msg = resp.choices[0].message
        usage = getattr(resp, "usage", None) or {}
        tool_calls = None
        if getattr(msg, "tool_calls", None):
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": _parse_arguments(tc.function.arguments or ""),
                }
                for tc in msg.tool_calls
            ]
        details = getattr(usage, "prompt_tokens_details", None) or {}
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=getattr(msg, "content", None) or "",
                tool_calls=tool_calls,
            ),
            usage=Usage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                cached_tokens=getattr(details, "cached_tokens", 0)
                if details
                else 0,
            ),
            model=getattr(resp, "model", None) or self.model,
        )
