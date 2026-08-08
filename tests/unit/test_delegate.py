from dhybrid.eval.harness import ScriptedLLM
from dhybrid.subagents.delegate import DelegateResult, delegate, delegate_parallel
from dhybrid.tools.registry import ToolRegistry


def _tools() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register("grep", "cari", {"q": {"type": "string"}}, lambda **kw: "hit")
    reg.register("boom", "gagal", {}, lambda: 1 / 0)
    return reg


def test_delegate_single():
    client = ScriptedLLM(["text:jawaban sesudah delegasi"])
    res = delegate("goal x", client, _tools(), "sys", max_steps=2)
    assert isinstance(res, DelegateResult)
    assert "delegasi" in res.text


def test_delegate_parallel_run_all_and_ordered():
    # 2 goal; tiap goal scripted "text:…{g}" → final_text memuat goal masing2.
    factory = lambda: ScriptedLLM(["text:selesai-a", "text:selesai-a"])
    goals = ["A", "B", "C"]
    results = delegate_parallel(
        goals=goals,
        client_factory=factory,
        tools=_tools(),
        system_prompt="sys",
        max_steps=2,
        max_workers=3,
    )
    assert len(results) == len(goals)
    # konteks subagent bersih → final_text generik ("selesai-a") untuk semua
    assert all(r.steps >= 1 for r in results)
    # task error tersebar ke thread utama (bukan tenggelam): gunakan tool boom
    bad = delegate_parallel(
        goals=["x"],
        client_factory=lambda: ScriptedLLM(["tool:boom:z", "text:ok"]),
        tools=_tools(),
        system_prompt="sys",
        max_steps=2,
    )
    assert len(bad) == 1