"""Tests for episodic memory with vector store."""
from dhybrid.session.episodic_memory import EpisodicMemory


def test_episodic_memory_stores_and_recalls(tmp_path):
    db_path = tmp_path / "episodic.sqlite"
    mem = EpisodicMemory(str(db_path))
    mem.remember("task_123", "Implemented JWT auth with RS256", tags=["auth", "jwt"])
    results = mem.recall("JWT authentication")
    assert len(results) == 1
    assert "RS256" in results[0]["content"]


def test_episodic_memory_tags(tmp_path):
    db_path = tmp_path / "episodic.sqlite"
    mem = EpisodicMemory(str(db_path))
    mem.remember("task_1", "Created user model", tags=["model", "user"])
    mem.remember("task_2", "Created auth service", tags=["service", "auth"])
    results = mem.recall("model", limit=5)
    assert len(results) >= 1
    assert any("user model" in r["content"] for r in results)


def test_episodic_memory_recent(tmp_path):
    db_path = tmp_path / "episodic.sqlite"
    mem = EpisodicMemory(str(db_path))
    mem.remember("task_1", "First task")
    mem.remember("task_2", "Second task")
    mem.remember("task_3", "Third task")
    recent = mem.get_recent(2)
    assert len(recent) == 2
    assert recent[0]["content"] == "Third task"


def test_episodic_memory_persistence(tmp_path):
    db_path = tmp_path / "episodic.sqlite"
    mem1 = EpisodicMemory(str(db_path))
    mem1.remember("task_1", "Persistent task")
    # New instance should see the data
    mem2 = EpisodicMemory(str(db_path))
    results = mem2.recall("Persistent")
    assert len(results) == 1


def test_episodic_memory_delete(tmp_path):
    db_path = tmp_path / "episodic.sqlite"
    mem = EpisodicMemory(str(db_path))
    mem.remember("task_1", "To delete")
    mem.forget("task_1")
    results = mem.recall("delete")
    assert len(results) == 0