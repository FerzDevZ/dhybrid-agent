from dhybrid.session import userconfig


def test_load_empty_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(userconfig, "user_config_path", lambda: tmp_path / "config.yaml")
    assert userconfig.load_user_config() == {}


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(userconfig, "user_config_path", lambda: tmp_path / "config.yaml")
    userconfig.save_model_choice({"provider": "openai", "model": "x-model", "base_url": None, "api_key_env": "K"})
    data = userconfig.load_user_config()
    assert data["model"]["model"] == "x-model"
    assert tmp_path.joinpath("config.yaml").exists()


def test_save_small_model(tmp_path, monkeypatch):
    monkeypatch.setattr(userconfig, "user_config_path", lambda: tmp_path / "config.yaml")
    userconfig.save_small_model("opencode-zen-fast")
    assert userconfig.load_user_config()["small_model"] == "opencode-zen-fast"
    userconfig.save_small_model(None)
    assert userconfig.load_user_config()["small_model"] is None


def test_invalid_yaml_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(userconfig, "user_config_path", lambda: tmp_path / "config.yaml")
    (tmp_path / "config.yaml").write_text("::: bukan yaml :::")
    assert userconfig.load_user_config() == {}
