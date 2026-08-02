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

    assert auto_skill_worthwhile(["terminal"], "selesai") is True
    assert auto_skill_worthwhile([], "halo") is False          # sapaan tanpa tool
    assert auto_skill_worthwhile(["terminal"], "[error API] x") is False


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
