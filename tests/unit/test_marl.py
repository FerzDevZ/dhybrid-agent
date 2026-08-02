"""Test MARL: kualitas output, verifier, scoreboard, escalation."""

from dhybrid.agent.quality import score_output
from dhybrid.agent.scoreboard import Scoreboard
from dhybrid.agent.verify import (
    count_created_files,
    snapshot_files,
    verify_build,
)
from dhybrid.agent.verify import tests_info as _tests_info


def test_score_output_cases():
    assert score_output("") == 0
    assert score_output("Saya tidak bisa melakukan itu") < 40
    assert score_output("Mau pakai stack apa?", is_build=True, files_created=0) < 30
    assert score_output("Selesai, 3 file dibuat", is_build=True, files_created=3, tests_passed=True) >= 50
    assert score_output("jawaban normal") >= 40


def test_verify_snapshot_and_created(tmp_path):
    (tmp_path / "a.py").write_text("x")
    before = snapshot_files(str(tmp_path))
    assert "a.py" in before
    (tmp_path / "b.py").write_text("y")
    after = snapshot_files(str(tmp_path))
    assert count_created_files(before, after) == 1
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("z")
    assert ".git/config" not in snapshot_files(str(tmp_path))


def test_verify_tests_info():
    events = [
        {"name": "run_tests", "output": "2 passed in 0.1s"},
        {"name": "terminal", "output": "ls"},
    ]
    passed, count = _tests_info(events)
    assert passed is True and count == 1
    events2 = [{"name": "run_tests", "output": "1 failed, 2 passed"}]
    assert _tests_info(events2)[0] is False


def test_verify_build_summary(tmp_path):
    before = snapshot_files(str(tmp_path))
    (tmp_path / "x.py").write_text("x")
    after = snapshot_files(str(tmp_path))
    v = verify_build(str(tmp_path), before, after, [{"name": "run_tests", "output": "1 passed"}])
    assert v["files_created"] == 1 and v["tests_passed"] is True


def test_scoreboard_roundtrip(tmp_path):
    sb = Scoreboard(tmp_path / "sb.sqlite")
    sb.record("model-a", 80)
    sb.record("model-a", 60)
    sb.record("model-b", 30)
    rows = sb.table()
    assert rows[0][0] == "model-a" and rows[0][1] == 70.0
    assert sb.best_available(["model-b", "model-a"]) == "model-a"
    assert sb.best_available(["model-x"]) is None
    assert sb.best_available([]) is None


def test_loop_escalates_on_low_quality():
    """Skor sangat rendah (menolak) → beralih ke client chain berikutnya."""
    from dhybrid.agent.loop import AgentLoop, LoopConfig
    from dhybrid.efficiency.budget import TokenBudget
    from dhybrid.efficiency.context import ContextManager
    from dhybrid.llm.base import (
        ChatMessage,
        ChatResponse,
        LLMClient,
        StreamEvent,
        Usage,
    )
    from dhybrid.tools.registry import ToolRegistry

    class Refuser(LLMClient):
        def __init__(self, text):
            self.text = text
            self.calls = 0

        def stream(self, messages, **kw):
            self.calls += 1
            yield StreamEvent(kind="delta", text=self.text)
            yield StreamEvent(kind="done", usage=Usage(5, 5))

        def complete(self, messages, **kw):
            return ChatResponse(message=ChatMessage(role="assistant", content="x"), usage=Usage(), model="f")

        def model_name(self):
            return "refuser"

    class Worker(LLMClient):
        def __init__(self):
            self.calls = 0

        def stream(self, messages, **kw):
            self.calls += 1
            yield StreamEvent(kind="delta", text="Selesai: berhasil dikerjakan")
            yield StreamEvent(kind="done", usage=Usage(5, 5))

        def complete(self, messages, **kw):
            return ChatResponse(message=ChatMessage(role="assistant", content="x"), usage=Usage(), model="f")

        def model_name(self):
            return "worker"

    tools = ToolRegistry()
    tools.register("grep", "cari", {"q": {"type": "string"}}, lambda q: "ok")
    refuser = Refuser("Saya tidak bisa mengerjakan ini")
    worker = Worker()
    loop = AgentLoop(refuser, tools, ContextManager(), TokenBudget(soft=10**9, hard=10**9),
                     cfg=LoopConfig(quality_threshold=40), chain=[worker])
    res = loop.run("buatkan aplikasi login", "sys")
    assert res.escalated_quality
    assert worker.calls >= 1
    assert "berhasil" in res.final_text
