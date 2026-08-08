"""RegressionHarness — evaluasi perilaku agent secara deterministik.

Tujuan: setiap perubahan kode dicek tidak membuat agent "makin lemah" pada
kasus-kasus yang sudah pernah diperbaiki (kasus bug historis).

Cara: skenario = prompt + daftar respon model palsu (scripted) + assertion.
Harness menjalankan AgentLoop dengan client palsu yang TIDAK bergantung model
asli (deterministik, cepat, offline), lalu membandingkan hasil (final_text,
quality, jumlah nudge/refleksi, bukti build) terhadap ekspektasi.

Gunakan di `tests/regression/` supaya terbawa ke CI.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from dhybrid.agent.loop.agent_loop import AgentLoop, LoopConfig
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.context import ContextManager
from dhybrid.llm.base import ChatMessage, ChatResponse, StreamEvent, Usage
from dhybrid.tools.registry import ToolRegistry


class ScriptedLLM:
    """Respon tetap per panggilan; `tool:name:arg` memicu tool call, `text:` teks."""

    def __init__(self, replies, name="fake"):
        self.replies = list(replies)
        self.name = name
        self.calls = 0
        self.seen_system: list[str] = []

    def stream(self, messages, **kw):
        self.calls += 1
        # catat teks user/system yang SUDAH ada di konteks panggilan ini
        for m in messages:
            c = getattr(m, "content", None)
            if c:
                self.seen_system.append(c)
        if self.calls <= len(self.replies):
            r = self.replies[self.calls - 1]
        else:
            r = "text:selesai"
        if r.startswith("tool:"):
            _, name, arg = r.split(":", 2)
            yield StreamEvent(
                kind="tool_call", tool_call={"id": "t1", "name": name, "arguments": {"q": arg}}
            )
        else:
            yield StreamEvent(kind="delta", text=r.removeprefix("text:"))
        yield StreamEvent(kind="done", usage=Usage(prompt_tokens=10, completion_tokens=5))

    def complete(self, messages, **kw):
        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model=self.name
        )

    def model_name(self):
        return self.name


@dataclass
class Scenario:
    name: str
    prompt: str
    replies: list[str]
    # assertions — kosong = cukup pastikan selesai tanpa error
    expect_final_contains: list[str] = field(default_factory=list)
    max_nudges: int = 3
    max_reflect: int | None = None   # ekspektasi jumlah refleksi (None = bebas)
    expect_stopped_early: bool | None = None
    expect_files_created: bool | None = None
    expect_repair: bool | None = None  # True=harus ada [repair], False=tidak boleh
    max_repair: int = 2
    setup_tools: Callable[[ToolRegistry], None] | None = None


@dataclass
class ScenarioResult:
    scenario: Scenario
    passed: bool
    failures: list[str]
    result: object | None = None

    @property
    def summary(self) -> str:
        return f"[{'PASS' if self.passed else 'FAIL'}] {self.scenario.name}"


class RegressionHarness:
    """Menjalankan skenario & mengumpulkan hasil (offline, tanpa model asli)."""

    def __init__(self, cwd: str | None = None):
        self.base_dir = cwd or tempfile.mkdtemp(prefix="dhybrid_harness_")

    def _tools(self, cwd: str) -> ToolRegistry:
        reg = ToolRegistry()
        reg.register("grep", "cari", {"q": {"type": "string"}}, lambda **kw: "hit.txt:1: x")

        def _write(**kw):
            name = kw.get("path") or kw.get("q") or "out.txt"
            path = Path(cwd) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            # file .py (test) ditulis "gagal" agar auto-verify punya bahan repair
            if name.endswith(".py"):
                path.write_text("def test_broken():\n    assert False\n")
            else:
                path.write_text("ok\n")
            return f"wrote {name}"

        reg.register("write_file", "tulis", {"path": {"type": "string"}}, _write)
        reg.register("boom", "gagal", {}, lambda: 1 / 0)
        return reg

    def run(self, scenario: Scenario) -> ScenarioResult:
        # cwd fresh per scenario → tidak ada file sisa antar skenario
        cwd = tempfile.mkdtemp(prefix="dhybrid_harness_")
        reg = self._tools(cwd)
        if scenario.setup_tools:
            scenario.setup_tools(reg)
        client = ScriptedLLM(scenario.replies)
        loop = AgentLoop(
            client,
            reg,
            ContextManager(),
            TokenBudget(soft=10**9, hard=10**9),
            cfg=LoopConfig(max_nudges=scenario.max_nudges, max_repair_rounds=scenario.max_repair),
            cwd=cwd,
        )
        res = loop.run(scenario.prompt, "sys")
        failures: list[str] = []
        for needle in scenario.expect_final_contains:
            if needle not in (res.final_text or ""):
                failures.append(f"final_text tidak memuat '{needle}': {res.final_text!r}")
        if scenario.max_reflect is not None and res.reflect_iterations != scenario.max_reflect:
            failures.append(
                f"reflect_iterations={res.reflect_iterations} (ekspektasi {scenario.max_reflect})"
            )
        if scenario.expect_stopped_early is not None and res.stopped_early != scenario.expect_stopped_early:
            failures.append(f"stopped_early={res.stopped_early}")
        if scenario.expect_files_created is not None:
            has = res.files_created > 0
            if has != scenario.expect_files_created:
                failures.append(f"files_created={res.files_created}")
        if scenario.expect_repair is not None:
            repaired = any("[repair 1]" in c for c in client.seen_system)
            if repaired != scenario.expect_repair:
                failures.append(f"repair diterima? {repaired}")
        return ScenarioResult(scenario, not failures, failures, res)

    def run_all(self, scenarios: list[Scenario]) -> list[ScenarioResult]:
        return [self.run(s) for s in scenarios]

    @staticmethod
    def report(results: list[ScenarioResult]) -> str:
        lines = ["Regression Harness"]
        for r in results:
            if r.failures:
                for f in r.failures:
                    lines.append(f"  - FAIL {r.scenario.name}: {f}")
        passed = sum(1 for r in results if r.passed)
        lines.append(f"{passed}/{len(results)} scenario pass")
        return "\n".join(lines)
