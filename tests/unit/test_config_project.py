from pathlib import Path

import yaml

from dhybrid.config import Config, _apply_dict, load_project_config


def test_load_project_config_missing(tmp_path: Path):
    assert load_project_config(tmp_path) == {}


def test_load_project_config_parses(tmp_path: Path):
    d = tmp_path / ".dhybrid"
    d.mkdir()
    (d / "config.yaml").write_text(
        yaml.safe_dump({"model": {"model": "custom-model"}, "budget": {"soft": 1000, "hard": 2000}})
    )
    data = load_project_config(tmp_path)
    assert data["model"]["model"] == "custom-model"
    assert data["budget"]["soft"] == 1000


def test_apply_dict_overrides_fields(tmp_path: Path):
    cfg = Config()
    data = {
        "model": {"model": "proj-model", "temperature": 0.9},
        "budget": {"soft": 1, "hard": 2},
        "small_model": "proj-small",
        "tool": {"max_output_chars": 123},
    }
    _apply_dict(cfg, data)
    assert cfg.model.model == "proj-model"
    assert cfg.model.temperature == 0.9
    assert cfg.small_model == "proj-small"
    assert cfg.budget == {"soft": 1, "hard": 2}
    assert cfg.tool["max_output_chars"] == 123