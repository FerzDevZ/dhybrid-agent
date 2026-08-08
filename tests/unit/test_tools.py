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


def test_spec_text_for_jit_subset():
    """JIT Tool Loading: hanya tool relevan yg di-render, core selalu ada."""
    reg = ToolRegistry()
    for name in (
        "terminal", "read_file", "write_file", "apply_patch", "grep", "ask_user",  # core
        "git_commit", "git_status",  # git
        "mvn_test", "mvn_build",  # java
        "pdf_ops",  # docs
    ):
        reg.register(name, f"tool {name}", {}, lambda: "ok")
    # tanpa keyword ekstra → hanya core
    core = reg.spec_text_for("halo")
    assert "git_commit" not in core and "mvn_test" not in core
    assert "read_file" in core and "terminal" in core
    # menyebut git → kelompok git ikut
    with_git = reg.spec_text_for("bagaimana commit branch ini")
    assert "git_commit" in with_git and "git_status" in with_git
    # menyebut mvn → kelompok java ikut, git tidak (subset terpisah)
    with_java = reg.spec_text_for("jalankan mvn build")
    assert "mvn_test" in with_java and "mvn_build" in with_java
    assert "git_commit" not in with_java


def test_jit_repo_scaffold_groups(tmp_path):
    """Regresi: repo_issue/repo_pr/scaffold dulu ORPHAN — terdaftar tapi tak
    pernah di-inject JIT (agent tidak pernah bisa memanggil). Pastikan keyword
    memicu grup repo & scaffold."""
    from pathlib import Path

    from dhybrid.config import Config
    from dhybrid.tools import build_tools

    cfg = Config.load("config/default.yaml")
    cfg.workspace = Path(tmp_path)
    reg = build_tools(cfg, client_factory=lambda: None, base_dir=str(tmp_path))

    t = reg.spec_text_for("tolong buatkan issue github untuk bug ini")
    assert "repo_issue" in t and "repo_pr" in t
    t2 = reg.spec_text_for("buat struktur proyek dari template")
    assert "scaffold" in t2
    # tanpa keyword: tidak ikut (hemat token)
    t3 = reg.spec_text_for("halo")
    assert "repo_issue" not in t3 and "scaffold" not in t3


def test_execute_error_handling():
    reg = ToolRegistry()

    def boom():
        raise ZeroDivisionError

    reg.register("boom", "b", {}, boom)
    assert "ZeroDivisionError" in reg.execute("boom", {})
    assert "tidak dikenal" in reg.execute("nope", {})


def test_browser_tool_register_contract():
    """Regresi: register() dulu menukar description & fn → tool browser selalu
    crash 'str() takes no keyword arguments'. Pastikan kontrak terpenuhi."""
    from dhybrid.tools import browser_tool

    reg = ToolRegistry(allowlist=None)
    browser_tool.register(reg)
    browser = reg.specs()[0]
    assert isinstance(browser["description"], str)
    # fn harus callable: eksekusi sampai (playwright belum terpasang di CI →
    # error wajar bertipe pesan playwright, BUKAN TypeError argumen).
    out = reg.execute("browser", {"action": "snapshot"})
    assert "str() takes no keyword" not in out
    assert "TypeError" not in out


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
