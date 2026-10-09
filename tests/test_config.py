import json

import pytest

from akool_modelhub_cli.config import (
    DEFAULT_BASE_URL,
    read_config,
    resolve_config,
    validate_base_url,
    write_config,
)


def test_new_env_precedes_saved_config(monkeypatch, tmp_path):
    path = tmp_path / "modelhub" / "config.json"
    write_config({"api_key": "saved", "base_url": "https://saved.invalid/api/v1"}, path)
    monkeypatch.setenv("MODEL_HUB_API_KEY", "legacy")
    monkeypatch.setenv("MODEL_HUB_BASE_URL", "https://legacy.invalid/api/v1")
    monkeypatch.setenv("AKOOL_MODELHUB_API_KEY", "new")
    monkeypatch.setenv("AKOOL_MODELHUB_BASE_URL", "https://new.invalid/api/v1")
    result = resolve_config(path=path, base_url="https://explicit.invalid/api/v1")
    assert result.api_key == "new"
    assert result.base_url == "https://explicit.invalid/api/v1"
    assert "api_key=" not in repr(result)


def test_main_akool_config_is_not_modified(tmp_path):
    main = tmp_path / ".akool" / "config.json"
    main.parent.mkdir()
    main.write_text('{"client_secret":"other-product"}')
    local = main.parent / "modelhub" / "config.json"
    write_config({"api_key": "model-hub-key", "base_url": "https://example.invalid/api/v1"}, local)
    assert json.loads(main.read_text()) == {"client_secret": "other-product"}
    assert read_config(local)["api_key"] == "model-hub-key"


def test_config_symlink_is_rejected(tmp_path):
    target = tmp_path / "other.json"
    target.write_text("{}")
    link = tmp_path / "config.json"
    link.symlink_to(target)
    with pytest.raises(ValueError):
        write_config({"api_key": "secret"}, link)
    with pytest.raises(ValueError):
        read_config(link)
    assert target.read_text() == "{}"


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.example/api/v1",
        "https://key:secret@host/",
        "https://host/?key=secret",
        "file:///tmp",
        "https://host/#fragment",
    ],
)
def test_bad_api_roots_rejected(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_localhost_test_api_allowed():
    assert validate_base_url("http://127.0.0.1:1234/api/v1/") == "http://127.0.0.1:1234/api/v1"


def test_old_environment_names_are_not_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("AKOOL_MODELHUB_API_KEY", raising=False)
    monkeypatch.delenv("AKOOL_MODELHUB_BASE_URL", raising=False)
    monkeypatch.setenv("MODEL_HUB_API_KEY", "old-key")
    monkeypatch.setenv("MODEL_HUB_BASE_URL", "https://old.invalid/api/v1")
    with pytest.raises(ValueError, match="AKOOL_MODELHUB_API_KEY"):
        resolve_config(path=tmp_path / "missing" / "config.json")


def test_production_default_requires_only_the_modelhub_key(monkeypatch, tmp_path):
    monkeypatch.setenv("AKOOL_MODELHUB_API_KEY", "sk-test")
    monkeypatch.delenv("AKOOL_MODELHUB_BASE_URL", raising=False)
    result = resolve_config(path=tmp_path / "missing/config.json")
    assert result.base_url == "https://maas.akool.com/api/v1"
    assert DEFAULT_BASE_URL == "https://maas.akool.com"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://maas-fat.akool.io", "https://maas-fat.akool.io/api/v1"),
        ("https://maas-fat.akool.io/", "https://maas-fat.akool.io/api/v1"),
        ("https://maas-fat.akool.io/api/v1/", "https://maas-fat.akool.io/api/v1"),
        (
            "https://landing-fat.akool.io/interface/maas-backend",
            "https://landing-fat.akool.io/interface/maas-backend/api/v1",
        ),
        ("https://example.com/gateway/api/v1", "https://example.com/gateway/api/v1"),
        ("http://127.0.0.1:8080", "http://127.0.0.1:8080/api/v1"),
    ],
)
def test_base_url_normalizes_to_api_root_once(value, expected):
    assert validate_base_url(value) == expected
    assert validate_base_url(expected) == expected


def test_endpoint_url_is_not_a_base_url():
    with pytest.raises(ValueError, match="not an endpoint"):
        validate_base_url("https://maas-fat.akool.io/api/v1/client/models")


def test_saved_host_and_environment_gateway_both_normalize(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    write_config({"api_key": "sk-saved", "base_url": "https://maas-fat.akool.io"}, path)
    monkeypatch.delenv("AKOOL_MODELHUB_API_KEY", raising=False)
    monkeypatch.delenv("AKOOL_MODELHUB_BASE_URL", raising=False)
    assert resolve_config(path=path).base_url == "https://maas-fat.akool.io/api/v1"
    monkeypatch.setenv("AKOOL_MODELHUB_BASE_URL", "https://example.com/prefix")
    assert resolve_config(path=path).base_url == "https://example.com/prefix/api/v1"
