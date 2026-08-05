"""Tests for semantic code search tool."""
from dhybrid.tools.semantic_search import SemanticSearch


def test_semantic_search_basic():
    ss = SemanticSearch()
    files = {
        "auth.py": "def login(user): return authenticate(user)",
        "user.py": "class User: pass",
        "api.py": "def get_user(id): return db.query(User).filter_by(id=id).first()",
    }
    ss.index(files)
    results = ss.search("authentication function")
    assert len(results) > 0
    # auth.py should be most relevant
    assert results[0][0] == "auth.py"


def test_semantic_search_empty():
    ss = SemanticSearch()
    results = ss.search("anything")
    assert results == []


def test_semantic_search_update():
    ss = SemanticSearch()
    ss.index({"a.py": "def foo(): pass"})
    ss.index({"b.py": "def bar(): pass"})
    results = ss.search("foo")
    assert len(results) == 2
    assert results[0][0] == "a.py"


def test_semantic_search_clear():
    ss = SemanticSearch()
    ss.index({"a.py": "def foo(): pass"})
    ss.clear()
    results = ss.search("foo")
    assert results == []


def test_semantic_search_remove():
    ss = SemanticSearch()
    ss.index({"a.py": "def foo(): pass", "b.py": "def bar(): pass"})
    ss.remove("a.py")
    results = ss.search("foo")
    # a.py should be removed, but semantic search may return b.py with low score
    # Check that a.py is not in results
    paths = [r[0] for r in results]
    assert "a.py" not in paths