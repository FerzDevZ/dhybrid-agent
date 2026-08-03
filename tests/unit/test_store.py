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


def test_memory_recent_returns_facts(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    assert mem.recent() == ""  # kosong
    mem.remember("a", "fakta satu")
    mem.remember("b", "fakta dua")
    out = mem.recent(limit=2)
    assert "fakta satu" in out and "fakta dua" in out
    assert "a:" in out and "b:" in out


def test_memory_digest_prioritizes_context_relevant(tmp_path):
    """digest(context) menaikkan fakta yang cocok dgn proyek/cwd, bukan hanya
    yang paling baru — supaya injeksi awal sesi relevan & hemat token."""
    mem = MemoryStore(tmp_path / "m.sqlite")
    mem.remember("deploy", "proyek dhybrid-agent di-deploy ke koyeb")
    mem.remember("sembarang", "catatan terbaru tanpa keyword proyek")
    out = mem.digest(context="/tmp/dhybrid-agent", limit=2)
    assert "dhybrid-agent" in out  # fakta relevan tetap muncul meski bukan yg terbaru
    # recent() tetap bekerja normal (ada kaitannya dgn digest)
    assert "sembarang" in mem.recent(limit=2)


def test_memory_digest_falls_back_to_recent_when_no_match(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    mem.remember("a", "fakta alfa")
    mem.remember("b", "fakta beta")
    out = mem.digest(context="xyzzy-absurd-tidak-ada-di-memory", limit=2)
    assert "fakta alfa" in out and "fakta beta" in out
    # konteks kosong / tidak relevan → tetap aman, tidak crash
    assert mem.digest(context="", limit=2) != ""
    assert mem.digest(context="!!! @@ 123 ::", limit=1) != ""  # token FTS dibersihkan


def test_session_cwd_and_last_session_for_cwd(tmp_path):
    store = SessionStore(tmp_path / "s.sqlite")
    assert store.last_session_for_cwd("/proyek/a") is None
    sa = store.new_session(cwd="/proyek/a")
    store.append_message(sa, "user", "hai")
    sb = store.new_session(cwd="/proyek/a")  # lebih baru
    # yang terakhir di cwd sama → sb
    assert store.last_session_for_cwd("/proyek/a") == sb
    assert store.last_session_for_cwd("/proyek/b") is None
    assert store.session_cwd(sa) == "/proyek/a"


def test_store_migrates_adding_cwd_column(tmp_path):
    """DB lama (tanpa kolom cwd) → migrasi otomatis menambah kolom cwd."""
    import sqlite3

    db = tmp_path / "old.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sessions (id TEXT, created TEXT, title TEXT, summary TEXT, final_text TEXT)")
    conn.commit()
    conn.close()

    store = SessionStore(db)  # harus tidak crash + cwd tersedia
    sid = store.new_session(cwd="/x")
    assert store.session_cwd(sid) == "/x"
