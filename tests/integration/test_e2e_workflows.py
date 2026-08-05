"""Integration tests for end-to-end workflow testing."""

import pytest

from dhybrid.config import Config
from dhybrid.session.context import SessionContext
from dhybrid.session.store import SessionStore
from dhybrid.tools import build_tools
from dhybrid.tools.registry import ToolRegistry


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_session_context_creation(self, tmp_path):
        """Test creating a session context with all components."""
        cfg = Config.load()
        cfg.workspace = tmp_path / ".dhybrid"
        
        ctx = SessionContext(
            cfg,
            SessionStore(tmp_path / "sessions.sqlite"),
            cwd=str(tmp_path),
        )
        
        assert ctx.cfg is not None
        assert ctx.store is not None
        assert ctx.tools is not None
        assert ctx.memory is not None
        assert ctx.system_prompt is not None
        # tool_count is initially empty, populated after tool execution
        assert isinstance(ctx.tools.tool_count, dict)
    
    def test_full_workflow_skill_creation(self, tmp_path):
        """Test complete workflow: task → tools → skill creation."""
        cfg = Config.load()
        cfg.workspace = tmp_path / ".dhybrid"
        cfg.skills = {"auto_learn": True}
        
        ctx = SessionContext(
            cfg,
            SessionStore(tmp_path / "sessions.sqlite"),
            cwd=str(tmp_path),
        )
        
        # Simulate a successful task
        from dhybrid.ui.repl import _auto_learn_skill
        
        class MockResult:
            files_created = 2
            tests_passed = True
            final_text = "Created login page with tests"
        
        ctx.skills = []
        ctx.tools = ToolRegistry()
        ctx.tools.tool_count = {"terminal": 3, "write_file": 2, "run_tests": 1}
        
        _auto_learn_skill(ctx, "buat login page", "Created login page", MockResult())
        
        # Verify skill was created
        skill_file = cfg.workspace / "skills" / "buat-login-page" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text()
        assert "buat-login-page" in content
    
    def test_tool_execution_pipeline(self, tmp_path):
        """Test executing multiple tools in sequence."""
        cfg = Config.load()
        cfg.workspace = tmp_path / ".dhybrid"
        
        # Build tools separately for testing
        reg = build_tools(cfg)
        
        # Test tools are registered
        assert "write_file" in reg._tools
        assert "read_file" in reg._tools
        
        # Execute write_file
        reg.execute("write_file", {"path": str(tmp_path / "test.txt"), "content": "hello world"})
        content = reg.execute("read_file", {"path": str(tmp_path / "test.txt")})
        assert "hello world" in content
    
    def test_multi_language_detection(self, tmp_path):
        """Test that multi-language tools are available."""
        cfg = Config.load()
        cfg.workspace = tmp_path / ".dhybrid"
        
        reg = build_tools(cfg)
        
        # Check tool names
        tool_names = list(reg._tools.keys())
        
        # Go tools
        assert "go_test" in tool_names
        assert "go_vet" in tool_names
        
        # Rust tools
        assert "cargo_test" in tool_names
        assert "cargo_build" in tool_names
        
        # TypeScript/Node tools
        assert "npm_test" in tool_names
        assert "tsc_check" in tool_names
        
        # Java tools
        assert "mvn_test" in tool_names
        assert "gradle_build" in tool_names
        
        # C# tools
        assert "dotnet_test" in tool_names
        assert "dotnet_build" in tool_names
    
    def test_skill_injection_workflow(self, tmp_path):
        """Test skill selection and injection pipeline."""
        from dhybrid.skills.loader import inject_skills, list_skills, select_skills
        
        # Create a test skill
        skill_dir = tmp_path / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill for integration
---
# test-skill

This is a test skill body.
""")
        
        skills = list_skills(tmp_path / "skills")
        assert len(skills) >= 1
        
        # Select skills - use keywords that match the skill
        selected = select_skills("test skill body integration", skills)
        assert "test-skill" in selected
        
        # Inject skills
        prompt = "Do something with test skill"
        injected = inject_skills(prompt, skills)
        assert "test-skill" in injected or "[SKILL:" in injected
    
    def test_memory_persistence(self, tmp_path):
        """Test memory persistence across sessions."""
        cfg = Config.load()
        cfg.workspace = tmp_path / ".dhybrid"
        
        ctx = SessionContext(
            cfg,
            SessionStore(tmp_path / "sessions.sqlite"),
            cwd=str(tmp_path),
        )
        
        # Set a memory
        ctx.memory.remember("test_key", "test_value")
        
        # Get the memory
        value = ctx.memory.recall("test_key")
        assert value == "test_value"
        
        # Create new context with same project
        ctx2 = SessionContext(
            cfg,
            SessionStore(tmp_path / "sessions.sqlite"),
            cwd=str(tmp_path),
        )
        
        # Memory should persist
        value2 = ctx2.memory.recall("test_key")
        assert value2 == "test_value"
    
    def test_episodic_memory_integration(self, tmp_path):
        """Test episodic memory integration."""
        try:
            from dhybrid.session.episodic_memory import (  # noqa: F401 — probe ketersediaan deps
                EpisodicMemory,
            )
            
            cfg = Config.load()
            cfg.workspace = tmp_path / ".dhybrid"
            
            ctx = SessionContext(
                cfg,
                SessionStore(tmp_path / "sessions.sqlite"),
                cwd=str(tmp_path),
            )
            
            # Test episodic memory functions
            _ = ctx.memory  # akses untuk memastikan tidak error
            
        except ImportError:
            pytest.skip("Episodic memory dependencies not available")
    
    def test_config_persistence(self, tmp_path):
        """Test configuration persistence."""
        from dhybrid.config import load_config, save_config
        
        cfg = Config.load()
        cfg.workspace = tmp_path / ".dhybrid"
        cfg.set("custom.setting", "test_value")
        cfg.set("model.temperature", 0.5)
        
        config_path = tmp_path / "config.yaml"
        save_config(cfg, config_path)
        
        # Load config
        loaded = load_config(config_path)
        assert loaded.get("custom.setting") == "test_value"
        assert loaded.get("model.temperature") == 0.5
    
    def test_marketplace_skill_flow(self, tmp_path):
        """Test full marketplace skill flow: export → import."""
        from dhybrid.skills.marketplace import (
            export_skill,
            import_skill,
            list_published_skills,
        )
        
        # Create source skill
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "export-test"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: export-test
description: Skill to export
---
# Export Test

This skill will be exported and imported.
""")
        
        # Export skill
        export_path = tmp_path / "exported.json"
        result = export_skill(str(skills_dir), "export-test", str(export_path))
        assert result is True
        assert export_path.exists()
        
        # Import to new location
        target_dir = tmp_path / "target-skills"
        target_dir.mkdir()
        result = import_skill(str(target_dir), str(export_path))
        assert result is True
        
        # Verify imported
        imported = list_published_skills(str(target_dir))
        names = [s["name"] for s in imported]
        assert "export-test" in names
    
    def test_skill_composition_workflow(self, tmp_path):
        """Test composing skills into workflows."""
        from dhybrid.skills.loader import Skill, compose_skills
        
        skill1 = Skill(
            name="setup",
            description="Setup project",
            body="Setup steps",
            path=tmp_path / "setup" / "SKILL.md",
        )
        skill2 = Skill(
            name="test",
            description="Run tests",
            body="Test steps",
            path=tmp_path / "test" / "SKILL.md",
        )
        skill3 = Skill(
            name="deploy",
            description="Deploy app",
            body="Deploy steps",
            path=tmp_path / "deploy" / "SKILL.md",
        )
        
        # Compose workflow
        workflow = compose_skills([skill1, skill2, skill3], "ci-workflow", "Complete CI workflow")
        
        assert workflow is not None
        assert workflow.name == "ci-workflow"
        assert "setup" in workflow.body
        assert "test" in workflow.body
        assert "deploy" in workflow.body
        assert "Sequential" in workflow.body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])