"""Session branching & merging (git-like) — Fase 2.3.

Branch = snapshot sesi induk (copy-on-write). Pesan baru yang ditulis DI BRANCH
tidak menyentuh induk; saat merge, hanya pesan baru branch (id > fork_base_id)
yang disalin kembali ke induk. Induk tetap utuh selama eksperimen berjalan.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BranchTree:
    """Representasi tree sesi utk UI (list --tree)."""
    id: str
    branch_name: str | None = None
    title: str = ""
    children: list[BranchTree] = field(default_factory=list)

    def print(self, prefix: str = "", name_only: bool = False) -> None:
        label = self.branch_name or "(main)"
        print(f"{prefix}• {label}" + ("" if name_only else f"  [{self.id}] — {self.title}"))
        for i, c in enumerate(self.children):
            last = i == len(self.children) - 1
            c.print(prefix + ("    " if last else "│   "), name_only)


class BranchingError(Exception):
    """Error operasi branch/merge."""


def create_branch(store, parent_sid: str, branch_name: str) -> str:
    """Buat branch dari `parent_sid` (snapshot copy-on-write). Return branch id.

    - Pesan induk di-copy ke branch (baseline).
    - `fork_base_id` merekam id pesan terakhir yang disalin → saat merge hanya
      pesan baru branch (id > fork_base_id) yang dikembalikan ke induk.
    """
    parent = store.get_session(parent_sid)
    if parent is None:
        raise BranchingError(f"sesi induk tidak ada: {parent_sid}")
    if not branch_name or not branch_name.strip():
        raise BranchingError("nama branch wajib diisi")
    if store.find_branch(parent_sid, branch_name):
        raise BranchingError(f"branch '{branch_name}' sudah ada di bawah sesi ini")

    branch_sid = store.new_session(
        title=(parent.get("title") or "untitled"),
        cwd=parent.get("cwd"),
        parent_session_id=parent_sid,
        branch_name=branch_name,
    )
    # snapshot copy-on-write pesan induk
    last_base = 0
    for m in store.all_messages(parent_sid):
        last_base = store.append_message(branch_sid, m["role"], m["content"] or "", m.get("tool_calls"))
    store.set_fork_base(branch_sid, last_base)
    # bawa ringkasan induk agar branch punya konteks awal yang sama
    store.set_summary(branch_sid, parent.get("summary") or "", parent.get("final_text") or "")
    return branch_sid


def merge_branch(
    store,
    branch_sid: str,
    target_sid: str | None = None,
    *,
    delete_branch: bool = True,
) -> str:
    """Gabungkan pesan baru dari branch ke sesi (default = induknya). Return target sid.

    - Pesan yang DITAMBAH di branch (id > fork_base_id) di-copy ke target.
    - Ringkasan target diperbarui dari branch bila branch punya ringkasan baru.
    - Opsional hapus branch setelah merge.
    """
    branch = store.get_session(branch_sid)
    if branch is None:
        raise BranchingError(f"branch tidak ada: {branch_sid}")
    target_sid = target_sid or branch.get("parent_session_id")
    if not target_sid:
        raise BranchingError("branch tidak punya induk — tentukan target_sid")
    if target_sid == branch_sid:
        raise BranchingError("tidak bisa merge branch ke dirinya sendiri")

    base = int(branch.get("fork_base_id") or 0)
    for m in store.all_messages(branch_sid):
        if int(m["id"]) <= base:
            continue  # sudah ada di induk (hasil fork)
        store.append_message(target_sid, m["role"], m["content"] or "", m.get("tool_calls"))

    # update ringkasan target dgn ringkasan branch (branch punya agregat terbaru)
    branch_summary = branch.get("summary") or ""
    branch_final = branch.get("final_text") or ""
    if branch_summary or branch_final:
        store.set_summary(target_sid, branch_summary, branch_final)

    if delete_branch:
        store.delete_session(branch_sid)
    return target_sid


def branch_tree(store, root_sid: str) -> BranchTree:
    """Bangun pohon branch dari `root_sid` (rekursif ke bawah)."""

    def _node(sid: str) -> BranchTree:
        s = store.get_session(sid) or {}
        node = BranchTree(id=sid, branch_name=s.get("branch_name"), title=s.get("title") or "")
        for b in store.branches_of(sid):
            node.children.append(_node(b["id"]))
        return node

    return _node(root_sid)


def path_of(store, sid: str) -> list[str]:
    """Jalur dari sesi ini ke root (main → branch → sub-branch)."""
    path: list[str] = []
    seen: set[str] = set()
    cur: str | None = sid
    while cur and cur not in seen:
        seen.add(cur)
        s = store.get_session(cur)
        if s is None:
            break
        path.append(s.get("branch_name") or s.get("title") or cur)
        cur = s.get("parent_session_id")
    return list(reversed(path))