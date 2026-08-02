from dhybrid.session.memory import MemoryStore
from dhybrid.session.store import SessionStore


def test_session_roundtrip(tmp_path):
    store = SessionStore(tmp_path / "s.sqlite")
    sid = store.new_session("tes")
    store.append_message(sid, "user", "halo")
    store.append_message(sid, "assistant", "hai")
    store.record_usage(sid, "m", 10, 20, 5, 0.01)
    info = store.get_session(sid)
    assert info["title"] == "tes"
    assert store.last_messages(sid, n=1)[0]["content"] == "hai"
    u = store.usage(sid)
    assert u[0]["prompt"] == 10 and u[0]["cached"] == 5
    assert store.sessions()[0]["id"] == sid


def test_session_summary_and_delete(tmp_path):
    store = SessionStore(tmp_path / "s.sqlite")
    sid = store.new_session()
    store.set_summary(sid, "ringkas", "final")
    assert store.get_session(sid)["summary"] == "ringkas"
    store.delete_session(sid)
    assert store.get_session(sid) is None


def test_memory_roundtrip_and_fts(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    mem.remember("proyek", "dhybrid-agent pakai python 3.12")
    assert "dhybrid-agent" in mem.recall("proyek")
    hit = mem.search("python")
    assert "proyek" in hit
    mem.forget("proyek")
    assert "tidak ada" in mem.recall("proyek")
