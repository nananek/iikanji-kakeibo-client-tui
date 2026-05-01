"""仕訳一覧スクリーン

DataTable で /api/v1/journals の結果を表示する。
- ↑↓ で移動、Page Up/Down でページング
- / で検索、Esc でクリア
- f で日付範囲フィルタ
- r でリフレッシュ
"""

from __future__ import annotations

from datetime import date
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static

from iikanji_tui.api import APIClient, APIError


PER_PAGE = 50


def summarize_lines(lines: list[dict]) -> tuple[str, str, int]:
    """明細から (借方科目コード, 貸方科目コード, 金額) を要約する"""
    debit_codes = [
        l.get("account_code", "") for l in lines if (l.get("debit") or 0) > 0
    ]
    credit_codes = [
        l.get("account_code", "") for l in lines if (l.get("credit") or 0) > 0
    ]
    total = sum(int(l.get("debit") or 0) for l in lines)

    def _fmt(codes: list[str]) -> str:
        if not codes:
            return ""
        if len(codes) == 1:
            return codes[0]
        return f"{codes[0]} 他{len(codes) - 1}件"

    return _fmt(debit_codes), _fmt(credit_codes), total


def filter_journals(
    journals: list[dict], query: str
) -> list[dict]:
    """摘要・科目コードに対する部分一致フィルタ"""
    if not query:
        return journals
    q = query.lower()
    result = []
    for j in journals:
        haystack = [j.get("description", "")]
        for line in j.get("lines", []):
            haystack.append(line.get("account_code", ""))
            haystack.append(line.get("description", ""))
        if any(q in str(s).lower() for s in haystack):
            result.append(j)
    return result


class JournalListScreen(Screen):
    """仕訳一覧スクリーン"""

    BINDINGS = [
        Binding("r", "refresh", "更新"),
        Binding("slash", "focus_search", "検索"),
        Binding("escape", "clear_search", "クリア"),
        Binding("g", "first_page", "先頭"),
        Binding("G", "last_page", "末尾"),
        Binding("n", "next_page", "次"),
        Binding("p", "prev_page", "前"),
        Binding("q", "app.quit", "終了"),
    ]

    DEFAULT_CSS = """
    JournalListScreen {
        layout: vertical;
    }
    #search_bar {
        height: 3;
        padding: 0 1;
    }
    #status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    DataTable {
        height: 1fr;
    }
    """

    def __init__(self, api: APIClient, **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self.page = 1
        self.total = 0
        self.search_query = ""
        self.date_from: str | None = None
        self.date_to: str | None = None
        self._all_journals: list[dict] = []
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="search_bar"):
            yield Input(placeholder="検索（摘要・科目）", id="search")
        yield Static("", id="status")
        yield DataTable(id="journals", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#journals", DataTable)
        table.cursor_type = "row"
        table.add_columns(
            "日付", "伝票#", "摘要", "借方", "貸方", "金額", "ソース",
        )
        self.run_worker(self.load_page(), exclusive=True)

    async def load_page(self) -> None:
        """API から現ページの仕訳を取得して描画する"""
        if self._loading:
            return
        self._loading = True
        try:
            self._set_status("読み込み中...")
            try:
                payload = self._fetch_page()
            except APIError as e:
                self._set_status(f"エラー: {e.message}")
                return
            self.total = int(payload.get("total", 0))
            self._all_journals = payload.get("journals", [])
            self._render_rows()
            self._update_status()
        finally:
            self._loading = False

    def _fetch_page(self) -> dict:
        """同期 API 呼び出し（テストでオーバーライド可能）"""
        return self.api.list_journals(
            page=self.page, per_page=PER_PAGE,
            date_from=self.date_from, date_to=self.date_to,
        )

    def _render_rows(self) -> None:
        table = self.query_one("#journals", DataTable)
        table.clear()
        rows = filter_journals(self._all_journals, self.search_query)
        for j in rows:
            debit, credit, amount = summarize_lines(j.get("lines", []))
            table.add_row(
                j.get("date", ""),
                str(j.get("entry_number", "")),
                j.get("description", "") or "",
                debit, credit,
                f"¥{amount:,}",
                j.get("source", ""),
                key=str(j.get("id")),
            )

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def _update_status(self) -> None:
        rows_shown = len(filter_journals(self._all_journals, self.search_query))
        max_page = max(1, (self.total + PER_PAGE - 1) // PER_PAGE)
        msg = (
            f"ページ {self.page}/{max_page}  全 {self.total} 件  "
            f"表示 {rows_shown} 件"
        )
        if self.search_query:
            msg += f"  検索: {self.search_query!r}"
        self._set_status(msg)

    # --- アクション ---

    def action_refresh(self) -> None:
        self.run_worker(self.load_page(), exclusive=True)

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_clear_search(self) -> None:
        search = self.query_one("#search", Input)
        search.value = ""
        self.search_query = ""
        self._render_rows()
        self._update_status()

    def action_next_page(self) -> None:
        max_page = max(1, (self.total + PER_PAGE - 1) // PER_PAGE)
        if self.page < max_page:
            self.page += 1
            self.run_worker(self.load_page(), exclusive=True)

    def action_prev_page(self) -> None:
        if self.page > 1:
            self.page -= 1
            self.run_worker(self.load_page(), exclusive=True)

    def action_first_page(self) -> None:
        if self.page != 1:
            self.page = 1
            self.run_worker(self.load_page(), exclusive=True)

    def action_last_page(self) -> None:
        max_page = max(1, (self.total + PER_PAGE - 1) // PER_PAGE)
        if self.page != max_page:
            self.page = max_page
            self.run_worker(self.load_page(), exclusive=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.search_query = event.value
            self._render_rows()
            self._update_status()
