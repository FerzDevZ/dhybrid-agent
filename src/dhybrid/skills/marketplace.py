"""Skill marketplace - import/export/share skills as packages."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SkillPackage:
    """Represents a packaged skill for sharing."""
    name: str
    description: str
    body: str
    version: str = "1.0.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillPackage:
        return cls(**data)


def export_skill(skills_dir: str, skill_name: str, output_path: str) -> bool:
    """Export a skill to a JSON package file.
    
    Args:
        skills_dir: Directory containing skills
        skill_name: Name of skill to export
        output_path: Path to output JSON file
    
    Returns:
        True if successful, False otherwise
    """
    skills_path = Path(skills_dir)
    skill_dir = skills_path / skill_name
    skill_file = skill_dir / "SKILL.md"
    
    if not skill_file.exists():
        return False
    
    try:
        content = skill_file.read_text(encoding="utf-8")
        
        # Parse frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                body = parts[2].strip()
            else:
                frontmatter = ""
                body = content
        else:
            frontmatter = ""
            body = content
        
        # Parse frontmatter fields
        name = skill_name
        description = ""
        for line in frontmatter.split("\n"):
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip('"')
        
        # Create package
        package = SkillPackage(
            name=name,
            description=description,
            body=body,
            version="1.0.0",
        )
        
        # Write package file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(package.to_dict(), indent=2, ensure_ascii=False))
        
        return True
    except Exception:
        logger.exception("export_skill gagal")
        return False


def import_skill(skills_dir: str, package_path: str, overwrite: bool = False) -> bool:
    """Import a skill from a JSON package file.
    
    Args:
        skills_dir: Directory to import skill into
        package_path: Path to skill package JSON file
        overwrite: Whether to overwrite existing skill
    
    Returns:
        True if successful, False otherwise
    """
    try:
        package_file = Path(package_path)
        if not package_file.exists():
            return False
        
        with open(package_file) as f:
            package_data = json.load(f)
        
        package = SkillPackage.from_dict(package_data)
        
        skills_path = Path(skills_dir)
        skill_dir = skills_path / package.name
        
        # Check if skill exists
        if skill_dir.exists() and not overwrite:
            return False
        
        # Create skill directory
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        # Write SKILL.md
        skill_file = skill_dir / "SKILL.md"
        frontmatter = f"""---
name: {package.name}
description: {package.description}
---
"""
        content = frontmatter + "\n" + package.body
        skill_file.write_text(content, encoding="utf-8")
        
        return True
    except Exception:
        logger.exception("import_skill gagal")
        return False


def list_published_skills(skills_dir: str) -> list[dict[str, str]]:
    """List all published skills in a directory.
    
    Args:
        skills_dir: Directory containing skills
    
    Returns:
        List of skill metadata dicts
    """
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return []
    
    skills = []
    for skill_dir in skills_path.iterdir():
        if not skill_dir.is_dir():
            continue
        
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        
        name = skill_dir.name
        try:
            content = skill_file.read_text(encoding="utf-8")
            description = ""
            
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 2:
                    frontmatter = parts[1]
                    for line in frontmatter.split("\n"):
                        if line.startswith("description:"):
                            description = line.split(":", 1)[1].strip().strip('"')
                            break
            
            skills.append({
                "name": name,
                "description": description,
            })
        except Exception as e:  # noqa: BLE001
            logger.warning("lewatkan skill rusak: %s (%s)", name, type(e).__name__)
            continue
    
    return skills


def search_skills(query: str, skills_dir: str) -> list[dict[str, str]]:
    """Search skills by query string.
    
    Args:
        query: Search query
        skills_dir: Directory containing skills
    
    Returns:
        List of matching skill metadata
    """
    all_skills = list_published_skills(skills_dir)
    query_lower = query.lower()
    
    matches = []
    for skill in all_skills:
        if (query_lower in skill["name"].lower() or 
            query_lower in skill["description"].lower()):
            matches.append(skill)
    
    return matches