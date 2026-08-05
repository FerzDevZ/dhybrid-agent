"""Konfigurasi dhybrid-agent: YAML + env override."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModelConfig:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    max_tokens: int = 4096
    temperature: float = 0.2
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    chain: list = field(default_factory=list)  # preset cadangan escalation kualitas

    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")

    def cost(self, prompt: int, completion: int) -> float:
        """Estimasi biaya USD dari token (harga per 1M token → per 1k = /1000)."""
        return (prompt / 1000 * self.cost_per_1k_input
                + completion / 1000 * self.cost_per_1k_output)


@dataclass
class Config:
    workspace: Path = field(default_factory=lambda: Path.home() / ".dhybrid")
    model: ModelConfig = field(default_factory=ModelConfig)
    small_model: str | None = None
    budget: dict = field(default_factory=lambda: {"soft": 60000, "hard": 120000})
    context: dict = field(default_factory=lambda: {"keep_recent": 8, "compact_ratio": 0.5})
    tool: dict = field(default_factory=lambda: {"max_output_chars": 8000, "allowlist": []})
    delegation: dict = field(default_factory=lambda: {"max_active": 3, "max_result_chars": 2000, "max_steps": 15})
    skills: dict = field(default_factory=lambda: {"dir": "skills", "max_inject": 3, "max_chars": 800, "fallback": "general"})
    clarify: dict = field(default_factory=lambda: {"enabled": True, "ai": True, "max_per_session": 3})
    presets: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)  # custom user settings

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        """Cari config: path eksplisit → cwd/config/default.yaml → config bawaan
        di direktori install (biar jalan dari folder mana pun)."""
        candidates: list[Path] = []
        if path:
            candidates.append(Path(path))
        else:
            candidates.append(Path("config/default.yaml"))
            candidates.append(Path(__file__).resolve().parents[2] / "config" / "default.yaml")
        cfg = cls()
        data: dict | None = None
        for cand in candidates:
            if cand.exists():
                data = yaml.safe_load(cand.read_text()) or {}
                break
        data = data or {}

        if "workspace" in data:
            cfg.workspace = Path(data["workspace"]).expanduser()

        if "model" in data and isinstance(data["model"], dict):
            for k, v in data["model"].items():
                if k == "small_model":
                    cfg.small_model = v
                elif hasattr(cfg.model, k):
                    setattr(cfg.model, k, v)

        for key in ("budget", "context", "tool", "delegation", "skills", "clarify"):
            if key in data and isinstance(data[key], dict):
                setattr(cfg, key, data[key])

        if "presets" in data and isinstance(data["presets"], dict):
            cfg.presets = data["presets"]
        
        if "extra" in data and isinstance(data["extra"], dict):
            cfg.extra = data["extra"]

        # user override (~/.dhybrid/config.yaml) — menimpa model bawaan (persisten)
        from dhybrid.session.userconfig import load_user_config
        user = load_user_config()
        if "model" in user and isinstance(user["model"], dict):
            for k, v in user["model"].items():
                if hasattr(cfg.model, k):
                    setattr(cfg.model, k, v)
        if "small_model" in user:
            cfg.small_model = user["small_model"]

        # env override: DHYBRID_MODEL, DHYBRID_PROVIDER, DHYBRID_BASE_URL, DHYBRID_SMALL_MODEL
        if os.environ.get("DHYBRID_MODEL"):
            cfg.model.model = os.environ["DHYBRID_MODEL"]
        if os.environ.get("DHYBRID_PROVIDER"):
            cfg.model.provider = os.environ["DHYBRID_PROVIDER"]
        if os.environ.get("DHYBRID_BASE_URL"):
            cfg.model.base_url = os.environ["DHYBRID_BASE_URL"]
        if os.environ.get("DHYBRID_SMALL_MODEL"):
            cfg.small_model = os.environ["DHYBRID_SMALL_MODEL"]
        return cfg

    def get(self, key: str, default=None):
        """Get nested config value using dot notation (e.g., 'model.provider')."""
        parts = key.split(".")
        obj = self
        for i, part in enumerate(parts):
            if isinstance(obj, dict):
                obj = obj.get(part, default)
            elif hasattr(obj, part):
                obj = getattr(obj, part)
            elif hasattr(self, "extra") and part in self.extra:
                # Check if it's a custom setting in extra
                obj = self.extra.get(part, default)
            else:
                return default
            if obj is None:
                return default
        return obj

    def set(self, key: str, value):
        """Set nested config value using dot notation (e.g., 'model.provider')."""
        parts = key.split(".")
        obj = self
        for part in parts[:-1]:
            if isinstance(obj, dict):
                if part not in obj:
                    obj[part] = {}
                obj = obj[part]
            elif hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                # For custom settings, store in extra
                if obj is self:
                    if "extra" not in obj.__dict__:
                        obj.extra = {}
                    if part not in obj.extra:
                        obj.extra[part] = {}
                    obj = obj.extra[part]
                else:
                    # Create nested dict if doesn't exist
                    new_obj = {}
                    if isinstance(obj, dict):
                        obj[part] = new_obj
                    else:
                        setattr(obj, part, new_obj)
                    obj = new_obj
        
        last = parts[-1]
        if isinstance(obj, dict):
            obj[last] = value
        elif obj is self:
            # Store custom settings in extra
            if "extra" not in obj.__dict__:
                obj.extra = {}
            obj.extra[last] = value
        elif hasattr(obj, last):
            setattr(obj, last, value)
        else:
            # Store in extra for custom settings
            if "extra" not in self.__dict__:
                self.extra = {}
            self.extra[last] = value

    def get_preset(self, name: str) -> dict | None:
        """Get a preset by name."""
        return self.presets.get(name)

    def list_presets(self) -> list[str]:
        """List all preset names."""
        return list(self.presets.keys())

    def add_preset(self, name: str, preset: dict):
        """Add or update a preset."""
        self.presets[name] = preset


def load_config(path: str | Path) -> Config:
    """Load config from a specific file path."""
    return Config.load(path)


def save_config(cfg: Config, path: str | Path):
    """Save config to a YAML file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert config to dict for saving
    data = {
        "workspace": str(cfg.workspace),
        "model": {
            "provider": cfg.model.provider,
            "model": cfg.model.model,
            "base_url": cfg.model.base_url,
            "api_key_env": cfg.model.api_key_env,
            "max_tokens": cfg.model.max_tokens,
            "temperature": cfg.model.temperature,
            "cost_per_1k_input": cfg.model.cost_per_1k_input,
            "cost_per_1k_output": cfg.model.cost_per_1k_output,
            "chain": cfg.model.chain,
        },
        "small_model": cfg.small_model,
        "budget": cfg.budget,
        "context": cfg.context,
        "tool": cfg.tool,
        "delegation": cfg.delegation,
        "skills": cfg.skills,
        "clarify": cfg.clarify,
        "presets": cfg.presets,
        "extra": cfg.extra,
    }
    
    import yaml
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
