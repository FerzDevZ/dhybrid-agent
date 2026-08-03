import tempfile

from dhybrid.agent.loop import AgentLoop, LoopConfig
from dhybrid.agent.router import HybridRouter
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.context import ContextManager
from dhybrid.llm.base import ChatMessage, ChatResponse, LLMClient, StreamEvent, Usage
from dhybrid.tools.registry import ToolRegistry

# cwd kosong yang stabil supaya snapshot_files deterministik (tidak bocor
# isi repo ke bukti "files_created" saat unit test).
EMPTY_CWD = tempfile.mkdtemp(prefix="dhybrid_loop_")


class ScriptedClient(LLMClient):
    def __init__(self, replies, name="fake"):
        self.replies = replies
        self.name = name
        self.calls = 0
        self.last_messages = None

    def stream(self, messages, **kw):
        self.calls += 1
        self.last_messages = messages
        if self.calls <= len(self.replies):
            r = self.replies[self.calls - 1]
            if r.startswith("tool:"):
                _, name, arg = r.split(":", 2)
                yield StreamEvent(kind="tool_call", tool_call={"id": "t1", "name": name, "arguments": {"q": arg}})
            elif r == "errtool":
                yield StreamEvent(kind="tool_call", tool_call={"id": "t1", "name": "boom", "arguments": {}})
            else:
                text = r.removeprefix("text:")
                yield StreamEvent(kind="delta", text=text)
        else:
            yield StreamEvent(kind="delta", text="selesai")
        yield StreamEvent(kind="done", usage=Usage(prompt_tokens=10, completion_tokens=5))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model=self.name)

    def model_name(self):
        return self.name


def _tools():
    reg = ToolRegistry()
    reg.register("grep", "cari", {"q": {"type": "string"}}, lambda q: f"src/a.py:1: {q}")
    reg.register("boom", "gagal", {}, lambda: 1 / 0)
    return reg


def test_loop_tool_then_final():
    loop = AgentLoop(
        ScriptedClient(["tool:grep:x", "text:ketemu: line 1"]),
        _tools(),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
        cwd=EMPTY_CWD,
    )
    res = loop.run("cari x", "kamu agent")
    assert res.final_text == "ketemu: line 1"
    assert res.steps == 2


def test_loop_early_stop_signal():
    loop = AgentLoop(
        ScriptedClient(["text:TIDAK ADA YANG PERLU DIUBAH."]),
        _tools(),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
        cwd=EMPTY_CWD,
    )
    res = loop.run("cek", "sys")
    assert res.stopped_early


class _AskClient(LLMClient):
    """Call 1: panggil tool ask_user; call berikutnya: jawaban teks."""

    def __init__(self, name="askfake"):
        self.name = name
        self.calls = 0

    def stream(self, messages, **kw):
        self.calls += 1
        if self.calls == 1:
            yield StreamEvent(kind="tool_call", tool_call={
                "id": "t1",
                "name": "ask_user",
                "arguments": {"prompt": "pakai Django atau Flask?", "options": ["Django", "Flask"]},
            })
        else:
            yield StreamEvent(kind="delta", text="selesai")
        yield StreamEvent(kind="done", usage=Usage(prompt_tokens=10, completion_tokens=5))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model=self.name)

    def model_name(self):
        return self.name


def _ask_tools(state):
    from dhybrid.tools.ask import register as register_ask

    reg = ToolRegistry()
    register_ask(reg, state)
    return reg


def test_loop_pauses_for_ask_user():
    from dhybrid.tools.ask import AskState

    state = AskState(interactive=True)
    loop = AgentLoop(
        _AskClient(),
        _ask_tools(state),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
        cwd=EMPTY_CWD,
        ask_state=state,
    )
    res = loop.run("buat web app", "sys")
    assert res.pending_question == {
        "prompt": "pakai Django atau Flask?",
        "options": ["Django", "Flask"],
    }
    assert state.pending is None  # pertanyaan sudah diambil loop untuk REPL


def test_loop_ask_user_blocked_non_interactive():
    from dhybrid.tools.ask import AskState

    state = AskState(interactive=False)
    loop = AgentLoop(
        _AskClient(),
        _ask_tools(state),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
        cwd=EMPTY_CWD,
        ask_state=state,
    )
    res = loop.run("buat web app", "sys")
    assert res.pending_question is None  # tidak pause — agent lanjut sendiri
    assert state.pending is None


def test_loop_budget_hard_stop():
    loop = AgentLoop(
        ScriptedClient(["tool:grep:x", "tool:grep:x", "tool:grep:x"]),
        _tools(),
        ContextManager(),
        TokenBudget(soft=10, hard=15),  # setiap step +15 → habis cepat
        cwd=EMPTY_CWD,
        cfg=LoopConfig(max_steps=10),
    )
    res = loop.run("cari", "sys")
    assert res.budget_exhausted


def test_loop_escalates_to_big_on_errors():
    small = ScriptedClient(["errtool", "errtool", "text:jawaban kecil"], name="small")
    big = ScriptedClient(["text:jawaban besar"], name="big")
    router = HybridRouter(big_client=big, small_client=small, cache=None)
    loop = AgentLoop(router, _tools(), ContextManager(), TokenBudget(soft=10**9, hard=10**9), cwd=EMPTY_CWD)
    res = loop.run("jalankan pytest lalu perbaiki", "sys")
    assert res.escalated
    assert res.final_text == "jawaban besar"


class TextToolClient(LLMClient):
    """Menjawab dengan blok ```tool (fallback / mode teks), lalu jawaban final."""

    def __init__(self):
        self.calls = 0
        self.last_messages = None

    def stream(self, messages, **kw):
        self.calls += 1
        self.last_messages = messages
        if self.calls == 1:
            yield StreamEvent(
                kind="delta",
                text='Saya cari dulu.\n```tool\n{"name": "grep", "arguments": {"q": "x"}}\n```',
            )
        else:
            yield StreamEvent(kind="delta", text="ketemu: line 1")
        yield StreamEvent(kind="done", usage=Usage(prompt_tokens=10, completion_tokens=5))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model="fake")

    def model_name(self):
        return "text-model"


def test_loop_text_mode_tool_fallback():
    """Mode teks: hasil tool dikirim sebagai pesan USER, tanpa tool_calls native —
    kompatibel dengan model yang menolak format native (mis. zen 400)."""
    client = TextToolClient()
    loop = AgentLoop(client, _tools(), ContextManager(), TokenBudget(soft=10**9, hard=10**9), cwd=EMPTY_CWD)
    res = loop.run("cari x", "sys")
    assert res.final_text == "ketemu: line 1"
    assert res.steps == 2
    roles = [m.role for m in client.last_messages]
    assert "tool" not in roles                      # tidak ada role:tool
    assert not any(m.tool_calls for m in client.last_messages)  # tidak ada tool_calls native
    assert any("[Hasil tool 'grep']" in m.content for m in client.last_messages if m.role == "user")


def test_build_question_escalates_even_with_chain_available():
    """Regresi utama: task MEMBANGUN yang diakhiri pertanyaan → jangan
    dianggap selesai; saat escalation chain tersedia, langsung naik model
    (sebelumnya jawaban pertanyaan semacam ini justru di-final-kan 'DONE')."""
    low = ScriptedClient(["text:Apakah lebih baik pakai stack A atau stack B dulu?"], name="low")
    high = ScriptedClient(["text:Oke, pakai Laravel Breeze dan langsung buat sekarang"], name="high")

    calls = []

    def factory(preset_name: str):
        calls.append(preset_name)
        return high

    loop = AgentLoop(
        client_or_router=low,
        tools=_tools(),
        ctx=ContextManager(),
        budget=TokenBudget(soft=10**9, hard=10**9),
        cwd=EMPTY_CWD,
        cfg=LoopConfig(
            quality_threshold=35,
            escalation_chain=["high"],
            max_escalations=1,
        ),
        client_factory=factory,
    )
    res = loop.run("buatkan login register", "sys")
    assert res.escalated_quality is True        # tidak dibekukan sebagai DONE
    assert calls == ["high"]                   # benar-benar pindah ke model kuat


class JunkTailClient(LLMClient):
    """Turn 1 emit tool-call indeks <tool_call>{0,1}; turn berikutnya DIAM (teks kosong)
    — model free yang 'macet di akhir'. Loop harus tetap memberi respons nyata."""

    def __init__(self):
        self.calls = 0
        self.last_messages = None

    def stream(self, messages, **kw):
        self.calls += 1
        self.last_messages = messages
        if self.calls == 1:
            yield StreamEvent(kind="delta", text=(
                '<tool_call>\n{0: "terminal", 1: {"command": "pwd"}}\n<tool_call>'
            ))
        else:
            yield StreamEvent(kind="delta", text="")
        yield StreamEvent(kind="done", usage=Usage(5, 5))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model="fake")

    def model_name(self):
        return "junk"


def test_loop_empty_tail_still_produces_response():
    """Regresi utama: bila model selesai tanpa kalimat penutup (kosong),
    dhybrid harus menyusun respons penutup — bukan 'DONE' tanpa output."""
    client = JunkTailClient()
    loop = AgentLoop(client, _tools(), ContextManager(), TokenBudget(soft=10**9, hard=10**9), cwd=EMPTY_CWD)
    res = loop.run("buatkan web login register", "sys")
    assert res.final_text and res.final_text.strip()
    assert "Pekerjaan selesai" in res.final_text  # disintesis dari jejak tool


def _tools_writer(cwd):
    from pathlib import Path

    reg = ToolRegistry()

    def _write(path):
        (Path(cwd) / path).write_text("x")
        return "ok"

    reg.register("write", "tulis file", {"path": {"type": "string"}}, _write)
    return reg


class WriterClient(LLMClient):
    """Tulis 2 file (step 0 & 1), lalu jawab final (step 2) — memicu live-verify."""

    def __init__(self):
        self.calls = 0

    def stream(self, messages, **kw):
        self.calls += 1
        if self.calls in (1, 2):
            yield StreamEvent(kind="tool_call", tool_call={
                "id": f"t{self.calls}", "name": "write",
                "arguments": {"path": f"f{self.calls}.py"},
            })
        else:
            yield StreamEvent(kind="delta", text="selesai")
        yield StreamEvent(kind="done", usage=Usage(5, 5))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model="fake")

    def model_name(self):
        return "writer"


def test_loop_live_verify_injects_file_evidence(tmp_path):
    """Live verifier harus BENAR-BENAR menyuntik evidence ke prompt model
    saat file baru terdeteksi (membuat agent sadar progres, bukan dead-code)."""
    client = WriterClient()
    loop = AgentLoop(client, _tools_writer(tmp_path), ContextManager(),
                     TokenBudget(soft=10 ** 9, hard=10 ** 9), cwd=str(tmp_path))
    res = loop.run("buatkan aplikasi", "sys")
    assert res.steps >= 3
    assert any(
        "[verifikasi]" in m.content and "file" in m.content
        for m in loop.ctx.messages
        if m.role == "user"
    )


class Flaky429Client(LLMClient):
    """Model yang raise HTTP 429 sebanyak fail_times, lalu menjawab normal."""

    def __init__(self, fail_times=1):
        self.fail_times = fail_times
        self.calls = 0

    def stream(self, messages, **kw):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("ConnectError/HTTPStatusError: 429 Too Many Requests")
        yield StreamEvent(kind="delta", text="Selesai ok.")
        yield StreamEvent(kind="done", usage=Usage(5, 5))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model="fake")

    def model_name(self):
        return "flaky"


def test_loop_retries_transient_429():
    """429 (sementara) tidak langsung DONE — retry model yang sama, lalu sukses."""
    c = Flaky429Client(fail_times=1)
    loop = AgentLoop(c, _tools(), ContextManager(), TokenBudget(soft=10 ** 9, hard=10 ** 9), cwd=EMPTY_CWD)
    res = loop.run("apa saja", "sys")
    assert c.calls == 2  # 1 gagal transient + 1 sukses
    assert res.final_text == "Selesai ok."


def test_loop_429_all_models_fails_friendly_message():
    """Kalaupun semua retry gagal tanpa fallback, DONE pakai pesan ramah —
    bukan stack mentah '429 Too Many Requests'."""
    c = Flaky429Client(fail_times=5)
    loop = AgentLoop(c, _tools(), ContextManager(), TokenBudget(soft=10 ** 9, hard=10 ** 9), cwd=EMPTY_CWD,
                     cfg=LoopConfig(max_steps=4, escalation_chain=[]))
    res = loop.run("untuk apa", "sys")
    assert "429" not in res.final_text
    assert "rate limit" in res.final_text.lower() or "model" in res.final_text.lower()


class QuestionClient(LLMClient):
    """Turn 1: balik bertanya; turn 2: langsung kerjakan."""

    def __init__(self):
        self.calls = 0
        self.last_messages = None

    def stream(self, messages, **kw):
        self.calls += 1
        self.last_messages = messages
        if self.calls == 1:
            yield StreamEvent(kind="delta", text="Mau pakai stack apa?")
        else:
            yield StreamEvent(kind="delta", text="Selesai: app.py dibuat dan diverifikasi")
        yield StreamEvent(kind="done", usage=Usage(prompt_tokens=5, completion_tokens=5))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model="fake")

    def model_name(self):
        return "q-model"


def test_loop_nudges_build_request_to_act():
    """User minta dibuatkan, model balik bertanya tanpa kerja → loop menyodok
    sekali agar langsung eksekusi, lalu lanjut."""
    client = QuestionClient()
    loop = AgentLoop(client, _tools(), ContextManager(), TokenBudget(soft=10**9, hard=10**9), cwd=EMPTY_CWD)
    res = loop.run("buatkan login register", "sys")
    assert client.calls == 2
    assert "app.py" in res.final_text
    assert any("DIBUATKAN" in m.content for m in client.last_messages if m.role == "user")


def test_loop_no_nudge_for_non_build_question():
    """Bukan permintaan membangun → pertanyaan dibiarkan apa adanya."""
    client = QuestionClient()
    loop = AgentLoop(client, _tools(), ContextManager(), TokenBudget(soft=10**9, hard=10**9), cwd=EMPTY_CWD)
    res = loop.run("jelaskan apa itu python", "sys")
    assert client.calls == 1
    assert res.final_text == "Mau pakai stack apa?"

def test_loop_nudge_build_question_is_bounded():
    """Build yang terus bertanya → disodok lebih gigih (max_nudges*2) tapi TETAP bounded,
    tidak loop tanpa batas, dan tidak pernah disangkakan 'selesai' saat masih bertanya."""

    class Stubborn(QuestionClient):
        def stream(self, messages, **kw):
            self.calls += 1
            self.last_messages = messages
            yield StreamEvent(kind="delta", text="Stack apa dulu?")
            yield StreamEvent(kind="done", usage=Usage(5, 5))

    s = Stubborn()
    loop = AgentLoop(s, _tools(), ContextManager(), TokenBudget(soft=10**9, hard=10**9), cwd=EMPTY_CWD)
    res = loop.run("buatkan aplikasi", "sys")
    # 1 jawaban asli + (max_nudges*2 = 6) nudge pilih-default, lalu berhenti
    assert s.calls == 1 + loop.cfg.max_nudges * 2
    assert res.final_text == "Stack apa dulu?"


class PromiseClient(LLMClient):
    """Turn 1: janji mau buat (tanpa eksekusi file); turn 2: jawab final."""

    def __init__(self):
        self.calls = 0
        self.last_messages = None

    def stream(self, messages, **kw):
        self.calls += 1
        self.last_messages = messages
        if self.calls == 1:
            yield StreamEvent(kind="delta", text="Saya akan buat dengan Node.js + Express.")
        else:
            yield StreamEvent(kind="delta", text="Selesai: app.js dibuat dan diverifikasi")
        yield StreamEvent(kind="done", usage=Usage(5, 5))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model="fake")

    def model_name(self):
        return "promise"


def test_loop_nudges_promise_to_execute():
    """Model cuma berjanji (tidak ada file dibuat) → disodok 'EKSEKUSI sekarang'."""
    client = PromiseClient()
    loop = AgentLoop(client, _tools(), ContextManager(), TokenBudget(soft=10**9, hard=10**9), cwd=EMPTY_CWD)
    res = loop.run("buatkan aplikasi login", "sys")
    assert client.calls == 2
    assert "app.js" in res.final_text
    assert any("EKSEKUSI SEKARANG" in m.content for m in client.last_messages if m.role == "user")


class SilentAfterToolClient(LLMClient):
    """Turn 1: pakai tool; turn 2: DIAM (jawaban kosong); turn 3: jawab."""

    def __init__(self):
        self.calls = 0

    def stream(self, messages, **kw):
        self.calls += 1
        if self.calls == 1:
            yield StreamEvent(kind="tool_call", tool_call={"id": "t1", "name": "grep", "arguments": {"q": "x"}})
        elif self.calls == 2:
            yield StreamEvent(kind="delta", text="")  # diam — tidak ada jawaban
        else:
            yield StreamEvent(kind="delta", text="Selesai: hasil ditemukan")
        yield StreamEvent(kind="done", usage=Usage(5, 5))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model="fake")

    def model_name(self):
        return "silent"


def test_loop_nudges_silent_model_to_answer():
    """Model pakai tool lalu diam (jawaban kosong) → loop menyodok 'beri jawaban'."""
    client = SilentAfterToolClient()
    loop = AgentLoop(client, _tools(), ContextManager(), TokenBudget(soft=10**9, hard=10**9), cwd=EMPTY_CWD)
    res = loop.run("cari x", "sys")
    assert client.calls == 3  # tool → diam(nudge) → jawab
    assert res.final_text == "Selesai: hasil ditemukan"


def test_loop_tool_errors_dont_loop_forever():
    loop = AgentLoop(
        ScriptedClient(["errtool", "errtool", "errtool", "text:akhir"]),
        _tools(),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
        cwd=EMPTY_CWD,
        cfg=LoopConfig(max_steps=4),
    )
    res = loop.run("x", "sys")
    assert res.steps <= 4

def test_quality_escalation_chain():
    """Model pertama jawab kosong (score=0) → escalate ke model kedua via chain."""
    # Model pertama: diam (jawaban kosong) → score 0 < threshold 35
    low_model = ScriptedClient([""], name="low")
    # Model kedua: jawab normal → score 50 >= 35, tidak escalate
    high_model = ScriptedClient(["ok"], name="high")

    factory_called = {"count": 0}
    def factory(preset_name: str):
        factory_called["count"] += 1
        return high_model

    loop = AgentLoop(
        low_model,
        _tools(),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
        cfg=LoopConfig(
            quality_threshold=35,
            escalation_chain=["preset-high"],
            max_escalations=1,
            max_nudges=1,
        ),
        cwd=EMPTY_CWD,
        client_factory=factory,
    )
    res = loop.run("jelaskan arsitektur sistem", "sys")
    assert res.escalated_quality
    assert factory_called["count"] == 1
    assert res.final_text.strip() == "ok"


def test_quality_rejects_disabled_preset_then_escalates():
    """Regresi: preset escalation yang factory-nya gagal (provider disabled /
    key kosong → return None) harus DILEWATI, lalu lanjut ke preset valid
    berikutnya. Dulu loop crash / berhenti / kena 401 di preset buruk."""
    low = ScriptedClient([""], name="low")   # skor 0 → trigger escalation
    high = ScriptedClient(["jawaban bagus"], name="high")

    calls = []

    def factory(preset_name: str):
        calls.append(preset_name)
        # preset pertama (mis. openrouter-big tanpa key) → None (disabled)
        if preset_name == "disabled-big":
            return None
        return high

    loop = AgentLoop(
        low,
        _tools(),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
        cfg=LoopConfig(
            quality_threshold=35,
            escalation_chain=["disabled-big", "good-big"],  # first gagal, second ok
            max_escalations=2,
        ),
        cwd=EMPTY_CWD,
        client_factory=factory,
    )
    res = loop.run("jelaskan sistem", "sys")
    # pertama diminta disabled-big → None → lanjut ke good-big → jalan
    assert "disabled-big" in calls
    assert calls[-1] == "good-big"
    assert res.escalated_quality
    assert res.final_text.strip() == "jawaban bagus"


def test_quality_no_escalation_when_passed():
    """Jika skor tinggi, tidak perlu escalate."""
    ok_model = ScriptedClient(["Jawaban baik dan lengkap"], name="ok")
    factory_called = {"count": 0}
    def factory(preset_name: str):
        factory_called["count"] += 1
        return ok_model

    loop = AgentLoop(
        ok_model,
        _tools(),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
        cfg=LoopConfig(
            quality_threshold=35,
            escalation_chain=["preset-high"],
            max_escalations=2,
        ),
        cwd=EMPTY_CWD,
        client_factory=factory,
    )
    res = loop.run("jelaskan arsitektur", "sys")
    assert not res.escalated_quality
    assert factory_called["count"] == 0
    assert res.quality_score >= 35
