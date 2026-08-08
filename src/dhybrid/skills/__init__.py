"""Skills package: loader, marketplace, and skill management."""

from __future__ import annotations

from dhybrid.skills.loader import (
    Skill,
    auto_skill_worthwhile,
    build_skill_md,
    inject_skills,
    install_skill,
    list_marketplace_skills,
    list_skills,
    # Marketplace functions
    publish_skill,
    search_marketplace_skills,
    select_skills,
    slugify,
)
from dhybrid.skills.marketplace import (
    SkillPackage,
    export_skill,
    import_skill,
    list_published_skills,
    search_skills,
)
from dhybrid.skills.plugin import (
    PluginRegistryError,
    RegisteredPlugin,
    SkillPlugin,
    SkillPluginRegistry,
    default_registry,
    discover_plugins,
    dskill,
)

__all__ = [
    "PluginRegistryError",
    "RegisteredPlugin",
    "Skill",
    "SkillPackage",
    "SkillPlugin",
    "SkillPluginRegistry",
    "auto_skill_worthwhile",
    "build_skill_md",
    "default_registry",
    "discover_plugins",
    "dskill",
    "export_skill",
    "import_skill",
    "inject_skills",
    "install_skill",
    "list_marketplace_skills",
    "list_published_skills",
    "list_skills",
    "publish_skill",
    "search_marketplace_skills",
    "search_skills",
    "select_skills",
    "slugify",
]