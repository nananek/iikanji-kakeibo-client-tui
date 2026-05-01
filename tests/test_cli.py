"""CLI のテスト"""

from __future__ import annotations

from click.testing import CliRunner

from iikanji_tui.cli import main
from iikanji_tui.config import Config, save_config


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
