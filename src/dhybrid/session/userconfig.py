"""User config — override pilihan user di ~/.dhybrid/config.yaml (persisten)."""

from __future__ import annotations

from pathlib import Path

import yaml


def user_config_path() -> Path:
    return Path.home() / ".dhybrid" / "config.yaml"


def load_user_config() -> dict:
    p = user_config_path()
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text()) or {}
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def save_model_choice(cfg) -> None:
    """Simpan pilihan model (terima ModelConfig atau dict) — persisten."""
    p = user_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = load_user_config()
    if hasattr(cfg, "provider"):
        m = {
            "provider": cfg.provider,
            "model": cfg.model,
            "base_url": cfg.base_url,
            "api_key_env": cfg.api_key_env,
        }
    else:
        m = cfg
    data["model"] = m
    p.write_text(yaml.safe_dump(data, sort_keys=False))


def save_small_model(name: str | None) -> None:
    """Simpan/ubah model kecil router (None = nonaktif)."""
    p = user_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = load_user_config()
    data["small_model"] = name
    p.write_text(yaml.safe_dump(data, sort_keys=False))


def get_disabled_skills() -> list[str]:
    """Skill yang dimatikan user (tersimpan di user config)."""
    data = load_user_config()
    return list((data.get("skills") or {}).get("disabled", []) or [])


def toggle_skill(name: str) -> tuple[bool, list[str]]:
    """Hidup/matikan skill. Return (enabled_now, daftar disabled)."""
    p = user_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = load_user_config()
    skills = data.setdefault("skills", {})
    disabled = list(skills.get("disabled", []) or [])
    if name in disabled:
        disabled.remove(name)
        enabled = True
    else:
        disabled.append(name)
        enabled = False
    skills["disabled"] = disabled
    data["skills"] = skills
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return enabled, disabled
