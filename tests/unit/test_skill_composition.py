"""Tests for skill composition (combine skills for complex workflows)."""
import pytest
from pathlib import Path
from dhybrid.skills.loader import (
    Skill,
    compose_skills,
    compose_skill_sequence,
    SkillComposition,
)


def test_compose_skills_basic():
    """Test composing multiple skills into a single workflow."""
    skill1 = Skill(
        name="setup-project",
        description="Setup project structure",
        body="""---
name: setup-project
description: Setup project structure
---
# setup-project

**Steps:**
1. Create project directories
2. Initialize git repo
3. Create basic config files
""",
        path=Path("/skills/setup-project/SKILL.md"),
    )
    
    skill2 = Skill(
        name="write-tests",
        description="Write unit tests",
        body="""---
name: write-tests
description: Write unit tests
---
# write-tests

**Steps:**
1. Create test directory
2. Write test cases
3. Run pytest
""",
        path=Path("/skills/write-tests/SKILL.md"),
    )
    
    skill3 = Skill(
        name="ci-setup",
        description="Setup CI/CD pipeline",
        body="""---
name: ci-setup
description: Setup CI/CD pipeline
---
# ci-setup

**Steps:**
1. Create GitHub Actions workflow
2. Add test stage
3. Add build stage
""",
        path=Path("/skills/ci-setup/SKILL.md"),
    )
    
    composed = compose_skills(
        [skill1, skill2, skill3],
        name="full-dev-workflow",
        description="Complete development workflow",
    )
    
    assert composed.name == "full-dev-workflow"
    assert "Complete development workflow" in composed.description
    assert "setup-project" in composed.body
    assert "write-tests" in composed.body
    assert "ci-setup" in composed.body
    assert "**setup-project**" in composed.body
    assert "**write-tests**" in composed.body
    assert "**ci-setup**" in composed.body
    assert "Execution order:** Sequential (1 → 2 → 3...)" in composed.body


def test_compose_skill_sequence():
    """Test composing skills as a sequence with dependencies."""
    skill1 = Skill(
        name="init-repo",
        description="Initialize git repository",
        body="Step 1: git init",
        path=Path("/skills/init-repo/SKILL.md"),
    )
    
    skill2 = Skill(
        name="add-remote",
        description="Add git remote",
        body="Step 2: git remote add origin ...",
        path=Path("/skills/add-remote/SKILL.md"),
    )
    
    skill3 = Skill(
        name="push-code",
        description="Push code to remote",
        body="Step 3: git push",
        path=Path("/skills/push-code/SKILL.md"),
    )
    
    composed = compose_skill_sequence(
        [skill1, skill2, skill3],
        name="git-push-workflow",
        description="Initialize and push to remote",
    )
    
    assert "git-push-workflow" in composed.name
    assert "Step 1" in composed.body
    assert "Step 2" in composed.body
    assert "Step 3" in composed.body


def test_skill_composition_dataclass():
    """Test SkillComposition dataclass."""
    comp = SkillComposition(
        name="test-composition",
        description="A test composition",
        skill_names=["skill-a", "skill-b", "skill-c"],
        composition_type="sequence",
        metadata={"version": "1.0"},
    )
    
    assert comp.name == "test-composition"
    assert comp.composition_type == "sequence"
    assert len(comp.skill_names) == 3
    assert comp.metadata["version"] == "1.0"
    
    # Test serialization
    data = comp.to_dict()
    assert data["name"] == "test-composition"
    assert data["skill_names"] == ["skill-a", "skill-b", "skill-c"]
    
    # Test deserialization
    comp2 = SkillComposition.from_dict(data)
    assert comp2.name == comp.name
    assert comp2.skill_names == comp.skill_names


def test_compose_skills_empty():
    """Test composing empty list returns None."""
    result = compose_skills([], name="empty")
    assert result is None


def test_compose_skills_single():
    """Test composing single skill returns it as-is."""
    skill = Skill(
        name="single-skill",
        description="Only skill",
        body="Just this skill",
        path=Path("/skills/single-skill/SKILL.md"),
    )
    
    composed = compose_skills([skill], name="single")
    
    assert composed is not None
    assert composed.name == "single"
    assert composed.description == "Only skill"
    assert composed.body == "Just this skill"