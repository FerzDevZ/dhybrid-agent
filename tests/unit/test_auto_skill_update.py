"""Task 10: update skill lama yang terbukti lebih lengkap (hanya skill auto)."""
from dhybrid.skills.loader import Skill
from dhybrid.ui.repl import _auto_learn_skill, _should_update_skill


def test_update_when_new_richer():
    old = "1. pakai tool `write_file`"
    new = "1. pakai tool `terminal`\n2. pakai tool `write_file`\n3. pakai tool `run_tests`"
    assert _should_update_skill(old, new) is True


def test_no_update_when_old_richer():
    old = "1. a\n2. b\n3. c"
    new = "1. a"
    assert _should_update_skill(old, new) is False


def test_update_auto_skill_when_richer(tmp_path, monkeypatch):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    existing = Skill(
        name="buat-login",
        description="buat login — skill otomatis dari sesi nyata",
        body="**Langkah yang terbukti berhasil** (dari sesi nyata):\n\n1. pakai tool `write_file`",
        path=tmp_path / "x",
    )
    ctx.skills = [existing]
    ctx.tools.tool_count = {"terminal": 2, "write_file": 1, "run_tests": 1}
    result = _stub_result()
    result.files_created = 3
    _auto_learn_skill(ctx, "buat login", "done", result)
    target = ctx.workspace / "skills" / "buat-login" / "SKILL.md"
    assert target.exists()
    assert "diperbarui dari sesi nyata" in target.read_text()


def test_never_overwrite_manual_skill(tmp_path, monkeypatch):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    existing = Skill(
        name="buat-login",
        description="buat halaman login — skill buatan tangan user",
        body="**Langkah:**\n\n1. tulis kode sendiri\n2. jangan diubah agent",
        path=tmp_path / "x",
    )
    ctx.skills = [existing]
    ctx.tools.tool_count = {"terminal": 2, "write_file": 1, "run_tests": 1}
    result = _stub_result()
    result.files_created = 3
    _auto_learn_skill(ctx, "buat login", "done", result)
    assert not (ctx.workspace / "skills" / "buat-login" / "SKILL.md").exists()


from tests.unit.test_repl_clarify import _make_ctx, _stub_result
