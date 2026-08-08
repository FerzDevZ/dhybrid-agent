"""Step executor — single step execution logic (pure, testable)."""

from __future__ import annotations

from dataclasses import dataclass

from dhybrid.agent.hooks import Hooks
from dhybrid.agent.parsing import strip_tool_block
from dhybrid.agent.reasoning import ReasoningTrace
from dhybrid.agent.streaming import ToolBlockFilter
from dhybrid.agent.text_parser import extract_tool_calls_from_text
from dhybrid.llm.base import ChatMessage, ChatResponse, LLMClient, Usage
from dhybrid.security.guard import sanitize_tool_output
from dhybrid.tools.registry import ToolRegistry


@dataclass
class StepConfig:
    """Configuration for step execution."""
    max_tool_output_chars: int = 8000


@dataclass
class StepResult:
    """Result of a single step execution."""
    response: ChatResponse
    tool_events: list[dict]
    reasoning_steps: list[tuple[str, str, list[str]]]  # (phase, description, tools)


class StepExecutor:
    """Executes a single model step: call model → execute tools → return results."""

    def __init__(
        self,
        client: LLMClient,
        tools: ToolRegistry,
        hooks: Hooks,
        reasoning_trace: ReasoningTrace,
        config: StepConfig | None = None,
        cwd: str = ".",
    ):
        self.client = client
        self.tools = tools
        self.hooks = hooks
        self.reasoning_trace = reasoning_trace
        self.config = config or StepConfig()
        self.cwd = cwd

    def execute(
        self,
        messages: list[ChatMessage],
    ) -> StepResult:
        """Execute one complete step: model call + tool execution."""
        # 1. Call model
        response = self._call_model(messages)

        # 2. Execute tools if any
        tool_events = []
        if response.message.tool_calls:
            tool_events = self._execute_tools(response.message.tool_calls)
        elif response.fallback_tool_call:
            # Text mode - already handled in _call_model
            pass

        # 3. Extract reasoning steps
        reasoning_steps = self.reasoning_trace.get_steps()

        return StepResult(
            response=response,
            tool_events=tool_events,
            reasoning_steps=reasoning_steps,
        )

    def _call_model(self, messages: list[ChatMessage]) -> ChatResponse:
        """Call model with streaming, handle tool calls."""
        text = ""
        tool_calls: list[dict] = []
        usage = None
        filt = ToolBlockFilter(self.hooks.delta) if self.hooks.on_delta else None
        if filt:
            import os
            filt.debug = bool(os.environ.get("DHYBRID_DEBUG"))

        for ev in self.client.stream(messages):
            if ev.kind == "delta":
                text += ev.text
                if filt:
                    filt.feed(ev.text)
            elif ev.kind == "tool_call" and ev.tool_call:
                tool_calls.append(ev.tool_call)
            elif ev.kind == "done" and ev.usage:
                usage = ev.usage

        if filt:
            filt.flush()

        fallback = False
        if not tool_calls:
            calls = extract_tool_calls_from_text(text)
            if calls:
                tool_calls = calls
                text = strip_tool_block(text)
                fallback = True

        self.reasoning_trace.add_step("start", f"Model response ({len(text)} chars)", [])

        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=text,
                tool_calls=tool_calls or None,
            ),
            usage=usage or Usage(),
            model=self.client.model_name(),
            fallback_tool_call=fallback,
        )

    def _execute_tools(self, tool_calls: list[dict]) -> list[dict]:
        """Execute tool calls and return events."""
        events = []
        for tc in tool_calls:
            tool_name = tc["name"]
            self.reasoning_trace.add_step("execute", f"Running {tool_name}", [tool_name])
            output = self.tools.execute(tool_name, tc.get("arguments", {}))
            # Guard injeksi: netralkan percobaan instruksi dari output tool
            # (web scrape, file user) SEBELUM masuk konteks.
            output = sanitize_tool_output(output, self.config.max_tool_output_chars)
            events.append({
                "name": tool_name,
                "args": tc.get("arguments", {}),
                "output": output,
            })
            self.hooks.tool(tool_name, tc.get("arguments", {}), output)
            self.reasoning_trace.add_step("observe", f"Tool {tool_name} completed", [tool_name])
        return events

    def format_tool_results(self, events: list[dict]) -> list[ChatMessage]:
        """Format tool execution results as chat messages (for text mode)."""
        messages = []
        for ev in events:
            messages.append(
                ChatMessage(
                    role="user",
                    content=f"[Hasil tool '{ev['name']}']\n{ev['output']}",
                )
            )
        return messages

    def format_native_tool_results(self, tool_calls: list[dict], events: list[dict]) -> list[ChatMessage]:
        """Format tool results for native tool calling (role: tool)."""
        messages = []
        for tc, ev in zip(tool_calls, events):
            messages.append(
                ChatMessage(
                    role="tool",
                    content=ev["output"],
                    tool_call_id=tc["id"],
                )
            )
        return messages