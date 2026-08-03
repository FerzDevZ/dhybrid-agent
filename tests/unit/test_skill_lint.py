"""Task 13: lint skill — frontmatter rusak di-skip tanpa crash."""
from dhybrid.skills.loader import list_skills


def _write(tmp_path, name, text):
    d = tmp_path / name
    d.mkdir()
    (d / "SKILL.md").write_text(text)


def test_list_skills_skips_broken(tmp_path):
    _write(tmp_path, "good", "---\nname: good\ndescription: ok\n---\nbody")
    _write(tmp_path, "bad-name", "---\nname: [unclosed\n---\nrusak")
    _write(tmp_path, "no-frontmatter", "tidak ada frontmatter sama sekali")
    _write(tmp_path, "space-name", "---\nname: nama dengan spasi\ndescription: x\n---\nbody")
    skills = list_skills(tmp_path)
    names = [s.name for s in skills]
    assert "good" in names
    assert "bad-name" not in names
    assert "no-frontmatter" not in names
    assert "space-name" not in names
