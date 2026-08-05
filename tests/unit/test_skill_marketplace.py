"""Tests for skill marketplace (import/export skills)."""
import json

from dhybrid.skills.marketplace import (
    SkillPackage,
    export_skill,
    import_skill,
    list_published_skills,
)


def test_export_skill(tmp_path):
    """Test exporting a skill to a package file."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    
    # Create a test skill
    skill_dir = skills_dir / "test-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: test-skill
description: A test skill for export
---
# Test Skill

This is a test skill.
""")
    
    # Export the skill
    export_path = tmp_path / "test-skill.json"
    result = export_skill(str(skills_dir), "test-skill", str(export_path))
    
    assert result is True
    assert export_path.exists()
    
    # Verify package contents
    with open(export_path) as f:
        package = json.load(f)
    
    assert package["name"] == "test-skill"
    assert package["description"] == "A test skill for export"
    assert "body" in package
    assert "This is a test skill" in package["body"]


def test_import_skill(tmp_path):
    """Test importing a skill from a package file."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    
    # Create a skill package
    package = {
        "name": "imported-skill",
        "description": "An imported skill",
        "body": "# Imported Skill\n\nThis skill was imported.",
        "version": "1.0.0",
        "author": "test",
    }
    package_path = tmp_path / "imported-skill.json"
    with open(package_path, "w") as f:
        json.dump(package, f)
    
    # Import the skill
    result = import_skill(str(skills_dir), str(package_path))
    
    assert result is True
    
    # Verify skill was created
    imported_skill = skills_dir / "imported-skill" / "SKILL.md"
    assert imported_skill.exists()
    
    content = imported_skill.read_text()
    assert "imported-skill" in content
    assert "This skill was imported" in content


def test_import_skill_overwrite(tmp_path):
    """Test importing a skill with overwrite flag."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    
    # Create existing skill
    existing_dir = skills_dir / "existing-skill"
    existing_dir.mkdir()
    (existing_dir / "SKILL.md").write_text("""---
name: existing-skill
description: Original skill
---
# Original Skill

Old content.
""")
    
    # Create package with same name
    package = {
        "name": "existing-skill",
        "description": "Updated skill",
        "body": "# Updated Skill\n\nNew content.",
        "version": "2.0.0",
    }
    package_path = tmp_path / "existing-skill.json"
    with open(package_path, "w") as f:
        json.dump(package, f)
    
    # Import without overwrite should fail
    result = import_skill(str(skills_dir), str(package_path), overwrite=False)
    assert result is False
    
    # Import with overwrite should succeed
    result = import_skill(str(skills_dir), str(package_path), overwrite=True)
    assert result is True
    
    # Verify updated content
    updated = (skills_dir / "existing-skill" / "SKILL.md").read_text()
    assert "Updated Skill" in updated
    assert "New content" in updated


def test_list_published_skills(tmp_path):
    """Test listing published skills in a directory."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    
    # Create multiple skills
    for name in ["skill-a", "skill-b", "skill-c"]:
        skill_dir = skills_dir / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(f"""---
name: {name}
description: Description for {name}
---
# {name}

Content for {name}.
""")
    
    # List skills
    skills = list_published_skills(str(skills_dir))
    
    assert len(skills) == 3
    names = [s["name"] for s in skills]
    assert "skill-a" in names
    assert "skill-b" in names
    assert "skill-c" in names


def test_skill_package_dataclass():
    """Test SkillPackage dataclass."""
    pkg = SkillPackage(
        name="test-skill",
        description="A test skill",
        body="# Test Skill\n\nContent here.",
        version="1.0.0",
        author="test-author",
    )
    
    assert pkg.name == "test-skill"
    assert pkg.version == "1.0.0"
    
    # Test serialization
    data = pkg.to_dict()
    assert data["name"] == "test-skill"
    assert data["version"] == "1.0.0"
    
    # Test deserialization
    pkg2 = SkillPackage.from_dict(data)
    assert pkg2.name == pkg.name
    assert pkg2.version == pkg.version