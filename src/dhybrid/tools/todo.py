"""Tool todo — daftar tugas in-memory per sesi (bantu agent tetap fokus)."""

from __future__ import annotations


def _make_todo():
    items: list[str] = []

    def todo_add(item: str) -> str:
        items.append(item)
        return f"OK: todo #{len(items)} ditambahkan"

    def todo_list() -> str:
        if not items:
            return "(todo kosong)"
        return "\n".join(f"{i + 1}. {t}" for i, t in enumerate(items))

    def todo_done(index: int) -> str:
        if not (1 <= index <= len(items)):
            return f"ERROR: index {index} di luar jangkauan (1-{len(items)})"
        done = items.pop(index - 1)
        return f"OK: selesai — {done}"

    def todo_clear() -> str:
        items.clear()
        return "OK: todo dikosongkan"

    return todo_add, todo_list, todo_done, todo_clear


def register(reg, max_chars: int = 8000) -> None:
    add, lst, done, clear = _make_todo()
    reg.register("todo_add", "Tambahkan item ke daftar tugas sesi.", {"item": {"type": "string"}}, add)
    reg.register("todo_list", "Tampilkan daftar tugas sesi.", {}, lst)
    reg.register("todo_done", "Tandai tugas selesai (index 1-based).", {"index": {"type": "integer"}}, done)
    reg.register("todo_clear", "Kosongkan daftar tugas.", {}, clear)
