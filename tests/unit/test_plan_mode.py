"""Test Plan/Build Mode: gerbang read-only, tool gate, mode block, izin eskalasi."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dhybrid.agent.hooks import Hooks
from dhybrid.agent.loop.escalation_policy import EscalationConfig, EscalationPolicy
from dhybrid.llm.base import LLMClient, StreamEvent, Usage
from dhybrid.mode import PLAN, apply_mode, mode_system_block
from dhybrid.tools import terminal
from dhybrid.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def _reset_global_gates():
    """Isolasi: jangan biarkan flag readonly bocor ke test lain."""
    yield
    terminal.readonly = False

# ---------- terminal: is_readonly_command ----------

@pytest.mark.parametrize("cmd", [
    "ls -la", "cat file", "head -5 x", "tail -3 y", "wc -l file", "grep foo a",
    "strings file", "watch -n1 df -h", "file a", "stat x", "which git", "pwd",
    "env", "date", "du -sh", "ps aux", "find . -name '*.py'",
    "git status", "git diff", "git log --oneline -3", "git show HEAD",
    "git branch -a", "git ls-files", "git remote -v",
])
def test_readonly_allowed(cmd):
    assert terminal.is_readonly_command(cmd) is True


@pytest.mark.parametrize("cmd", [
    "rm -rf x", "echo hi > f", "a && b", "ls | head", "cat a; rm b",
    "git push", "git commit -m x", "npm install", "pytest", "python script.py",
    "touch f", "mkdir d", "$(ls)", "`ls`", "cat file > out", "rm", "",
])
def test_readonly_denied(cmd):
    assert terminal.is_readonly_command(cmd) is False


# ---------- registry: gate tool readonly ----------

def _reg() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        "write_file",
        "tulis file (mutasi)",
        {"path": {"type": "string"}, "content": {"type": "string"}},
        lambda path="", content="": "written",
    )
    reg.register(
        "read_file",
        "baca file (observasi)",
        {"path": {"type": "string"}},
        lambda path="": "content",
    )
    return reg


def test_registry_readonly_blocks_mutation():
    reg = _reg()
    reg.readonly = True
    out = reg.execute("write_file", {"path": "x", "content": "y"})
    assert out.startswith("ERROR") and "diblokir" in out
    assert reg.execute("read_file", {"path": "x"}) == "content"


def test_registry_readonly_off_normal():
    reg = _reg()
    assert reg.execute("write_file", {"path": "x", "content": "y"}) == "written"


# ---------- apply_mode ----------

def test_apply_mode_plan_sets_gates():
    reg = _reg()
    cfg = SimpleNamespace(mode=PLAN, workflow={})
    ctx = SimpleNamespace(tools=reg, cfg=cfg)
    apply_mode(ctx, PLAN)
    assert ctx.mode == PLAN
    assert reg.readonly is True
    assert terminal.readonly is True
    apply_mode(ctx, "build")
    assert ctx.mode == "build"
    assert reg.readonly is False
    assert terminal.readonly is False


def test_apply_mode_default_from_cfg():
    cfg = SimpleNamespace(mode=PLAN, workflow={})
    ctx = SimpleNamespace(tools=_reg(), cfg=cfg)
    assert apply_mode(ctx) == PLAN


# ---------- mode_system_block ----------

def test_mode_system_block_plan():
    block = mode_system_block(PLAN, {})
    assert "MODE PLAN" in block
    assert "observasi" in block.lower()


def test_mode_system_block_build_workflow():
    block = mode_system_block("build", {"auto_issue": True, "auto_pr": True})
    assert "MODE BUILD" in block
    assert "repo_issue" in block
    assert "repo_pr" in block
    no_pr = mode_system_block("build", {"auto_pr": False})
    assert "jangan buat PR" in no_pr


# ---------- eskalasi: gate izin user ----------

def _policy(confirm):
    cfg = EscalationConfig(
        escalation_chain=["big"],
        max_escalations=2,
        client_factory=lambda preset: object(),
        confirm_fn=confirm,
    )
    return EscalationPolicy(cfg, Hooks())


def test_escalation_confirm_deny():
    pol = _policy(lambda _reason: False)
    res = pol.escalate_for_errors(1, Exception("x"))
    assert res.escalated is False
    assert "menolak" in res.reason


def test_escalation_confirm_allow():
    pol = _policy(lambda _reason: True)
    assert pol.escalate_for_errors(1, Exception("x")).escalated is True


def test_escalation_no_confirm_defaults_auto():
    pol = _policy(None)
    assert pol.escalate_for_errors(1, Exception("x")).escalated is True


# ---------- agent loop: jalur error tool wajib izin ----------

class EchoClient(LLMClient):
    """Client scripted: 'errtool*' → panggil tool boom; 'text:x' → output teks."""

    def __init__(self, replies: list[str]):
        self.replies = list(replies)

    def stream(self, messages, **kw):
        reply = self.replies.pop(0)

        def it():
            if reply.startswith("errtool"):
                yield StreamEvent(
                    kind="tool_call",
                    tool_call={"name": "boom", "arguments": {}, "id": "call_boom"},
                )
            else:
                for ch in reply.replace("text:", ""):
                    yield StreamEvent(kind="delta", text=ch)
            yield StreamEvent(kind="done", usage=Usage(prompt_tokens=1, completion_tokens=1))

        return it()

    def complete(self, messages, **kw):
        return None


def _tools() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register("boom", "meledak", {}, lambda: 1 / 0)
    return reg


def _loop(confirm, small, big):
    from dhybrid.agent.loop.agent_loop import AgentLoop, LoopConfig
    from dhybrid.agent.router import HybridRouter
    from dhybrid.efficiency.budget import TokenBudget
    from dhybrid.efficiency.context import ContextManager

    sm = EchoClient(list(small))
    bg = EchoClient(list(big))
    router = HybridRouter(big_client=bg, small_client=sm, cache=None)
    return AgentLoop(
        router,
        _tools(),
        ContextManager(),
        budget=TokenBudget(soft=10**9, hard=10**9),
        cfg=LoopConfig(escalation_confirm_fn=confirm),
        cwd=_tmp(),
    )


def _tmp() -> str:
    import tempfile

    return tempfile.mkdtemp()


def test_loop_error_escalation_denied():
    loop = _loop(lambda _r: False, small=["errtool", "errtool", "text:jawaban kecil"], big=["text:jawaban besar"])
    res = loop.run("jalankan pytest", "sys")
    assert res.escalated is False


def test_loop_error_escalation_allowed():
    loop = _loop(lambda _r: True, small=["errtool", "errtool", "text:jawaban kecil"], big=["text:jawaban besar"])
    res = loop.run("jalankan pytest", "sys")
    assert res.escalated is True