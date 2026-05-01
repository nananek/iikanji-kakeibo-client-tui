"""設定ファイル読み書きのテスト"""

from __future__ import annotations

import os

import pytest

from iikanji_tui.config import (
    Config, load_config, save_config, clear_config, default_config_path,
)


class TestConfig:
    def test_empty_is_not_authenticated(self):
        c = Config()
        assert c.is_authenticated() is False

    def test_is_authenticated_with_token_and_url(self):
        c = Config(api_url="https://x.com", access_token="ikt_aaa")
        assert c.is_authenticated() is True

    def test_url_only_not_authenticated(self):
        c = Config(api_url="https://x.com")
        assert c.is_authenticated() is False

    def test_token_only_not_authenticated(self):
        c = Config(access_token="ikt_aaa")
        assert c.is_authenticated() is False


class TestLoadSave:
    def test_load_missing_returns_empty(self, tmp_config_path):
        config = load_config(tmp_config_path)
        assert config == Config()

    def test_save_then_load_roundtrip(self, tmp_config_path):
        original = Config(
            api_url="https://example.tailnet.ts.net",
            access_token="ikt_secret",
            last_used_at="2026-05-01T10:00:00",
        )
        save_config(original, tmp_config_path)
        loaded = load_config(tmp_config_path)
        assert loaded == original

    def test_save_creates_parent_directory(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "config.toml"
        config = Config(api_url="https://x.com", access_token="ikt_x")
        save_config(config, deep)
        assert deep.exists()

    def test_save_skips_empty_fields(self, tmp_config_path):
        config = Config(api_url="https://x.com", access_token="ikt_x")
        save_config(config, tmp_config_path)
        text = tmp_config_path.read_text()
        assert "last_used_at" not in text

    def test_save_uses_secure_permissions(self, tmp_config_path):
        config = Config(api_url="https://x.com", access_token="ikt_x")
        save_config(config, tmp_config_path)
        mode = os.stat(tmp_config_path).st_mode & 0o777
        assert mode == 0o600

    def test_save_atomic_via_tmp(self, tmp_config_path):
        config = Config(api_url="https://x.com", access_token="ikt_x")
        save_config(config, tmp_config_path)
        # 一時ファイルが残っていない
        assert not tmp_config_path.with_suffix(".toml.tmp").exists()


class TestClear:
    def test_clear_removes_existing_file(self, tmp_config_path):
        save_config(Config(api_url="x", access_token="y"), tmp_config_path)
        assert tmp_config_path.exists()
        clear_config(tmp_config_path)
        assert not tmp_config_path.exists()

    def test_clear_missing_is_noop(self, tmp_config_path):
        clear_config(tmp_config_path)  # 例外を投げない
        assert not tmp_config_path.exists()


class TestDefaultPath:
    def test_uses_xdg_config_home(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        path = default_config_path()
        assert path == tmp_path / "iikanji" / "config.toml"

    def test_falls_back_to_home_config(self, monkeypatch, tmp_path):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        path = default_config_path()
        assert path == tmp_path / ".config" / "iikanji" / "config.toml"


class TestPartialFile:
    def test_load_partial_file(self, tmp_config_path):
        tmp_config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_config_path.write_text('api_url = "https://x.com"\n')
        config = load_config(tmp_config_path)
        assert config.api_url == "https://x.com"
        assert config.access_token == ""

    def test_load_ignores_unknown_keys(self, tmp_config_path):
        tmp_config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_config_path.write_text(
            'api_url = "https://x.com"\nsomething_unknown = "foo"\n'
        )
        config = load_config(tmp_config_path)
        assert config.api_url == "https://x.com"
