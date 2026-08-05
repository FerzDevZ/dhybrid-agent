"""Tests for auto-skill improvement from user feedback."""
from dhybrid.skills.loader import Skill
from dhybrid.ui.repl import (
    _auto_learn_skill,
    _should_update_skill,
)


def test_should_update_skill_when_new_richer():
    """Test that skill should update when new version is richer."""
    old = "1. pakai tool `write_file`"
    new = "1. pakai tool `terminal`\n2. pakai tool `write_file`\n3. pakai tool `run_tests`"
    assert _should_update_skill(old, new) is True


def test_should_not_update_when_old_richer():
    """Test that skill should not update when old version is richer."""
    old = "1. a\n2. b\n3. c"
    new = "1. a"
    assert _should_update_skill(old, new) is False


def test_auto_learn_skill_creates_new(tmp_path, monkeypatch):
    """Test auto-learning a new skill from successful session."""
    # Setup context
    from dhybrid.config import Config
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore
    from dhybrid.tools.registry import ToolRegistry
    
    # Create a config with workspace pointing to tmp_path
    cfg = Config.load()
    cfg.workspace = tmp_path / ".dhybrid"
    
    ctx = SessionContext(
        cfg,
        SessionStore(tmp_path / "sessions.sqlite"),
        cwd=str(tmp_path),
    )
    ctx.skills = []
    ctx.tools = ToolRegistry()
    ctx.tools.tool_count = {"terminal": 2, "write_file": 1, "run_tests": 1}
    
    class StubResult:
        files_created = 3
        tests_passed = True
        final_text = "Task completed successfully"
    
    _auto_learn_skill(ctx, "buat login", "done", StubResult())
    
    # Check skill was created in the configured workspace
    skill_file = cfg.workspace / "skills" / "buat-login" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text()
    assert "buat-login" in content
    assert "terminal" in content


def test_auto_skill_updates_when_richer(tmp_path, monkeypatch):
    """Test auto-skill updates existing skill when new version is richer."""
    from dhybrid.config import Config
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore
    from dhybrid.tools.registry import ToolRegistry
    
    # Create a config with workspace pointing to tmp_path
    cfg = Config.load()
    cfg.workspace = tmp_path / ".dhybrid"
    
    ctx = SessionContext(
        cfg,
        SessionStore(tmp_path / "sessions.sqlite"),
        cwd=str(tmp_path),
    )
    
    # Create existing skill
    skill_dir = cfg.workspace / "skills" / "buat-login"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("""---
name: buat-login
description: buat login — skill otomatis dari sesi nyata
---
# buat-login

**Langkah yang terbukti berhasil** (dari sesi nyata):
1. pakai tool `write_file`
""")
    
    ctx.skills = [Skill(
        name="buat-login",
        description="buat login — skill otomatis dari sesi nyata",
        body="""---
name: buat-login
description: buat login — skill otomatis dari sesi nyata
---
# buat-login

**Langkah yang terbukti berhasil** (dari sesi nyata):
1. pakai tool `write_file`
""",
        path=skill_dir / "SKILL.md",
    )]
    
    ctx.tools = ToolRegistry()
    ctx.tools.tool_count = {"terminal": 2, "write_file": 1, "run_tests": 1}
    
    class StubResult:
        files_created = 3
        tests_passed = True
        final_text = "Task completed successfully"
    
    from dhybrid.ui.repl import _auto_learn_skill
    _auto_learn_skill(ctx, "buat login", "done", StubResult())
    
    # Check skill was updated
    skill_file = cfg.workspace / "skills" / "buat-login" / "SKILL.md"
    content = skill_file.read_text()
    assert "diperbarui dari sesi nyata" in content
    assert "terminal" in content
    assert "run_tests" in content


def test_never_overwrite_manual_skill(tmp_path, monkeypatch):
    """Test that manual skills are never overwritten."""
    from dhybrid.config import Config
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore
    from dhybrid.tools.registry import ToolRegistry
    
    # Create a config with workspace pointing to tmp_path
    cfg = Config.load()
    cfg.workspace = tmp_path / ".dhybrid"
    
    ctx = SessionContext(
        cfg,
        SessionStore(tmp_path / "sessions.sqlite"),
        cwd=str(tmp_path),
    )
    
    # Create manual skill (no "skill otomatis dari sesi nyata" in description)
    skill_dir = cfg.workspace / "skills" / "buat-login"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("""---
name: buat-login
description: buat halaman login — skill buatan tangan user
---
# buat-login

**Langkah:**
1. tulis kode sendiri
2. jangan diubah agent
""")
    
    ctx.skills = [Skill(
        name="buat-login",
        description="buat halaman login — skill buatan tangan user",
        body="""---
name: buat-login
description: buat halaman login — skill buatan tangan user
---
# buat-login

**Langkah:**
1. tulis kode sendiri
2. jangan diubah agent
""",
        path=skill_dir / "SKILL.md",
    )]
    
    ctx.tools = ToolRegistry()
    ctx.tools.tool_count = {"terminal": 2, "write_file": 1, "run_tests": 1}
    
    class StubResult:
        files_created = 3
        tests_passed = True
        final_text = "Task completed successfully"
    
    from dhybrid.ui.repl import _auto_learn_skill
    _auto_learn_skill(ctx, "buat login", "done", StubResult())
    
    # Check skill was NOT overwritten
    skill_file = cfg.workspace / "skills" / "buat-login" / "SKILL.md"
    content = skill_file.read_text()
    assert "diperbarui dari sesi nyata" not in content
    assert "tulis kode sendiri" in content
    assert "jangan diubah agent" in content