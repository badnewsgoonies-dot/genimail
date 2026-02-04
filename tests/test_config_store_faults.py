from genimail.infra import config_store


def test_config_load_invalid_json_sets_error(tmp_path, monkeypatch):
    config_dir = tmp_path / "email_config"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text("{invalid", encoding="utf-8")

    monkeypatch.setattr(config_store, "CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(config_store, "CONFIG_FILE", str(config_file))

    cfg = config_store.Config()

    assert cfg.load_error
    assert cfg.get("window_geometry") == "1100x700"


def test_config_load_non_object_sets_error(tmp_path, monkeypatch):
    config_dir = tmp_path / "email_config"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text('["not", "an", "object"]', encoding="utf-8")

    monkeypatch.setattr(config_store, "CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(config_store, "CONFIG_FILE", str(config_file))

    cfg = config_store.Config()

    assert cfg.load_error == "Config payload must be a JSON object."
