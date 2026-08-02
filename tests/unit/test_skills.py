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
