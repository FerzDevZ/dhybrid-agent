"""Tests Session Branching & Merging (Fase 2.3) — copy-on-write, merge, tree."""
import pytest

from dhybrid.session.branching import (
    BranchingError,
    branch_tree,
    create_branch,
    merge_branch,
    path_of,
)
from dhybrid.session.store import SessionStore


@pytest.fixture
def store(tmp_path):
    return SessionStore(tmp_path / "s.sqlite")


def _seed(store, n: int, prefix: str = "m") -> str:
    sid = store.new_session(cwd="/proj")
    for i in range(1, n + 1):
        store.append_message(sid, "user", f"{prefix}{i}")
        store.append_message(sid, "assistant", f"jawaban {prefix}{i}")
    return sid


def test_create_branch_snapshots_parent(store):
    parent = _seed(store, 3)
    branch = create_branch(store, parent, "feature/auth")
    bp = store.get_session(branch)
    assert bp["parent_session_id"] == parent
    assert bp["branch_name"] == "feature/auth"
    # snapshot copy-on-write: semua pesan induk tersalin
    assert [m["content"] for m in store.all_messages(branch)] == [
        "m1", "jawaban m1", "m2", "jawaban m2", "m3", "jawaban m3",
    ]
    assert bp["fork_base_id"] == store.all_messages(branch)[-1]["id"]


def test_create_branch_requires_name(store):
    parent = _seed(store, 1)
    with pytest.raises(BranchingError):
        create_branch(store, parent, "  ")


def test_create_branch_duplicate_name_rejected(store):
    parent = _seed(store, 1)
    create_branch(store, parent, "dup")
    with pytest.raises(BranchingError):
        create_branch(store, parent, "dup")


def test_branch_writes_do_not_touch_parent(store):
    parent = _seed(store, 2)
    branch = create_branch(store, parent, "exp")
    # tulis pesan baru HANYA di branch
    store.append_message(branch, "user", "pesan eksperimen")
    parent_msgs = [m["content"] for m in store.all_messages(parent)]
    assert "pesan eksperimen" not in parent_msgs
    assert [m["content"] for m in store.all_messages(branch)][-1] == "pesan eksperimen"


def test_merge_returns_only_new_messages(store):
    parent = _seed(store, 2)
    branch = create_branch(store, parent, "fix")
    store.append_message(branch, "user", "baru di branch")
    store.append_message(branch, "assistant", "perbaikan selesai")
    merge_branch(store, branch)
    merged = [m["content"] for m in store.all_messages(parent)]
    # pesan lama tetap ada, pesan baru branch masuk ke ujung
    assert merged[:4] == ["m1", "jawaban m1", "m2", "jawaban m2"]
    assert merged[-2:] == ["baru di branch", "perbaikan selesai"]
    # branch dihapus setelah merge default
    assert store.get_session(branch) is None


def test_merge_keeps_branch_when_delete_false(store):
    parent = _seed(store, 1)
    branch = create_branch(store, parent, "keep")
    store.append_message(branch, "user", "x")
    merge_branch(store, branch, delete_branch=False)
    assert store.get_session(branch) is not None


def test_merge_to_explicit_target(store):
    main = _seed(store, 1)
    branch = create_branch(store, main, "b1")
    store.append_message(branch, "user", "dari b1")
    other = store.new_session(cwd="/lain")
    merge_branch(store, branch, target_sid=other)
    assert [m["content"] for m in store.all_messages(other)][-1] == "dari b1"


def test_merge_self_rejected(store):
    branch = create_branch(store, _seed(store, 1), "s")
    with pytest.raises(BranchingError):
        merge_branch(store, branch, target_sid=branch)


def test_branch_tree_structure(store):
    main = _seed(store, 1)
    b1 = create_branch(store, main, "feature/x")
    create_branch(store, main, "feature/y")
    create_branch(store, b1, "sub")
    tree = branch_tree(store, main)
    assert tree.id == main
    assert [c.branch_name for c in tree.children] == ["feature/x", "feature/y"]
    assert tree.children[0].children[0].branch_name == "sub"
    assert tree.children[1].children == []


def test_path_of_branch_to_root(store):
    main = store.new_session(cwd="/proj", title="main-session")
    store.append_message(main, "user", "m1")
    b1 = create_branch(store, main, "feature/auth")
    b2 = create_branch(store, b1, "hotfix")
    assert path_of(store, b2) == ["main-session", "feature/auth", "hotfix"]


def test_new_session_without_parent_is_main(store):
    sid = store.new_session(cwd="/x")
    s = store.get_session(sid)
    assert s["parent_session_id"] is None
    assert s["branch_name"] is None