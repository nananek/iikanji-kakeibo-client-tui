"""AI 下書き詳細スクリーン

- 案 1〜N の切り替え (Tab / 1-9)
- 各候補の明細を表示
- a で現在の候補を仕訳登録
- Esc で戻る
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from iikanji_tui.api import APIClient, APIError


class AIDraftDetailScreen(ModalScreen[dict | None]):
    """下書き詳細（dismiss 戻り値: 登録時の create_journal レスポンス or None）"""

    BINDINGS = [
        Binding("escape", "cancel", "戻る"),
        Binding("a", "accept", "登録"),
        Binding("tab", "next_suggestion", "次候補"),
        Binding("shift+tab", "prev_suggestion", "前候補"),
    ]

    DEFAULT_CSS = """
    AIDraftDetailScreen { align: center middle; }
    #dialog {
        width: 90%;
        height: 80%;
        background: $panel;
        border: thick $primary;
        padding: 1 2;
    }
    #lines { height: 1fr; }
    .header { text-style: bold; }
    .actions { height: 3; align-horizontal: right; }
    .err { color: $error; height: 1; }
    """

    def __init__(self, api: APIClient, draft_id: int, **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self.draft_id = draft_id
        self.suggestions: list[dict] = []
        self.current_index = 0
        self._submitting = False

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"下書き #{self.draft_id}", id="title", classes="header")
            yield Static("", id="suggestion_header")
            yield Static("", id="suggestion_meta")
            yield DataTable(id="lines")
            yield Static("", id="error", classes="err")
            with Horizontal(classes="actions"):
                yield Button("戻る", id="cancel")
                yield Button("前候補", id="prev")
                yield Button("次候補", id="next")
                yield Button("登録", id="accept", variant="primary")

    def on_mount(self) -> None:
        table = self.query_one("#lines", DataTable)
        table.add_columns("科目", "借方", "貸方", "摘要")
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        try:
            payload = self.api.get_draft(self.draft_id)
        except APIError as e:
            self._set_error(f"取得失敗: {e.message}")
            return
        self.suggestions = (
            payload.get("draft", {}).get("suggestions") or []
        )
        if not self.suggestions:
            self._set_error("候補がありません。")
            return
        self._render_view()

    def _render_view(self) -> None:
        if not self.suggestions:
            return
        s = self.suggestions[self.current_index]
        self.query_one("#suggestion_header", Static).update(
            f"[b]案 {self.current_index + 1}/{len(self.suggestions)}[/b]: "
            f"{s.get('title') or s.get('entry_description') or '-'}"
        )
        date = s.get("date") or "-"
        desc = s.get("entry_description") or "-"
        total = sum(int(l.get("debit_amount") or 0) for l in s.get("lines", []))
        self.query_one("#suggestion_meta", Static).update(
            f"日付: {date}    摘要: {desc}    金額: ¥{total:,}"
        )
        table = self.query_one("#lines", DataTable)
        table.clear()
        for l in s.get("lines", []):
            d = int(l.get("debit_amount") or 0)
            c = int(l.get("credit_amount") or 0)
            table.add_row(
                l.get("account_code", ""),
                f"¥{d:,}" if d else "",
                f"¥{c:,}" if c else "",
                l.get("description", "") or "",
            )

    def _set_error(self, msg: str) -> None:
        self.query_one("#error", Static).update(f"[red]{msg}[/red]" if msg else "")

    # --- アクション ---

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_next_suggestion(self) -> None:
        if not self.suggestions:
            return
        self.current_index = (self.current_index + 1) % len(self.suggestions)
        self._render_view()

    def action_prev_suggestion(self) -> None:
        if not self.suggestions:
            return
        self.current_index = (
            self.current_index - 1 + len(self.suggestions)
        ) % len(self.suggestions)
        self._render_view()

    def action_accept(self) -> None:
        if self._submitting or not self.suggestions:
            return
        s = self.suggestions[self.current_index]
        self._submitting = True
        try:
            resp = self.api.create_journal(
                date=s.get("date") or "",
                description=s.get("entry_description") or "",
                lines=[
                    {
                        "account_code": l.get("account_code", ""),
                        "debit": int(l.get("debit_amount") or 0),
                        "credit": int(l.get("credit_amount") or 0),
                    }
                    for l in s.get("lines", [])
                ],
                source="ai_receipt",
                draft_id=self.draft_id,
            )
        except APIError as e:
            self._set_error(f"登録失敗: {e.message}")
            return
        finally:
            self._submitting = False
        self.dismiss(resp)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "accept":
            self.action_accept()
        elif bid == "next":
            self.action_next_suggestion()
        elif bid == "prev":
            self.action_prev_suggestion()
        else:
            self.action_cancel()
