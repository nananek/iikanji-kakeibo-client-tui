"""CLI のテスト"""

from __future__ import annotations

from click.testing import CliRunner

from iikanji_tui.cli import main
from iikanji_tui.config import Config, load_config, save_config


class TestWhoami:
    def test_unauthenticated_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        runner = CliRunner()
        result = runner.invoke(main, ["whoami"])
        assert result.exit_code != 0
        assert "未認証" in result.output

    def test_authenticated_shows_url_and_prefix(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_config(Config(
            api_url="https://example.tailnet.ts.net",
            access_token="ikt_abcdef" + "0" * 26,
        ))
        runner = CliRunner()
        result = runner.invoke(main, ["whoami"])
        assert result.exit_code == 0
        assert "example.tailnet.ts.net" in result.output
        assert "ikt_abcdef" in result.output


class TestLogout:
    def test_logout_removes_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_config(Config(api_url="https://x.com", access_token="ikt_x"))
        cfg_path = tmp_path / "iikanji" / "config.toml"
        assert cfg_path.exists()
        runner = CliRunner()
        result = runner.invoke(main, ["logout"])
        assert result.exit_code == 0
        assert not cfg_path.exists()

    def test_logout_when_not_logged_in(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        runner = CliRunner()
        result = runner.invoke(main, ["logout"])
        assert result.exit_code == 0


class TestSetAiConfig:
    """E2 PR-D-d: set-ai-config CLI コマンド。"""

    def test_openai_provider_saves(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        runner = CliRunner()
        result = runner.invoke(main, [
            "set-ai-config", "--provider", "openai",
            "--api-key", "sk-test123",
        ])
        assert result.exit_code == 0, result.output
        cfg = load_config()
        assert cfg.ai_provider == "openai"
        assert cfg.openai_api_key == "sk-test123"
        assert cfg.anthropic_api_key == ""
        assert cfg.google_api_key == ""

    def test_anthropic_provider_saves(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        runner = CliRunner()
        result = runner.invoke(main, [
            "set-ai-config", "--provider", "anthropic",
            "--api-key", "sk-ant-test",
        ])
        assert result.exit_code == 0
        cfg = load_config()
        assert cfg.ai_provider == "anthropic"
        assert cfg.anthropic_api_key == "sk-ant-test"
        assert cfg.openai_api_key == ""

    def test_invalid_provider_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        runner = CliRunner()
        result = runner.invoke(main, [
            "set-ai-config", "--provider", "evil",
            "--api-key", "x",
        ])
        # click.Choice で early reject
        assert result.exit_code != 0
        assert "openai" in result.output or "Invalid value" in result.output

    def test_preserves_other_provider_keys(self, tmp_path, monkeypatch):
        """openai キー設定済の状態で anthropic を追加しても openai は残る。"""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_config(Config(
            api_url="https://x.com", access_token="t",
            ai_provider="openai", openai_api_key="sk-existing",
        ))
        runner = CliRunner()
        result = runner.invoke(main, [
            "set-ai-config", "--provider", "anthropic",
            "--api-key", "sk-ant-new",
        ])
        assert result.exit_code == 0
        cfg = load_config()
        assert cfg.ai_provider == "anthropic"
        assert cfg.openai_api_key == "sk-existing"  # 既存維持
        assert cfg.anthropic_api_key == "sk-ant-new"


class TestClearAiConfig:
    def test_clear_resets_all_keys(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_config(Config(
            api_url="https://x.com", access_token="t",
            ai_provider="anthropic",
            openai_api_key="sk-1", anthropic_api_key="sk-2",
            google_api_key="sk-3",
        ))
        runner = CliRunner()
        result = runner.invoke(main, ["clear-ai-config", "--yes"])
        assert result.exit_code == 0
        cfg = load_config()
        assert cfg.ai_provider == "openai"
        assert cfg.openai_api_key == ""
        assert cfg.anthropic_api_key == ""
        assert cfg.google_api_key == ""
        # サーバ認証情報は維持
        assert cfg.api_url == "https://x.com"
        assert cfg.access_token == "t"


class TestWhoamiAi:
    """E2 PR-D-d: whoami が AI 設定状態も表示する。"""

    def test_shows_ai_unset(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_config(Config(
            api_url="https://x.com", access_token="ikt_xxxxxxxxxxxxxxx",
        ))
        runner = CliRunner()
        result = runner.invoke(main, ["whoami"])
        assert result.exit_code == 0
        assert "AI provider: openai" in result.output
        assert "AI key: 未設定" in result.output

    def test_shows_ai_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_config(Config(
            api_url="https://x.com", access_token="ikt_xxxxxxxxxxxxxxx",
            ai_provider="anthropic", anthropic_api_key="sk-ant",
        ))
        runner = CliRunner()
        result = runner.invoke(main, ["whoami"])
        assert result.exit_code == 0
        assert "AI provider: anthropic" in result.output
        assert "AI key: 設定済み" in result.output
