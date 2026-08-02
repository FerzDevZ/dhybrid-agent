"""Provider LLM.

- OpenAICompatClient: melayani OpenAI, OpenRouter, Groq, DeepSeek, Gemini
  (endpoint /v1beta/openai) — semua OpenAI-compatible.
- AnthropicClient: adaptor native /v1/messages dengan cache_control
  (prompt caching = penghemat biaya input terbesar di Anthropic).
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator

import httpx

from dhybrid.config import ModelConfig
from dhybrid.llm.base import (
    ChatMessage,
    ChatResponse,
    LLMClient,
    StreamEvent,
    Usage,
    _parse_arguments,
)

RETRIES = 3
TIMEOUT = 300.0


class OpenAICompatClient(LLMClient):
    def __init__(self, cfg: ModelConfig):
        self.cfg = cfg
        self.base_url = (cfg.base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = cfg.api_key()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, messages: list[ChatMessage], **kw) -> dict:
        payload: dict = {
            "model": self.cfg.model,
            "messages": [m.to_api() for m in messages],
            "max_tokens": kw.get("max_tokens", self.cfg.max_tokens),
            "temperature": kw.get("temperature", self.cfg.temperature),
        }
        if kw.get("stop"):
            payload["stop"] = kw["stop"]
        return payload

    def _post(self, payload: dict) -> httpx.Response:
        last_err: Exception | None = None
        for attempt in range(RETRIES):
            try:
                return httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=TIMEOUT,
                )
            except httpx.HTTPError as e:
                last_err = e
                time.sleep(2**attempt)
        raise last_err  # type: ignore[misc]

    def stream(self, messages: list[ChatMessage], **kw) -> Iterator[StreamEvent]:
        payload = self._payload(messages, **kw)
        payload["stream"] = True
        r = self._post(payload)
        r.raise_for_status()
        acc: dict[int, dict] = {}
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            delta = chunk["choices"][0].get("delta", {})
            if delta.get("content"):
                yield StreamEvent(kind="delta", text=delta["content"])
            for tc in delta.get("tool_calls", []):
                idx = tc.get("index", 0)
                slot = acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if tc.get("id"):
                    slot["id"] = tc["id"]
                if tc["function"].get("name"):
                    slot["name"] = tc["function"]["name"]
                slot["arguments"] += tc["function"].get("arguments", "")
        # tool calls baru lengkap setelah stream selesai (akumulasi per index)
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
        yield StreamEvent(kind="done")

    def complete(self, messages: list[ChatMessage], **kw) -> ChatResponse:
        payload = self._payload(messages, **kw)
        payload["stream"] = False
        r = self._post(payload)
        r.raise_for_status()
        data = r.json()
        msg = data["choices"][0]["message"]
        usage = data.get("usage", {})
        tool_calls = None
        if msg.get("tool_calls"):
            tool_calls = [
                {
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": _parse_arguments(tc["function"].get("arguments", "")),
                }
                for tc in msg["tool_calls"]
            ]
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=msg.get("content") or "",
                tool_calls=tool_calls,
            ),
            usage=Usage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cached_tokens=usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                if isinstance(usage.get("prompt_tokens_details"), dict)
                else 0,
            ),
            model=data.get("model", self.cfg.model),
        )


class AnthropicClient(LLMClient):
    """Adaptor native Anthropic. System prompt diberi cache_control ephemeral
    → prompt caching otomatis (hemat input token antar turn)."""

    def __init__(self, cfg: ModelConfig):
        self.cfg = cfg
        self.base_url = (cfg.base_url or "https://api.anthropic.com/v1").rstrip("/")
        self.api_key = cfg.api_key()

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _to_anthropic(self, messages: list[ChatMessage]) -> dict:
        system_blocks: list[dict] = []
        out: list[dict] = []
        for m in messages:
            if m.role == "system":
                block = {"type": "text", "text": m.content}
                system_blocks.append(block)
            elif m.role == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id,
                                "content": m.content,
                            }
                        ],
                    }
                )
            elif m.role == "assistant" and m.tool_calls:
                out.append(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": tc["id"],
                                "name": tc["name"],
                                "input": tc["arguments"],
                            }
                            for tc in m.tool_calls
                        ],
                    }
                )
            else:
                out.append({"role": m.role, "content": m.content})
        # cache_control hanya valid di blok TERAKHIR dari system
        if system_blocks:
            system_blocks[-1]["cache_control"] = {"type": "ephemeral"}
        return {"system": system_blocks, "messages": out}

    def _post(self, payload: dict) -> httpx.Response:
        last_err: Exception | None = None
        for attempt in range(RETRIES):
            try:
                return httpx.post(
                    f"{self.base_url}/messages",
                    headers=self._headers(),
                    json=payload,
                    timeout=TIMEOUT,
                )
            except httpx.HTTPError as e:
                last_err = e
                time.sleep(2**attempt)
        raise last_err  # type: ignore[misc]

    def _payload(self, messages: list[ChatMessage], **kw) -> dict:
        body = self._to_anthropic(messages)
        body.update(
            {
                "model": self.cfg.model,
                "max_tokens": kw.get("max_tokens", self.cfg.max_tokens),
                "temperature": kw.get("temperature", self.cfg.temperature),
            }
        )
        if kw.get("stop"):
            body["stop_sequences"] = kw["stop"]
        return body

    def stream(self, messages: list[ChatMessage], **kw) -> Iterator[StreamEvent]:
        payload = self._payload(messages, **kw)
        payload["stream"] = True
        r = self._post(payload)
        r.raise_for_status()
        tool_acc: dict[str, dict] = {}
        usage = Usage()
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            event = json.loads(line[5:].strip())
            etype = event.get("type")
            if etype == "message_start":
                u = event.get("message", {}).get("usage", {})
                usage.prompt_tokens = u.get("input_tokens", 0)
            elif etype == "content_block_start":
                cb = event.get("content_block", {})
                if cb.get("type") == "tool_use":
                    tool_acc[event["index"]] = {
                        "id": cb.get("id", ""),
                        "name": cb.get("name", ""),
                        "arguments": "",
                    }
            elif etype == "content_block_delta":
                d = event.get("delta", {})
                if d.get("type") == "text_delta":
                    yield StreamEvent(kind="delta", text=d.get("text", ""))
                elif d.get("type") == "input_json_delta":
                    idx = event.get("index")
                    if idx in tool_acc:
                        tool_acc[idx]["arguments"] += d.get("partial_json", "")
            elif etype == "message_delta":
                u = event.get("usage", {})
                usage.completion_tokens = u.get("output_tokens", 0)
        for idx in sorted(tool_acc):
            t = tool_acc[idx]
            yield StreamEvent(
                kind="tool_call",
                tool_call={
                    "id": t["id"],
                    "name": t["name"],
                    "arguments": _parse_arguments(t["arguments"]),
                },
            )
        if usage.total:
            yield StreamEvent(kind="done", usage=usage)
        else:
            yield StreamEvent(kind="done")

    def complete(self, messages: list[ChatMessage], **kw) -> ChatResponse:
        payload = self._payload(messages, **kw)
        payload["stream"] = False
        r = self._post(payload)
        r.raise_for_status()
        data = r.json()
        tool_calls = None
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls = tool_calls or []
                tool_calls.append(
                    {
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "arguments": block.get("input", {}),
                    }
                )
        u = data.get("usage", {})
        return ChatResponse(
            message=ChatMessage(role="assistant", content=text, tool_calls=tool_calls),
            usage=Usage(
                prompt_tokens=u.get("input_tokens", 0),
                completion_tokens=u.get("output_tokens", 0),
                cached_tokens=u.get("cache_read_input_tokens", 0),
            ),
            model=data.get("model", self.cfg.model),
        )


def make_client(cfg: ModelConfig) -> LLMClient:
    if cfg.provider in ("openai", "openrouter", "groq", "deepseek", "gemini"):
        return OpenAICompatClient(cfg)
    if cfg.provider == "anthropic":
        return AnthropicClient(cfg)
    raise ValueError(f"unsupported provider: {cfg.provider}")
