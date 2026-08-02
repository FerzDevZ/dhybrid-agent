from dhybrid.tools.files import read_file, write_file
from dhybrid.tools.registry import ToolRegistry
from dhybrid.tools.terminal import is_dangerous, run_command


def test_register_execute_allowlist():
    reg = ToolRegistry(allowlist=["grep"])
    reg.register("grep", "cari", {"pattern": {"type": "string"}}, lambda pattern: f"hit:{pattern}")
    reg.register("rm", "hapus", {}, lambda: "deleted")
    assert reg.execute("grep", {"pattern": "x"}) == "hit:x"
    assert "tidak diizinkan" in reg.execute("rm", {})
    assert len(reg.specs()) == 1


def test_execute_error_handling():
    reg = ToolRegistry()

    def boom():
        raise ZeroDivisionError

    reg.register("boom", "b", {}, boom)
    assert "ZeroDivisionError" in reg.execute("boom", {})
    assert "tidak dikenal" in reg.execute("nope", {})


def test_run_command_ok():
    assert run_command("echo hello").strip() == "hello"


def test_run_command_error_and_cap():
    out = run_command("exit 3")
    assert "[exit 3]" in out
    capped = run_command("yes x | head -c 20000", max_chars=100)
    assert "truncated" in capped


def test_dangerous_patterns():
    assert is_dangerous("rm -rf /tmp/x")
    assert is_dangerous("git push --force origin main")
    assert not is_dangerous("git status")
    assert not is_dangerous("ls -la")


def test_read_write_roundtrip(tmp_path):
    f = tmp_path / "a.txt"
    write_file(str(f), "satu\ndua\ntiga")
    out = read_file(str(f), offset=2, limit=1)
    assert "2|dua" in out and "3 baris" in out


def test_read_missing():
    assert "tidak ada" in read_file("/nope/x.txt")


def test_grep_tool(tmp_path):
    (tmp_path / "x.py").write_text("def main():\n    pass\n")
    from dhybrid.tools.search import grep

    out = grep("def main", str(tmp_path))
    assert "x.py" in out


def test_todo_tools():
    from dhybrid.tools import todo

    reg = ToolRegistry()
    todo.register(reg)
    assert "OK" in reg.execute("todo_add", {"item": "fix bug"})
    assert "1. fix bug" in reg.execute("todo_list", {})
    assert "OK" in reg.execute("todo_done", {"index": 1})
    assert "(todo kosong)" in reg.execute("todo_list", {})
    assert "ERROR" in reg.execute("todo_done", {"index": 5})
