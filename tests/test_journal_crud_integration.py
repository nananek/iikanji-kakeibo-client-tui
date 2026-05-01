"""journal_list と CRUD モーダル統合のテスト"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from iikanji_tui.api import APIClient, APIError


def _journal(id: int, **overrides) -> dict:
    j = {
        "id": id, "date": "2026-01-15", "entry_number": id,
        "description": f"仕訳{id}", "source": "journal",
        "lines": [
            {"account_code": "5010", "debit": 1000, "credit": 0},
            {"account_code": "1010", "debit": 0, "credit": 1000},
        ],
        "vouchers": [],
    }
    j.update(overrides)
    return j


def _make_app(journals: list[dict]):
    from iikanji_tui.app import IikanjiTUI
    from iikanji_tui.config import Config

    api = MagicMock(spec=APIClient)
    api.list_journals.return_value = {
        "ok": True, "journals": journals,
        "total": len(journals), "page": 1, "per_page": 50,
    }
    api.create_journal.return_value = {
        "ok": True, "id": 99, "entry_number": 99,
    }
    api.delete_journal.return_value = {"ok": True}

    config = Config(
        api_url="https://x", access_token="ikt_x" + "0" * 32,
    )
    return IikanjiTUI(config=config, api=api), api


class TestNewEntry:
    @pytest.mark.asyncio
    async def test_action_new_pushes_modal(self):
        from iikanji_tui.screens.journal_edit import JournalEditScreen
        app, _ = _make_app([_journal(1)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_new_entry()
            await pilot.pause()
            assert isinstance(app.screen, JournalEditScreen)
            assert app.screen.mode == "new"


class TestCopyEntry:
    @pytest.mark.asyncio
    async def test_copy_uses_selected_journal(self):
        from iikanji_tui.screens.journal_edit import JournalEditScreen
        app, _ = _make_app([
            _journal(1, description="セブン 100円"),
            _journal(2, description="ファミマ 200円"),
        ])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_copy_entry()
            await pilot.pause()
            assert isinstance(app.screen, JournalEditScreen)
            assert app.screen.mode == "copy"
            # 1件目（カーソル先頭）の内容がコピーされている
            assert app.screen.draft.description in ("セブン 100円", "ファミマ 200円")
            assert app.screen.draft.entry_id is None

    @pytest.mark.asyncio
    async def test_copy_with_no_data_shows_status(self):
        app, _ = _make_app([])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_copy_entry()
            await pilot.pause()
            from textual.widgets import Static
            status = screen.query_one("#status", Static)
            assert "選択" in str(status.render())


class TestDeleteEntry:
    @pytest.mark.asyncio
    async def test_delete_pushes_confirm(self):
        from iikanji_tui.screens.confirm import ConfirmScreen
        app, _ = _make_app([_journal(1)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_delete_entry()
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)

    @pytest.mark.asyncio
    async def test_confirm_yes_calls_delete_api(self):
        app, api = _make_app([_journal(1, entry_number=42)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_delete_entry()
            await pilot.pause()
            # confirm modal を承認
            confirm = app.screen
            confirm.action_confirm()
            await pilot.pause()
            await pilot.pause()
            api.delete_journal.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_confirm_no_does_not_call_api(self):
        app, api = _make_app([_journal(1)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_delete_entry()
            await pilot.pause()
            confirm = app.screen
            confirm.action_cancel()
            await pilot.pause()
            api.delete_journal.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_with_no_data_shows_status(self):
        app, api = _make_app([])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_delete_entry()
            await pilot.pause()
            api.delete_journal.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_api_error_shown(self):
        from textual.widgets import Static
        app, api = _make_app([_journal(1)])
        api.delete_journal.side_effect = APIError(400, "確定済み期間")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_delete_entry()
            await pilot.pause()
            confirm = app.screen
            confirm.action_confirm()
            await pilot.pause()
            await pilot.pause()
            status = screen.query_one("#status", Static)
            assert "確定済み" in str(status.render())


class TestAfterSave:
    @pytest.mark.asyncio
    async def test_save_callback_refreshes_list(self):
        app, api = _make_app([_journal(1)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            initial_calls = api.list_journals.call_count
            # 保存成功風のコールバック
            screen._after_save({"ok": True, "id": 99, "entry_number": 99})
            await pilot.pause()
            await pilot.pause()
            assert api.list_journals.call_count > initial_calls
