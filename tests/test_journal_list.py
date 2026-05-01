"""仕訳一覧スクリーンのテスト"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from iikanji_tui.api import APIClient, APIError
from iikanji_tui.screens.journal_list import (
    JournalListScreen, filter_journals, summarize_lines, PER_PAGE,
)


def _journal(id: int, date: str = "2026-01-15",
             description: str = "テスト",
             entry_number: int = 1,
             source: str = "journal",
             lines: list | None = None) -> dict:
    if lines is None:
        lines = [
            {"account_code": "5010", "debit": 1000, "credit": 0,
             "description": "食費"},
            {"account_code": "1010", "debit": 0, "credit": 1000,
             "description": "現金"},
        ]
    return {
        "id": id, "date": date, "entry_number": entry_number,
        "description": description, "source": source,
        "lines": lines, "vouchers": [],
    }


class TestSummarizeLines:
    def test_simple_two_line(self):
        debit, credit, total = summarize_lines([
            {"account_code": "5010", "debit": 1000, "credit": 0},
            {"account_code": "1010", "debit": 0, "credit": 1000},
        ])
        assert debit == "5010"
        assert credit == "1010"
        assert total == 1000

    def test_multi_debit(self):
        debit, credit, total = summarize_lines([
            {"account_code": "5010", "debit": 600, "credit": 0},
            {"account_code": "5020", "debit": 400, "credit": 0},
            {"account_code": "1010", "debit": 0, "credit": 1000},
        ])
        assert "他1件" in debit
        assert credit == "1010"
        assert total == 1000

    def test_empty(self):
        debit, credit, total = summarize_lines([])
        assert debit == ""
        assert credit == ""
        assert total == 0


class TestFilterJournals:
    def test_no_query_returns_all(self):
        items = [_journal(1), _journal(2)]
        assert filter_journals(items, "") == items

    def test_filter_by_description(self):
        items = [
            _journal(1, description="ファミマ"),
            _journal(2, description="セブン"),
        ]
        assert len(filter_journals(items, "ファミマ")) == 1

    def test_filter_by_account_code(self):
        items = [
            _journal(1, lines=[
                {"account_code": "5010", "debit": 100, "credit": 0},
                {"account_code": "1010", "debit": 0, "credit": 100},
            ]),
            _journal(2, lines=[
                {"account_code": "5020", "debit": 200, "credit": 0},
                {"account_code": "1010", "debit": 0, "credit": 200},
            ]),
        ]
        assert len(filter_journals(items, "5020")) == 1

    def test_case_insensitive(self):
        items = [_journal(1, description="Amazon")]
        assert len(filter_journals(items, "amazon")) == 1


class TestScreen:
    def _make_app(self, journals: list[dict], total: int | None = None):
        from iikanji_tui.app import IikanjiTUI
        from iikanji_tui.config import Config

        if total is None:
            total = len(journals)

        api = MagicMock(spec=APIClient)
        api.list_journals.return_value = {
            "ok": True, "journals": journals,
            "total": total, "page": 1, "per_page": PER_PAGE,
        }
        config = Config(
            api_url="https://example.com",
            access_token="ikt_xxx" + "0" * 30,
        )
        app = IikanjiTUI(config=config, api=api)
        return app, api

    @pytest.mark.asyncio
    async def test_loads_journals_on_mount(self):
        from textual.widgets import DataTable
        app, api = self._make_app([_journal(1), _journal(2)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            api.list_journals.assert_called()
            screen = app.screen
            table = screen.query_one("#journals", DataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_search_filters_rows(self):
        from textual.widgets import DataTable, Input
        app, _ = self._make_app([
            _journal(1, description="ファミマ"),
            _journal(2, description="セブン"),
        ])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            search = screen.query_one("#search", Input)
            search.value = "ファミマ"
            await pilot.pause()
            table = screen.query_one("#journals", DataTable)
            assert table.row_count == 1

    @pytest.mark.asyncio
    async def test_escape_clears_search(self):
        from textual.widgets import DataTable
        app, _ = self._make_app([
            _journal(1, description="ファミマ"),
            _journal(2, description="セブン"),
        ])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.search_query = "ファミマ"
            screen._render_rows()
            await pilot.pause()
            screen.action_clear_search()
            await pilot.pause()
            table = screen.query_one("#journals", DataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_refresh_calls_api_again(self):
        app, api = self._make_app([_journal(1)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            initial_calls = api.list_journals.call_count
            screen = app.screen
            screen.action_refresh()
            await pilot.pause()
            await pilot.pause()
            assert api.list_journals.call_count > initial_calls

    @pytest.mark.asyncio
    async def test_pagination_advances(self):
        # 100件あるので max_page = 2
        items = [_journal(i) for i in range(1, 51)]
        app, api = self._make_app(items, total=100)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert screen.page == 1
            screen.action_next_page()
            await pilot.pause()
            await pilot.pause()
            assert screen.page == 2
            # 2回目の API 呼び出しは page=2
            args = api.list_journals.call_args
            assert args.kwargs["page"] == 2

    @pytest.mark.asyncio
    async def test_pagination_does_not_exceed_max(self):
        app, api = self._make_app([_journal(1)], total=1)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_next_page()  # ノーオプ
            await pilot.pause()
            assert screen.page == 1

    @pytest.mark.asyncio
    async def test_prev_page_clamped_to_1(self):
        app, _ = self._make_app([_journal(1)])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            screen.action_prev_page()
            await pilot.pause()
            assert screen.page == 1

    @pytest.mark.asyncio
    async def test_api_error_displayed_in_status(self):
        from textual.widgets import Static
        from iikanji_tui.app import IikanjiTUI
        from iikanji_tui.config import Config

        api = MagicMock(spec=APIClient)
        api.list_journals.side_effect = APIError(401, "認証エラー")
        config = Config(
            api_url="https://example.com",
            access_token="ikt_xxx" + "0" * 30,
        )
        app = IikanjiTUI(config=config, api=api)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            status = app.screen.query_one("#status", Static)
            assert "認証エラー" in str(status.render())

    @pytest.mark.asyncio
    async def test_status_shows_total_and_page(self):
        from textual.widgets import Static
        items = [_journal(i) for i in range(1, 11)]
        app, _ = self._make_app(items, total=10)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            status = app.screen.query_one("#status", Static)
            text = str(status.render())
            assert "10" in text
            assert "ページ" in text
