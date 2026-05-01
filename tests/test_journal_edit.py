"""仕訳編集モーダルのテスト"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from iikanji_tui.api import APIClient, APIError
from iikanji_tui.screens.journal_edit import (
    JournalDraft,
    JournalEditScreen,
    _parse_int,
)


class TestParseInt:
    def test_empty_returns_zero(self):
        assert _parse_int("") == 0
        assert _parse_int("   ") == 0

    def test_strips_commas(self):
        assert _parse_int("1,000") == 1000

    def test_invalid_returns_zero(self):
        assert _parse_int("abc") == 0


class TestJournalDraftEmpty:
    def test_default_today_date(self):
        d = JournalDraft.empty()
        assert d.date == date.today().isoformat()
        assert len(d.lines) == 2
        assert d.entry_id is None

    def test_custom_date(self):
        d = JournalDraft.empty(date(2026, 1, 15))
        assert d.date == "2026-01-15"


class TestJournalDraftFromJournal:
    def test_load_existing(self):
        journal = {
            "id": 42, "date": "2026-01-15", "entry_number": 5,
            "description": "食費",
            "lines": [
                {"account_code": "5010", "debit": 1000, "credit": 0,
                 "description": "食費"},
                {"account_code": "1010", "debit": 0, "credit": 1000,
                 "description": ""},
            ],
        }
        d = JournalDraft.from_journal(journal)
        assert d.date == "2026-01-15"
        assert d.description == "食費"
        assert d.entry_id == 42
        assert len(d.lines) == 2
        assert d.lines[0]["account_code"] == "5010"
        assert d.lines[0]["debit"] == 1000

    def test_copy_resets_id_and_date(self):
        journal = {
            "id": 42, "date": "2025-01-15",
            "description": "去年の仕訳",
            "lines": [
                {"account_code": "5010", "debit": 500, "credit": 0},
                {"account_code": "1010", "debit": 0, "credit": 500},
            ],
        }
        d = JournalDraft.from_journal(journal, copy=True)
        assert d.entry_id is None
        assert d.date == date.today().isoformat()
        assert d.description == "去年の仕訳"
        # 行はコピー
        assert d.lines[0]["account_code"] == "5010"


class TestJournalDraftBalance:
    def _draft(self, lines):
        return JournalDraft(
            date="2026-01-15", description="x", lines=lines,
        )

    def test_balanced(self):
        d = self._draft([
            {"account_code": "5010", "debit": 1000, "credit": 0},
            {"account_code": "1010", "debit": 0, "credit": 1000},
        ])
        assert d.is_balanced() is True
        assert d.total_debit() == 1000
        assert d.total_credit() == 1000

    def test_unbalanced(self):
        d = self._draft([
            {"account_code": "5010", "debit": 1000, "credit": 0},
            {"account_code": "1010", "debit": 0, "credit": 500},
        ])
        assert d.is_balanced() is False

    def test_zero_amount_not_balanced(self):
        d = self._draft([
            {"account_code": "5010", "debit": 0, "credit": 0},
            {"account_code": "1010", "debit": 0, "credit": 0},
        ])
        assert d.is_balanced() is False


class TestJournalDraftValidation:
    def _ok_draft(self):
        return JournalDraft(
            date="2026-01-15", description="食費",
            lines=[
                {"account_code": "5010", "debit": 1000, "credit": 0},
                {"account_code": "1010", "debit": 0, "credit": 1000},
            ],
        )

    def test_valid(self):
        assert self._ok_draft().validate() is None

    def test_missing_date(self):
        d = self._ok_draft()
        d.date = ""
        assert "日付" in d.validate()

    def test_invalid_date_format(self):
        d = self._ok_draft()
        d.date = "2026/01/15"
        assert "YYYY-MM-DD" in d.validate()

    def test_missing_description(self):
        d = self._ok_draft()
        d.description = "   "
        assert "摘要" in d.validate()

    def test_missing_account_code(self):
        d = self._ok_draft()
        d.lines[0]["account_code"] = ""
        # 空行扱いされて行数不足エラーになる
        err = d.validate()
        assert err is not None

    def test_both_debit_and_credit_in_one_line(self):
        d = JournalDraft(
            date="2026-01-15", description="x",
            lines=[
                {"account_code": "5010", "debit": 500, "credit": 500},
                {"account_code": "1010", "debit": 0, "credit": 1000},
            ],
        )
        err = d.validate()
        assert err is not None and "同時" in err

    def test_unbalanced_validation(self):
        d = self._ok_draft()
        d.lines[1]["credit"] = 500
        assert "貸借が一致" in d.validate()

    def test_only_one_non_empty_line(self):
        d = JournalDraft(
            date="2026-01-15", description="x",
            lines=[
                {"account_code": "5010", "debit": 1000, "credit": 0},
                {"account_code": "", "debit": 0, "credit": 0},
            ],
        )
        err = d.validate()
        assert err is not None
        assert "明細は最低2行" in err


class TestApiPayload:
    def test_filters_empty_lines(self):
        d = JournalDraft(
            date="2026-01-15", description="食費",
            lines=[
                {"account_code": "5010", "debit": 1000, "credit": 0},
                {"account_code": "1010", "debit": 0, "credit": 1000},
                {"account_code": "", "debit": 0, "credit": 0},
            ],
        )
        payload = d.to_api_payload()
        assert len(payload["lines"]) == 2

    def test_strips_description(self):
        d = JournalDraft(
            date="2026-01-15", description="  食費  ",
            lines=[
                {"account_code": "5010", "debit": 1000, "credit": 0},
                {"account_code": "1010", "debit": 0, "credit": 1000},
            ],
        )
        assert d.to_api_payload()["description"] == "食費"


class TestEditScreen:
    """Pilot で実際にモーダルを開いて挙動を確認"""

    def _api(self, response: dict | None = None,
             error: APIError | None = None):
        api = MagicMock(spec=APIClient)
        if error:
            api.create_journal.side_effect = error
        else:
            api.create_journal.return_value = response or {
                "ok": True, "id": 42, "entry_number": 1,
            }
        return api

    @pytest.mark.asyncio
    async def test_save_button_validates_balance(self):
        from iikanji_tui.app import IikanjiTUI
        from iikanji_tui.config import Config

        api = self._api()
        config = Config(
            api_url="https://x", access_token="ikt_x" + "0" * 32,
        )
        api.list_journals.return_value = {
            "ok": True, "journals": [], "total": 0,
        }
        app = IikanjiTUI(config=config, api=api)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            # 不一致なドラフトを直接設定
            draft = JournalDraft(
                date="2026-01-15", description="x",
                lines=[
                    {"account_code": "5010", "debit": 1000, "credit": 0},
                    {"account_code": "1010", "debit": 0, "credit": 500},
                ],
            )
            screen = JournalEditScreen(api, draft, mode="new")
            await app.push_screen(screen)
            await pilot.pause()
            screen.action_save()
            await pilot.pause()
            # API は呼ばれていない
            api.create_journal.assert_not_called()
            from textual.widgets import Static
            err = screen.query_one("#error", Static)
            assert "貸借" in str(err.render())

    @pytest.mark.asyncio
    async def test_save_calls_api_when_balanced(self):
        from iikanji_tui.app import IikanjiTUI
        from iikanji_tui.config import Config

        api = self._api()
        api.list_journals.return_value = {
            "ok": True, "journals": [], "total": 0,
        }
        config = Config(
            api_url="https://x", access_token="ikt_x" + "0" * 32,
        )
        app = IikanjiTUI(config=config, api=api)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            draft = JournalDraft(
                date="2026-01-15", description="食費",
                lines=[
                    {"account_code": "5010", "debit": 1000, "credit": 0},
                    {"account_code": "1010", "debit": 0, "credit": 1000},
                ],
            )
            screen = JournalEditScreen(api, draft, mode="new")
            await app.push_screen(screen)
            await pilot.pause()
            screen.action_save()
            await pilot.pause()
            api.create_journal.assert_called_once()
            kwargs = api.create_journal.call_args.kwargs
            assert kwargs["date"] == "2026-01-15"
            assert kwargs["description"] == "食費"
            assert len(kwargs["lines"]) == 2

    @pytest.mark.asyncio
    async def test_api_error_shown_in_error_field(self):
        from iikanji_tui.app import IikanjiTUI
        from iikanji_tui.config import Config

        api = self._api(error=APIError(400, "確定済み期間です"))
        api.list_journals.return_value = {
            "ok": True, "journals": [], "total": 0,
        }
        config = Config(
            api_url="https://x", access_token="ikt_x" + "0" * 32,
        )
        app = IikanjiTUI(config=config, api=api)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            draft = JournalDraft(
                date="2026-01-15", description="食費",
                lines=[
                    {"account_code": "5010", "debit": 1000, "credit": 0},
                    {"account_code": "1010", "debit": 0, "credit": 1000},
                ],
            )
            screen = JournalEditScreen(api, draft, mode="new")
            await app.push_screen(screen)
            await pilot.pause()
            screen.action_save()
            await pilot.pause()
            from textual.widgets import Static
            err = screen.query_one("#error", Static)
            assert "確定済み" in str(err.render())

    @pytest.mark.asyncio
    async def test_edit_mode_blocked(self):
        """編集モードはサーバー側 PUT が未対応なのでエラー表示"""
        from iikanji_tui.app import IikanjiTUI
        from iikanji_tui.config import Config

        api = self._api()
        api.list_journals.return_value = {
            "ok": True, "journals": [], "total": 0,
        }
        config = Config(
            api_url="https://x", access_token="ikt_x" + "0" * 32,
        )
        app = IikanjiTUI(config=config, api=api)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            draft = JournalDraft(
                date="2026-01-15", description="食費",
                lines=[
                    {"account_code": "5010", "debit": 1000, "credit": 0},
                    {"account_code": "1010", "debit": 0, "credit": 1000},
                ],
                entry_id=99,
            )
            screen = JournalEditScreen(api, draft, mode="edit")
            await app.push_screen(screen)
            await pilot.pause()
            screen.action_save()
            await pilot.pause()
            api.create_journal.assert_not_called()
            from textual.widgets import Static
            err = screen.query_one("#error", Static)
            assert "編集 API" in str(err.render())
