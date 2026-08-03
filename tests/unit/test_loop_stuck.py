"""Bug: baris DONE membohongi — jalur max_steps habis tidak pernah menghitung
kualitas & bukti file → quality_score default 100/100 padahal 0 file dibuat.

Regresi: model lemah (mis. free text-only) yang cuma recon terminal tanpa
membuat file kini ditandai jujur: skor rendah + stopped_early=True + label
STUCK di UI (bukan "DONE — kualitas 100/100 · 0 file").
"""
import tempfile

from dhybrid.agent.loop import AgentLoop, LoopConfig
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.context import ContextManager
from dhybrid.llm.base import LLMClient, StreamEvent, Usage
from dhybrid.tools.registry import ToolRegistry

EMPTY_CWD = tempfile.mkdtemp(prefix="dhybrid_stuck_")


class ReconClient(LLMClient):
    """Selalu tool-call (recon) — tidak pernah menjawab final → max_steps habis."""

    def __init__(self, name="fake"):
        self.name = name
        self.calls = 0

    def stream(self, messages, **kw):
        self.calls += 1
        yield StreamEvent(
            kind="tool_call",
            tool_call={"id": "t1", "name": "grep", "arguments": {"q": "cek"}},
        )
        yield StreamEvent(kind="done", usage=Usage(prompt_tokens=10, completion_tokens=5))

    def complete(self, messages, **kw):
        from dhybrid.llm.base import ChatMessage, ChatResponse

        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            usage=Usage(),
            model=self.name,
        )

    def model_name(self):
        return self.name


def _tools() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register("grep", "cari", {"q": {"type": "string"}}, lambda q: "src/a.py:1: x")
    return reg


def _run(prompt):
    loop = AgentLoop(
        ReconClient(),
        _tools(),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
        cwd=EMPTY_CWD,
        cfg=LoopConfig(max_steps=3),
    )
    return loop.run(prompt, "system", push_prompt=True)


def test_loop_max_steps_stuck_does_not_claim_done():
    result = _run("buat web login register")
    assert result.steps == 3  # max_steps habis, bukan early-stop
    assert result.files_created == 0
    assert result.quality_score < 100  # TIDAK mengklaim 100/100 tanpa bukti
    assert result.stopped_early is True  # build tanpa bukti file → jujur
    assert result.final_text.strip()


def test_loop_max_steps_nonbuild_keeps_normal():
    # prompt non-build (tanya jawab) yang diam → skor rendah tapi bukan STUCK-build
    result = _run("apa itu laravel")
    assert result.files_created == 0
    assert result.quality_score < 100
