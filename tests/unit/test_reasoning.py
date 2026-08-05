"""Tests for reasoning traces."""
from dhybrid.agent.reasoning import ReasoningTrace


def test_reasoning_trace_captures_steps():
    trace = ReasoningTrace()
    trace.add_step("analyze", "User wants login", ["read_file:auth.py"])
    trace.add_step("plan", "Will implement JWT", ["write_file:auth.py"])
    steps = trace.get_steps()
    assert len(steps) == 2
    assert steps[0]["phase"] == "analyze"
    assert steps[1]["phase"] == "plan"


def test_reasoning_trace_formats_for_prompt():
    trace = ReasoningTrace()
    trace.add_step("analyze", "User wants login", ["read_file:auth.py"])
    trace.add_step("plan", "Will implement JWT", ["write_file:auth.py"])
    formatted = trace.format_for_prompt()
    assert "analyze" in formatted
    assert "plan" in formatted
    assert "read_file:auth.py" in formatted


def test_reasoning_trace_clear():
    trace = ReasoningTrace()
    trace.add_step("analyze", "User wants login", [])
    trace.clear()
    assert trace.get_steps() == []


def test_reasoning_trace_serialization():
    trace = ReasoningTrace()
    trace.add_step("analyze", "User wants login", ["read_file:auth.py"])
    data = trace.to_dict()
    assert "steps" in data
    assert len(data["steps"]) == 1

    # Restore
    trace2 = ReasoningTrace.from_dict(data)
    assert len(trace2.get_steps()) == 1
    assert trace2.get_steps()[0]["phase"] == "analyze"