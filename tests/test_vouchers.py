"""証憑一覧スクリーンのテスト"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from iikanji_tui.api import APIClient, APIError


def _voucher(id: int, *, deadline_exceeded: bool = False,
             journal: dict | None = None,
             mime: str = "image/jpeg") -> dict:
    return {
        "id": id,
        "journal_entry_id": id,
        "image_mime": mime,
        "uploaded_at": "2026-05-01T10:00:00",
        "deadline_exceeded": deadline_exceeded,
        "journal": journal or {
            "date": "2026-04-15",
            "description": f"レシート{id}",
            "amount": 1000 + id,
        },
    }


def _make_app(vouchers: list[dict], **overrides):
    from iikanji_tui.app import IikanjiTUI
    from iikanji_tui.config import Config

    api = MagicMock(spec=APIClient)
    api.list_journals.return_value = {
        "ok": True, "journals": [], "total": 0, "page": 1, "per_page": 50,
    }
    api.list_vouchers.return_value = {
        "ok": True, "vouchers": vouchers,
        "total": len(vouchers), "page": 1, "per_page": 50,
    }
    api.verify_voucher.return_value = {"ok": True, "verified": True}
    api.get_voucher_image.return_value = b"fake-image-bytes"
    for k, v in overrides.items():
        setattr(api, k, v)
    config = Config(
        api_url="https://x", access_token="ikt_x" + "0" * 32,
    )
    return IikanjiTUI(config=config, api=api), api


class TestLoad:
    @pytest.mark.asyncio
    async def test_loads_on_mount(self):
        from iikanji_tui.screens.vouchers import VouchersScreen
        from textual.widgets import DataTable
        app, api = _make_app([_voucher(1), _voucher(2)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, VouchersScreen)
            api.list_vouchers.assert_called()
            table = app.screen.query_one("#vouchers", DataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_load_error_shown(self):
        from textual.widgets import Static
        app, api = _make_app([])
        api.list_vouchers.side_effect = APIError(401, "認証失敗")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            status = app.screen.query_one("#status", Static)
            assert "認証失敗" in str(status.render())


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_calls_api_with_query(self):
        from textual.widgets import Input
        app, api = _make_app([_voucher(1)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.query_one("#search", Input).value = "セブン"
            await pilot.pause()
            await pilot.pause()
            # API は search 引数付きで呼ばれた
            calls = [c for c in api.list_vouchers.call_args_list]
            assert any(c.kwargs.get("search") == "セブン" for c in calls)


class TestVerify:
    @pytest.mark.asyncio
    async def test_verify_success(self):
        from textual.widgets import Static
        app, api = _make_app([_voucher(1)])
        api.verify_voucher.return_value = {
            "ok": True, "verified": True,
        }
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_verify()
            await pilot.pause()
            api.verify_voucher.assert_called_with(1)
            status = screen.query_one("#status", Static)
            assert "改ざんなし" in str(status.render())

    @pytest.mark.asyncio
    async def test_verify_mismatch(self):
        from textual.widgets import Static
        app, api = _make_app([_voucher(1)])
        api.verify_voucher.return_value = {
            "ok": True, "verified": False,
        }
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            app.screen.action_verify()
            await pilot.pause()
            status = app.screen.query_one("#status", Static)
            assert "改ざん検出" in str(status.render())

    @pytest.mark.asyncio
    async def test_verify_with_no_selection(self):
        from textual.widgets import Static
        app, api = _make_app([])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            app.screen.action_verify()
            await pilot.pause()
            api.verify_voucher.assert_not_called()
            status = app.screen.query_one("#status", Static)
            assert "選択" in str(status.render())

    @pytest.mark.asyncio
    async def test_verify_api_error(self):
        from textual.widgets import Static
        app, api = _make_app([_voucher(1)])
        api.verify_voucher.side_effect = APIError(500, "内部エラー")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            app.screen.action_verify()
            await pilot.pause()
            status = app.screen.query_one("#status", Static)
            assert "内部エラー" in str(status.render())


class TestSave:
    @pytest.mark.asyncio
    async def test_save_writes_to_disk(self, tmp_path):
        from iikanji_tui.screens.vouchers import VouchersScreen
        app, api = _make_app([_voucher(1)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, VouchersScreen)
            screen.save_dir = str(tmp_path)
            screen.action_save()
            await pilot.pause()
            api.get_voucher_image.assert_called_with(1)
            saved = tmp_path / "voucher_1.jpg"
            assert saved.exists()
            assert saved.read_bytes() == b"fake-image-bytes"

    @pytest.mark.asyncio
    async def test_save_extension_from_mime(self, tmp_path):
        app, api = _make_app([_voucher(1, mime="image/png")])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            app.screen.save_dir = str(tmp_path)
            app.screen.action_save()
            await pilot.pause()
            assert (tmp_path / "voucher_1.png").exists()


class TestOpenExternal:
    @pytest.mark.asyncio
    async def test_open_calls_opener(self):
        from iikanji_tui.screens.vouchers import VouchersScreen
        opened = []
        def fake_opener(path):
            opened.append(path)
        app, api = _make_app([_voucher(1)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen._opener = fake_opener
            screen.action_open_external()
            await pilot.pause()
            assert len(opened) == 1
            assert opened[0].endswith(".jpg")


class TestPagination:
    @pytest.mark.asyncio
    async def test_next_page_advances(self):
        items = [_voucher(i) for i in range(1, 51)]
        app, api = _make_app(items)
        api.list_vouchers.return_value = {
            "ok": True, "vouchers": items,
            "total": 100, "page": 1, "per_page": 50,
        }
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_next_page()
            await pilot.pause()
            await pilot.pause()
            assert screen.page == 2
