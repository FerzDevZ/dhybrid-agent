from dhybrid.skills.loader import inject_skills, list_skills

TDD_SKILL = """---
name: tdd
description: TDD test-driven development, red-green-refactor, tulis test dulu
---

TDD: tulis test dulu (RED), implementasi minimal (GREEN), refactor.
"""


def test_list_skills(tmp_path):
    d = tmp_path / "skills"
    (d / "tdd").mkdir(parents=True)
    (d / "tdd" / "SKILL.md").write_text(TDD_SKILL)
    skills = list_skills(d)
    assert len(skills) == 1
    assert skills[0].name == "tdd"
    assert "TDD:" in skills[0].body


def test_inject_relevant_skill_only(tmp_path):
    d = tmp_path / "skills"
    (d / "tdd").mkdir(parents=True)
    (d / "tdd" / "SKILL.md").write_text(TDD_SKILL)
    (d / "gaming").mkdir(parents=True)
    (d / "gaming" / "SKILL.md").write_text(
        "---\nname: gaming\ndescription: tips bermain game\n---\nGaming tips\n"
    )
    skills = list_skills(d)
    out = inject_skills("bantu saya pakai TDD untuk fitur ini", skills)
    assert "[SKILL: tdd]" in out
    assert "Gaming tips" not in out


def test_inject_returns_prompt_when_no_match():
    skills = []
    out = inject_skills("hello", skills)
    assert out == "hello"


def test_slugify_from_prompt():
    from dhybrid.skills.loader import slugify

    assert slugify("tolong perbaiki bug di file calc.py") == "perbaiki-bug-file"
    assert slugify("haloo?") == "haloo"  # stopword 'tolong' dibuang; tetap ada kata
    assert slugify("yang dan di ke") == "task"  # semua stopword → fallback


def test_auto_skill_worthwhile():
    from dhybrid.skills.loader import auto_skill_worthwhile

    # aksi mengubah file → layak
    assert auto_skill_worthwhile(["terminal", "apply_patch"], {"terminal": 3, "apply_patch": 1}, "selesai") is True
    # sapaan tanpa tool → tidak
    assert auto_skill_worthwhile([], {}, "halo") is False
    # error → tidak
    assert auto_skill_worthwhile(["terminal"], {"terminal": 2}, "[error API] x") is False
    # eksplorasi saja (ls/grep/read, tanpa ubah file, < 4 pemakaian) → TIDAK jadi skill
    assert auto_skill_worthwhile(["terminal", "grep"], {"terminal": 1, "grep": 1}, "jawaban pertanyaan") is False
    # eksplorasi berat (>= 4 pemakaian) → layak
    assert auto_skill_worthwhile(["terminal", "grep"], {"terminal": 3, "grep": 2}, "hasil analisis") is True


def test_short_args_hides_content(tmp_path):
    """Indikator tool tidak boleh bocorkan isi write_file."""
    from dhybrid.ui.repl import _short_args

    out = _short_args({"path": "app.py", "content": "#!/usr/bin/env python3\n" + "x" * 500})
    assert "chars>" in out and "python3" not in out and "\n" not in out
    assert len(out) < 80


def test_slugify_fallback_generic():
    from dhybrid.skills.loader import slugify

    assert slugify("4") == "task"        # terlalu pendek → fallback generic
    assert slugify("123") == "123"       # numerik murni → skip di auto-learn (tanpa huruf)


def test_build_skill_md_compact_and_parsable(tmp_path):
    from dhybrid.skills.loader import build_skill_md, list_skills

    md = build_skill_md("fix-bug", "perbaiki bug", "perbaiki bug di calc", ["terminal", "patch"], "hasil ok", steps="1. pakai tool")
    (tmp_path / "fix-bug").mkdir()
    (tmp_path / "fix-bug" / "SKILL.md").write_text(md)
    skills = list_skills(tmp_path)
    assert skills[0].name == "fix-bug"
    assert len(md) < 600  # hemat token: skill otomatis harus ringkas


def test_skills_loaded_from_project_and_user_dirs(tmp_path):
    """SessionContext memuat skill proyek + skill user (~/.dhybrid/skills)."""
    from dhybrid.config import Config
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore

    proj = tmp_path / "proj"
    (proj / "skills" / "aaa").mkdir(parents=True)
    (proj / "skills" / "aaa" / "SKILL.md").write_text(
        "---\nname: aaa\ndescription: skill proyek aaa\n---\nAaa\n"
    )
    user_skills = tmp_path / "home" / ".dhybrid" / "skills"
    (user_skills / "bbb").mkdir(parents=True)
    (user_skills / "bbb" / "SKILL.md").write_text(
        "---\nname: bbb\ndescription: skill user bbb\n---\nBbb\n"
    )
    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path / "home" / ".dhybrid"
    ctx = SessionContext(cfg, SessionStore(tmp_path / "s.sqlite"), cwd=str(proj))
    names = {s.name for s in ctx.skills}
    assert "aaa" in names and "bbb" in names
    # skill BAWAAN (repo skills/) selalu tersedia di folder mana pun
    assert "tdd" in names and "debugging" in names and "lazy" in names


def test_disabled_skill_not_injected(tmp_path, monkeypatch):
    """Skill yang dimatikan user tidak ikut di-inject, tapi tetap terdaftar."""
    import dhybrid.session.userconfig as uc
    from dhybrid.config import Config
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore

    monkeypatch.setattr(uc, "user_config_path", lambda: tmp_path / "config.yaml")
    uc.toggle_skill("debugging")
    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path / ".dhybrid"
    ctx = SessionContext(cfg, SessionStore(tmp_path / "s.sqlite"), cwd=str(tmp_path))
    assert "debugging" not in {s.name for s in ctx.skills}       # tidak di-inject
    assert "debugging" in {s.name for s in ctx.all_skills}       # tetap terdaftar
    assert "debugging" in ctx.disabled_skills
