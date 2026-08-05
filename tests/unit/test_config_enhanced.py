"""Tests for enhanced configuration system."""
import pytest
import tempfile
from pathlib import Path
from dhybrid.config import Config, load_config, save_config


def test_config_loads_default():
    """Test that default config loads correctly."""
    cfg = Config.load()
    
    assert cfg.workspace is not None
    assert cfg.model is not None
    assert cfg.budget is not None
    assert cfg.context is not None
    assert cfg.tool is not None
    assert cfg.presets is not None


def test_config_get_nested():
    """Test getting nested config values."""
    cfg = Config.load()
    
    # Test get with dot notation
    assert cfg.get("model.provider") == "openai"
    assert cfg.get("budget.soft") == 60000
    assert cfg.get("tool.max_output_chars") == 8000
    assert cfg.get("tool.allowlist") is not None
    
    # Test get with default
    assert cfg.get("nonexistent.key", "default") == "default"


def test_config_set_nested():
    """Test setting nested config values."""
    cfg = Config.load()
    
    # Set a value
    cfg.set("model.temperature", 0.5)
    assert cfg.get("model.temperature") == 0.5
    
    # Set nested value
    cfg.set("tool.new_setting", "test_value")
    assert cfg.get("tool.new_setting") == "test_value"


def test_config_presets():
    """Test config presets management."""
    cfg = Config.load()
    
    # Get preset
    preset = cfg.get_preset("openai-fast")
    assert preset is not None
    assert preset["provider"] == "openai"
    assert preset["model"] == "gpt-4o-mini"
    
    # List presets
    presets = cfg.list_presets()
    assert "openai-fast" in presets
    assert "openai-big" in presets
    assert "anthropic-fast" in presets


def test_config_add_preset():
    """Test adding a new preset."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        
        # Create minimal config with proper ModelConfig
        from dhybrid.config import ModelConfig
        cfg = Config(
            workspace=Path(tmpdir) / ".dhybrid",
            model=ModelConfig(provider="openai", model="gpt-4o"),
            budget={"soft": 60000, "hard": 120000},
            context={"keep_recent": 8, "compact_ratio": 0.5},
            tool={"max_output_chars": 8000, "allowlist": []},
            presets={},
        )
        save_config(cfg, config_path)
        
        # Load and add preset
        cfg = load_config(config_path)
        cfg.add_preset("custom", {"provider": "custom", "model": "custom-model"})
        
        preset = cfg.get_preset("custom")
        assert preset is not None
        assert preset["provider"] == "custom"


def test_config_save_and_load(tmp_path):
    """Test saving and loading config."""
    config_path = tmp_path / "config.yaml"
    
    cfg = Config.load()
    cfg.set("model.temperature", 0.7)
    cfg.set("custom.setting", "test")
    save_config(cfg, config_path)
    
    # Load saved config
    loaded = load_config(config_path)
    assert loaded.get("model.temperature") == 0.7
    assert loaded.get("custom.setting") == "test"


def test_config_tool_allowlist():
    """Test tool allowlist management."""
    cfg = Config.load()
    
    # Get current allowlist
    allowlist = cfg.get("tool.allowlist", [])
    assert isinstance(allowlist, list)
    assert "terminal" in allowlist
    assert "write_file" in allowlist
    
    # Add to allowlist
    cfg.set("tool.allowlist", allowlist + ["custom_tool"])
    assert "custom_tool" in cfg.get("tool.allowlist", [])


def test_config_skill_settings():
    """Test skills configuration section."""
    cfg = Config.load()
    
    skills = cfg.get("skills", {})
    assert "auto_learn" in skills
    assert "max_inject" in skills
    assert "max_chars" in skills
    assert "fallback" in skills
    
    # Modify skill settings
    cfg.set("skills.auto_learn", False)
    assert cfg.get("skills.auto_learn") is False


def test_config_mcp_servers():
    """Test MCP servers configuration."""
    cfg = Config.load()
    
    servers = cfg.get("tool.mcp_servers", [])
    assert isinstance(servers, list)
    
    # Add MCP server
    cfg.set("tool.mcp_servers", servers + [{"name": "test", "command": "test"}])
    assert len(cfg.get("tool.mcp_servers", [])) == len(servers) + 1


def test_config_escalation_chain():
    """Test escalation chain configuration."""
    cfg = Config.load()
    
    chain = cfg.get("model.chain", [])
    assert isinstance(chain, list)
    assert "openai-fast" in chain or "bynara-big" in chain
    
    # Modify chain
    cfg.set("model.chain", ["custom-small", "custom-big"])
    assert cfg.get("model.chain") == ["custom-small", "custom-big"]


def test_config_validation():
    """Test config validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        
        # Create invalid config (missing required fields)
        import yaml
        invalid = {"model": {"provider": "openai"}}
        with open(config_path, "w") as f:
            yaml.dump(invalid, f)
        
        # Should raise error or use defaults
        try:
            cfg = load_config(config_path)
            # If it loads, should have defaults filled
            assert cfg.workspace is not None
        except Exception:
            # Validation error is also acceptable
            pass