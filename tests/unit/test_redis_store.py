"""TDD test RedisStore with SQLite fallback."""
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from dhybrid.session.store import RedisError, RedisStore


class TestRedisStore:
    """Test RedisStore layer with SQLite fallback."""

    def test_redis_store_init_without_redis(self):
        """RedisStore works even if redis not available - falls back to SQLite."""
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("dhybrid.session.store.REDIS_AVAILABLE", False):
            db_path = Path(tmpdir) / "test.sqlite"
            store = RedisStore(db_path=db_path)
            assert store.redis is None
            assert store.conn is not None

    def test_redis_store_save_load_checkpoint(self):
        """Save/load checkpoint via Redis when available."""
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("dhybrid.session.store.redis", return_value=Mock()) as mock_redis:
            mock_redis.return_value.set.return_value = True
            mock_redis.return_value.get.return_value = json.dumps({"run_count": 5, "fallback_uses": 2})
            db_path = Path(tmpdir) / "test.sqlite"
            store = RedisStore(db_path=db_path)
            store.redis = mock_redis.return_value

            store.save_checkpoint("sess123", {"run_count": 5, "fallback_uses": 2})
            state = store.load_checkpoint("sess123")

            assert state["run_count"] == 5
            assert state["fallback_uses"] == 2
            mock_redis.return_value.set.assert_called_once()
            mock_redis.return_value.get.assert_called_once_with("sess:sess123:state")

    def test_redis_store_fallback_to_sqlite(self):
        """When Redis fails, fall back to SQLite checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("dhybrid.session.store.redis", return_value=Mock()) as mock_redis:
            mock_redis.return_value.set.side_effect = RedisError("Redis connection refused")
            mock_redis.return_value.get.side_effect = RedisError("Redis connection refused")

            db_path = Path(tmpdir) / "test.sqlite"
            store = RedisStore(db_path=db_path)
            store.redis = mock_redis.return_value

            # Should not raise - falls back to SQLite
            store.save_checkpoint("sess123", {"run_count": 7})
            state = store.load_checkpoint("sess123")

            assert state["run_count"] == 7

    def test_redis_store_none_redis_uses_sqlite(self):
        """When RedisStore initialized with redis=None, uses SQLite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.sqlite"
            store = RedisStore(db_path=db_path, redis_client=None)
            assert store.redis is None
            
            store.save_checkpoint("sess1", {"x": 1})
            state = store.load_checkpoint("sess1")
            assert state["x"] == 1


def test_redis_store_persists_session_id():
    """new_session works with RedisStore."""
    with tempfile.TemporaryDirectory() as tmpdir, \
         patch("dhybrid.session.store.REDIS_AVAILABLE", False):
        db_path = Path(tmpdir) / "test.sqlite"
        store = RedisStore(db_path=db_path)
        sid = store.new_session("test session", "/home/user")
        assert len(sid) == 12
        
        session = store.get_session(sid)
        assert session["title"] == "test session"
        assert session["cwd"] == "/home/user"


def test_redis_fallback_graceful():
    """All operations gracefully fallback when Redis errors."""
    with tempfile.TemporaryDirectory() as tmpdir, \
         patch("dhybrid.session.store.redis", return_value=Mock()) as mock_redis:
        mock_redis.return_value.set.side_effect = RedisError("connection error")
        mock_redis.return_value.get.side_effect = RedisError("connection error")

        db_path = Path(tmpdir) / "test.sqlite"
        store = RedisStore(db_path=db_path)
        store.redis = mock_redis.return_value
        
        # None of these should raise
        store.save_checkpoint("s1", {"a": 1})
        # When Redis fails, it falls back to SQLite - data should be retrievable
        state = store.load_checkpoint("s1")
        assert state == {"a": 1}  # Falls back to SQLite correctly

        sid = store.new_session()
        assert sid is not None