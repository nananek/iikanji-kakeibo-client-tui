"""AI 証憑仕訳の下書き一覧スクリーン

- ↑↓ でカーソル移動
- u で画像アップロード → AI 解析
- Enter で詳細モーダル
- a でクイックアクセプト（案1で登録）
- d で削除
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from iikanji_tui.api import APIClient, APIError


class AIDraftsScreen(Screen):
    """AI 証憑下書き一覧"""

    BINDINGS = [
        Binding("r", "refresh", "更新"),
        Binding("u", "upload", "アップロード"),
        Binding("a", "quick_accept", "クイック登録"),
        Binding("enter", "open_detail", "詳細"),
        Binding("d", "delete_draft", "削除"),
        Binding("q", "app.quit", "終了"),
        Binding("escape", "close_screen", "戻る"),
    ]

    DEFAULT_CSS = """
    AIDraftsScreen {
        layout: vertical;
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
        self._drafts: list[dict] = []
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(" ", id="status")
        yield DataTable(id="drafts", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#drafts", DataTable)
        table.cursor_type = "row"
        table.add_columns("作成日時", "状態", "日付", "摘要", "金額", "候補数")
        self.run_worker(self.load_drafts(), exclusive=True)

    async def load_drafts(self) -> None:
        if self._loading:
            return
        self._loading = True
        try:
            self._set_status("読み込み中...")
            try:
                payload = self.api.list_drafts(status="analyzed")
            except APIError as e:
                self._set_status(f"エラー: {e.message}")
                return
            self._drafts = payload.get("drafts", [])
            self._render_rows()
            count = len(self._drafts)
            self._set_status(f"下書き {count} 件")
        finally:
            self._loading = False

    def _render_rows(self) -> None:
        table = self.query_one("#drafts", DataTable)
        table.clear()
        for d in self._drafts:
            summary = d.get("summary") or {}
            amount = summary.get("amount", 0)
            table.add_row(
                d.get("created_at", "")[:16].replace("T", " "),
                d.get("status", ""),
                summary.get("date", "") or "-",
                summary.get("description", "") or summary.get("title", "") or "-",
                f"¥{amount:,}" if amount else "-",
                str(summary.get("suggestion_count", 0)),
                key=str(d.get("id")),
            )

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def _selected_draft(self) -> dict | None:
        table = self.query_one("#drafts", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key = table.coordinate_to_cell_key(
                table.cursor_coordinate
            ).row_key
        except Exception:
            return None
        target = row_key.value if hasattr(row_key, "value") else str(row_key)
        if target is None:
            return None
        for d in self._drafts:
            if str(d.get("id")) == str(target):
                return d
        return None

    # --- アクション ---

    def action_refresh(self) -> None:
        self.run_worker(self.load_drafts(), exclusive=True)

    def action_close_screen(self) -> None:
        self.app.pop_screen()

    def action_upload(self) -> None:
        from iikanji_tui.screens.upload import UploadScreen

        def _after(result: dict | None) -> None:
            if result:
                self._set_status(
                    f"AI 解析完了 (draft_id={result.get('draft_id')})"
                )
                self.run_worker(self.load_drafts(), exclusive=True)

        self.app.push_screen(UploadScreen(self.api), _after)

    def action_quick_accept(self) -> None:
        target = self._selected_draft()
        if target is None:
            self._set_status("対象の下書きが選択されていません。")
            return
        draft_id = int(target.get("id"))
        try:
            detail = self.api.get_draft(draft_id)
        except APIError as e:
            self._set_status(f"取得失敗: {e.message}")
            return
        suggestions = detail.get("draft", {}).get("suggestions") or []
        if not suggestions:
            self._set_status("候補がありません。")
            return
        suggestion = suggestions[0]
        try:
            resp = self.api.create_journal(
                date=suggestion.get("date") or "",
                description=suggestion.get("entry_description") or "",
                lines=[
                    {
                        "account_code": l.get("account_code", ""),
                        "debit": int(l.get("debit_amount") or 0),
                        "credit": int(l.get("credit_amount") or 0),
                    }
                    for l in suggestion.get("lines", [])
                ],
                source="ai_receipt",
                draft_id=draft_id,
            )
        except APIError as e:
            self._set_status(f"登録失敗: {e.message}")
            return
        self._set_status(
            f"伝票 #{resp.get('entry_number')} として登録しました。"
        )
        self.run_worker(self.load_drafts(), exclusive=True)

    def action_open_detail(self) -> None:
        from iikanji_tui.screens.ai_detail import AIDraftDetailScreen
        target = self._selected_draft()
        if target is None:
            return
        self.app.push_screen(
            AIDraftDetailScreen(self.api, int(target["id"])),
            self._after_detail,
        )

    def _after_detail(self, result: dict | None) -> None:
        if result:
            self._set_status(
                f"伝票 #{result.get('entry_number')} として登録しました。"
            )
        self.run_worker(self.load_drafts(), exclusive=True)

    def action_delete_draft(self) -> None:
        from iikanji_tui.screens.confirm import ConfirmScreen
        target = self._selected_draft()
        if target is None:
            self._set_status("対象の下書きが選択されていません。")
            return
        draft_id = int(target.get("id"))
        message = f"下書き #{draft_id} を削除しますか？"

        def _confirmed(yes: bool | None) -> None:
            if not yes:
                return
            try:
                self.api.delete_draft(draft_id)
            except APIError as e:
                self._set_status(f"削除失敗: {e.message}")
                return
            self._set_status(f"下書き #{draft_id} を削除しました。")
            self.run_worker(self.load_drafts(), exclusive=True)

        self.app.push_screen(ConfirmScreen(message), _confirmed)
