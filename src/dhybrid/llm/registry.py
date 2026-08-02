"""Model registry: resolve preset name / 'provider:model' -> ModelConfig."""

from __future__ import annotations

from dhybrid.config import Config, ModelConfig


class ModelRegistry:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.presets: dict[str, dict] = cfg.presets or {}

    def resolve(self, name: str) -> ModelConfig:
        if name in self.presets:
            return ModelConfig(**self.presets[name])
        if ":" in name:
            provider, model = name.split(":", 1)
            return ModelConfig(provider=provider, model=model)
        raise KeyError(f"unknown model preset: {name!r} (lihat config/default.yaml)")

    def names(self) -> list[str]:
        return sorted(self.presets.keys())
