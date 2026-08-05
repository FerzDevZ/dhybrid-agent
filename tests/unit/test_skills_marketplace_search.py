"""Regresi BUG-03: `search_marketplace_skills` memanggil `search_skills` yang tidak di-import.

Sebelum fix, NameError ditelan oleh `except Exception` di loader.py sehingga
fungsi selalu return []. Dua hal yang diuji:
1. `search_skills` terdefinisi (ter-import) di namespace `loader`.
2. Pencarian marketplace sungguhan mengembalikan skill yang cocok.
"""
import dhybrid.skills.loader as L
from dhybrid.skills.loader import search_marketplace_skills


def test_search_skills_terdefinisi_di_loader():
    """F821: search_skills harus ada di namespace loader (RED sebelum fix)."""
    assert hasattr(L, "search_skills")


def test_search_marketplace_skills_kosong_return_list(tmp_path):
    """Direktori kosong -> list kosong, tanpa exception yang ditelan."""
    result = search_marketplace_skills("api", str(tmp_path))
    assert isinstance(result, list)
    assert result == []


def test_search_marketplace_skills_menemukan_skill(tmp_path):
    """Skill dengan keyword cocok harus muncul dalam hasil pencarian."""
    skill_dir = tmp_path / "baca-api"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: baca-api\ndescription: helper untuk membaca API restful\n---\n"
        "# Baca API\nkandungan\n",
        encoding="utf-8",
    )

    result = search_marketplace_skills("api", str(tmp_path))
    assert isinstance(result, list)
    assert any(s["name"] == "baca-api" for s in result)