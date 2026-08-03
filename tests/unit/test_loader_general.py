"""Test skill umum bawaan `general` — fallback auto-skill saat tak ada yang cocok."""

from dhybrid.dotenv import install_dir
from dhybrid.skills.loader import Skill, inject_skills, list_skills, select_skills


def test_general_skill_bundled():
    names = [s.name for s in list_skills(install_dir() / "skills")]
    assert "general" in names


def test_general_skill_has_description():
    skills = {s.name: s for s in list_skills(install_dir() / "skills")}
    sk = skills.get("general")
    assert sk is not None
    assert sk.description
    assert len(sk.body) >= 100


def _sk(name: str, desc: str) -> Skill:
    return Skill(name=name, description=desc, body=f"body {name}", path=None)


def test_select_skills_fallback_general():
    skills = [_sk("database", "sql query"), _sk("general", "panduan umum")]
    names = select_skills("buat web login", skills)
    assert names == ["general"]


def test_select_skills_no_fallback_when_disabled():
    skills = [_sk("database", "sql query"), _sk("general", "panduan umum")]
    names = select_skills("buat web login", skills, fallback=None)
    assert names == []


def test_select_skills_keeps_real_match_over_fallback():
    skills = [_sk("laravel-scaffold", "setup laravel auth web login"), _sk("general", "panduan umum")]
    names = select_skills("buat web login", skills)
    assert names == ["laravel-scaffold"]


def test_inject_skills_fallback_general():
    out = inject_skills("buat web login", [_sk("general", "panduan umum"), _sk("database", "sql query")])
    assert "[SKILL: general]" in out
    assert "body general" in out


def test_inject_skills_no_fallback_when_disabled():
    out = inject_skills(
        "buat web login",
        [_sk("general", "panduan umum")],
        fallback=None,
    )
    assert out == "buat web login"
