"""Model registry: resolve preset name / 'provider:model' -> ModelConfig."""

from __future__ import annotations

from dhybrid.config import Config, ModelConfig
from dhybrid.ui.commands import PROVIDERS, _load_provider_enabled


class ModelRegistry:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.presets: dict[str, dict] = cfg.presets or {}

    def resolve(self, name: str) -> ModelConfig:
        if name in self.presets:
            preset = self.presets[name]
            # Cek apakah provider enabled
            enabled = _load_provider_enabled()
            api_key_env = preset.get("api_key_env", "")
            for provider_name, env in PROVIDERS:
                if env == api_key_env:
                    if not enabled.get(provider_name, True):
                        raise KeyError(f"provider {provider_name} is disabled")
                    break
            return ModelConfig(**preset)
        if ":" in name:
            provider, model = name.split(":", 1)
            # Cek apakah provider enabled
            enabled = _load_provider_enabled()
            for provider_name, env in PROVIDERS:
                if env == f"{provider.upper()}_API_KEY" or env == f"OPENCODE_ZEN_API_KEY":
                    if not enabled.get(provider_name, True):
                        raise KeyError(f"provider {provider_name} is disabled")
                    break
            return ModelConfig(provider=provider, model=model)
        raise KeyError(f"unknown model preset: {name!r} (lihat config/default.yaml)")

    def names(self) -> list[str]:
        # Hanya return presets yang provider-nya enabled
        enabled = _load_provider_enabled()
        result = []
        for preset_name, preset in self.presets.items():
            api_key_env = preset.get("api_key_env", "")
            enabled_provider = True
            for prov_name, env in PROVIDERS:
                if env == api_key_env:
                    if not enabled.get(prov_name, True):
                        enabled_provider = False
                    break
            if enabled_provider:
                result.append(preset_name)
        return sorted(result)
