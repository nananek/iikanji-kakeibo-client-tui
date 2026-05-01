"""AI 下書き画面のテスト"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from iikanji_tui.api import APIClient, APIError


def _draft_summary(id: int, suggestion_count: int = 3, **kw) -> dict:
    base = {
        "id": id, "status": "analyzed", "comment": "",
        "created_at": "2026-05-01T10:00:00",
        "summary": {
            "title": f"テスト{id}",
            "date": "2026-05-01",
            "description": "食費",
            "amount": 1234,
            "suggestion_count": suggestion_count,
        },
    }
    base.update(kw)
    return base


def _suggestion(account_codes: list[tuple[str, int, int]] | None = None,
                date: str = "2026-05-01",
                description: str = "食費") -> dict:
    if account_codes is None:
        account_codes = [
            ("5010", 1000, 0),
            ("1010", 0, 1000),
        ]
    return {
        "title": "AI 案",
        "date": date,
        "entry_description": description,
        "lines": [
            {"account_code": code, "debit_amount": d, "credit_amount": c,
             "description": ""}
            for code, d, c in account_codes
        ],
    }


def _make_app(drafts: list[dict]):
    from iikanji_tui.app import IikanjiTUI
    from iikanji_tui.config import Config

    api = MagicMock(spec=APIClient)
    api.list_journals.return_value = {
        "ok": True, "journals": [], "total": 0, "page": 1, "per_page": 50,
    }
    api.list_drafts.return_value = {"ok": True, "drafts": drafts}
    api.delete_draft.return_value = {"ok": True}
    api.create_journal.return_value = {
        "ok": True, "id": 99, "entry_number": 99,
    }
    config = Config(
        api_url="https://x", access_token="ikt_x" + "0" * 32,
    )
    return IikanjiTUI(config=config, api=api), api


class TestAIDraftsScreenLoad:
    @pytest.mark.asyncio
    async def test_loads_drafts_on_mount(self):
        from textual.widgets import DataTable

        from iikanji_tui.screens.ai_drafts import AIDraftsScreen
        app, api = _make_app([_draft_summary(1), _draft_summary(2)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_ai()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, AIDraftsScreen)
            api.list_drafts.assert_called()
            table = app.screen.query_one("#drafts", DataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_load_error_shown_in_status(self):
        from textual.widgets import Static

        from iikanji_tui.screens.ai_drafts import AIDraftsScreen
        app, api = _make_app([])
        api.list_drafts.side_effect = APIError(401, "認証失敗")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_ai()
            await pilot.pause()
            await pilot.pause()
            ai = app.screen
            assert isinstance(ai, AIDraftsScreen)
            assert "認証失敗" in str(ai.query_one("#status", Static).render())


class TestQuickAccept:
    @pytest.mark.asyncio
    async def test_quick_accept_uses_first_suggestion(self):
        app, api = _make_app([_draft_summary(7)])
        api.get_draft.return_value = {
            "ok": True,
            "draft": {
                "id": 7,
                "suggestions": [_suggestion(), _suggestion()],
            },
        }
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_ai()
            await pilot.pause()
            await pilot.pause()
            ai = app.screen
            ai.action_quick_accept()
            await pilot.pause()
            await pilot.pause()
            api.get_draft.assert_called_with(7)
            api.create_journal.assert_called_once()
            kwargs = api.create_journal.call_args.kwargs
            assert kwargs["draft_id"] == 7
            assert kwargs["source"] == "ai_receipt"
            assert kwargs["lines"][0]["account_code"] == "5010"

    @pytest.mark.asyncio
    async def test_quick_accept_with_no_drafts(self):
        from textual.widgets import Static
        app, api = _make_app([])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_ai()
            await pilot.pause()
            await pilot.pause()
            ai = app.screen
            ai.action_quick_accept()
            await pilot.pause()
            api.create_journal.assert_not_called()
            status = ai.query_one("#status", Static)
            assert "選択" in str(status.render())

    @pytest.mark.asyncio
    async def test_quick_accept_create_error(self):
        from textual.widgets import Static
        app, api = _make_app([_draft_summary(7)])
        api.get_draft.return_value = {
            "ok": True,
            "draft": {"id": 7, "suggestions": [_suggestion()]},
        }
        api.create_journal.side_effect = APIError(400, "確定済み期間")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_ai()
            await pilot.pause()
            await pilot.pause()
            ai = app.screen
            ai.action_quick_accept()
            await pilot.pause()
            await pilot.pause()
            assert "確定済み" in str(ai.query_one("#status", Static).render())


class TestDeleteDraft:
    @pytest.mark.asyncio
    async def test_delete_pushes_confirm(self):
        from iikanji_tui.screens.confirm import ConfirmScreen
        app, api = _make_app([_draft_summary(5)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_ai()
            await pilot.pause()
            await pilot.pause()
            ai = app.screen
            ai.action_delete_draft()
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)

    @pytest.mark.asyncio
    async def test_confirm_yes_calls_delete(self):
        app, api = _make_app([_draft_summary(5)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_ai()
            await pilot.pause()
            await pilot.pause()
            app.screen.action_delete_draft()
            await pilot.pause()
            app.screen.action_confirm()
            await pilot.pause()
            await pilot.pause()
            api.delete_draft.assert_called_with(5)


class TestUploadScreen:
    @pytest.mark.asyncio
    async def test_validates_file_path(self, tmp_path):
        from textual.widgets import Static

        from iikanji_tui.screens.upload import UploadScreen
        app, api = _make_app([])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = UploadScreen(api)
            await app.push_screen(screen)
            await pilot.pause()
            screen.action_submit()
            await pilot.pause()
            err = screen.query_one("#error", Static)
            assert "入力" in str(err.render()) or "見つかりません" in str(err.render())
            api.analyze_image.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_analyze_when_file_exists(self, tmp_path):
        from textual.widgets import Input

        from iikanji_tui.screens.upload import UploadScreen
        img = tmp_path / "receipt.jpg"
        img.write_bytes(b"fake")

        app, api = _make_app([])
        api.analyze_image.return_value = {
            "ok": True, "draft_id": 11, "suggestions": [],
        }
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = UploadScreen(api)
            await app.push_screen(screen)
            await pilot.pause()
            screen.query_one("#path", Input).value = str(img)
            await pilot.pause()
            screen.action_submit()
            await pilot.pause()
            await pilot.pause()
            api.analyze_image.assert_called_once()


class TestDetailScreen:
    @pytest.mark.asyncio
    async def test_loads_suggestions(self):
        from textual.widgets import DataTable, Static

        from iikanji_tui.screens.ai_detail import AIDraftDetailScreen
        app, api = _make_app([])
        api.get_draft.return_value = {
            "ok": True,
            "draft": {
                "id": 1,
                "suggestions": [_suggestion(), _suggestion(date="2026-05-02")],
            },
        }
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = AIDraftDetailScreen(api, draft_id=1)
            await app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            api.get_draft.assert_called_with(1)
            header = screen.query_one("#suggestion_header", Static)
            assert "1/2" in str(header.render())
            table = screen.query_one("#lines", DataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_next_suggestion_cycles(self):
        from textual.widgets import Static

        from iikanji_tui.screens.ai_detail import AIDraftDetailScreen
        app, api = _make_app([])
        api.get_draft.return_value = {
            "ok": True,
            "draft": {
                "id": 1,
                "suggestions": [
                    _suggestion(description="案A"),
                    _suggestion(description="案B"),
                ],
            },
        }
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = AIDraftDetailScreen(api, draft_id=1)
            await app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            screen.action_next_suggestion()
            await pilot.pause()
            header = screen.query_one("#suggestion_header", Static)
            assert "2/2" in str(header.render())
            screen.action_next_suggestion()
            await pilot.pause()
            assert "1/2" in str(header.render())

    @pytest.mark.asyncio
    async def test_accept_calls_create_with_draft_id(self):
        from iikanji_tui.screens.ai_detail import AIDraftDetailScreen
        app, api = _make_app([])
        api.get_draft.return_value = {
            "ok": True,
            "draft": {"id": 3, "suggestions": [_suggestion()]},
        }
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = AIDraftDetailScreen(api, draft_id=3)
            await app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            screen.action_accept()
            await pilot.pause()
            await pilot.pause()
            api.create_journal.assert_called_once()
            kwargs = api.create_journal.call_args.kwargs
            assert kwargs["draft_id"] == 3
            assert kwargs["source"] == "ai_receipt"
