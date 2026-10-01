"""Config versioning (review finding M2/E2): old files must keep working."""

import json

import app.config as config


def _use_tmp(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", str(path))
    return path


def test_missing_file_gives_empty_dict(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    assert config.load_config() == {}


def test_v0_boolean_crlf_becomes_the_newline_option(monkeypatch, tmp_path):
    path = _use_tmp(monkeypatch, tmp_path)
    path.write_text(json.dumps({"crlf": True, "theme": "dark"}), encoding="utf-8")
    data = config.load_config()
    assert data["newline"] == "crlf"
    assert "crlf" not in data
    assert data["theme"] == "dark"          # untouched keys survive
    assert data["config_version"] == config.CONFIG_VERSION


def test_migration_is_idempotent(monkeypatch, tmp_path):
    path = _use_tmp(monkeypatch, tmp_path)
    path.write_text(json.dumps({"config_version": config.CONFIG_VERSION,
                                "newline": "lf"}), encoding="utf-8")
    once = config.load_config()
    twice = config.migrate_config(dict(once))
    assert once == twice


def test_save_merges_and_keeps_the_version(monkeypatch, tmp_path):
    path = _use_tmp(monkeypatch, tmp_path)
    config.save_config({"theme": "light"})
    config.save_config({"language": "en"})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["theme"] == "light" and data["language"] == "en"
    assert data["config_version"] == config.CONFIG_VERSION
