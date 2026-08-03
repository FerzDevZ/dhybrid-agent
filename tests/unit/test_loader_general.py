"""Test skill umum bawaan `general` — fallback auto-skill saat tak ada yang cocok."""

from dhybrid.dotenv import install_dir
from dhybrid.skills.loader import list_skills


def test_general_skill_bundled():
    names = [s.name for s in list_skills(install_dir() / "skills")]
    assert "general" in names


def test_general_skill_has_description():
    skills = {s.name: s for s in list_skills(install_dir() / "skills")}
    sk = skills.get("general")
    assert sk is not None
    assert sk.description
    assert len(sk.body) >= 100
