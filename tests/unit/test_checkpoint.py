import tempfile
from pathlib import Path

from dhybrid.efficiency.checkpoint import (
    RunCheckpoint,
    load_run_checkpoint,
    save_run_checkpoint,
)


def test_roundtrip():
    ckpt = RunCheckpoint(
        run_id="abc", step=3, prompt="halo", system_prompt="sys", cwd="/tmp",
        budget_used=1200, budget_history=[{"prompt": 500, "completion": 100}],
        reflect_iterations=2, repair_rounds=1,
        messages=[{"role": "user", "content": "halo"}, {"role": "assistant", "content": "ok"}],
    )
    with tempfile.TemporaryDirectory() as d:
        p = save_run_checkpoint(str(Path(d) / "r.json"), ckpt)
        got = load_run_checkpoint(p)
    assert got is not None
    assert got.budget_used == 1200
    assert got.budget_history == ckpt.budget_history
    assert got.messages == ckpt.messages
    assert got.step == 3 and got.reflect_iterations == 2


def test_missing_returns_none():
    assert load_run_checkpoint("/tmp/does-not-exist-xyz.json") is None


def test_corrupt_returns_none(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json")
    assert load_run_checkpoint(str(p)) is None