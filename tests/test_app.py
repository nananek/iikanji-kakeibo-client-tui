"""TUI アプリのスケルトンテスト"""

from __future__ import annotations

import pytest

from iikanji_tui.app import IikanjiTUI
from iikanji_tui.config import Config


def _status_text(app: IikanjiTUI) -> str:
    """status Static の中身を文字列で取り出す"""
    from textual.widgets import Static
    status = app.query_one("#status", Static)
    return str(status.render())


@pytest.mark.asyncio
async def test_app_starts_without_config():
    """未認証でも起動する"""
    app = IikanjiTUI(config=Config())
    async with app.run_test():
        assert app.title == "いいかんじ™家計簿"
        assert "未認証" in _status_text(app)


@pytest.mark.asyncio
async def test_app_starts_with_authenticated_config():
    config = Config(
        api_url="https://example.com",
        access_token="ikt_abcdefg" + "x" * 30,
    )
    app = IikanjiTUI(config=config)
    async with app.run_test():
        assert "認証済み" in _status_text(app)


@pytest.mark.asyncio
async def test_quit_keybind():
    app = IikanjiTUI(config=Config())
    async with app.run_test() as pilot:
        await pilot.press("q")
        # quit によりテストハーネスが正常終了する
