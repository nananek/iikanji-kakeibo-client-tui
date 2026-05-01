"""画像アップロード → AI 解析モーダル"""

from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from iikanji_tui.api import APIClient, APIError


class UploadScreen(ModalScreen[dict | None]):
    """画像パスとメモを入力 → /api/v1/ai/analyze 呼出"""

    BINDINGS = [
        Binding("escape", "cancel", "キャンセル"),
        Binding("ctrl+s", "submit", "解析"),
    ]

    DEFAULT_CSS = """
    UploadScreen { align: center middle; }
    #dialog {
        width: 70%;
        max-width: 80;
        background: $panel;
        border: thick $primary;
        padding: 1 2;
    }
    .actions { height: 3; align-horizontal: right; }
    .err { color: $error; height: 1; }
    .info { color: $text-muted; height: 1; }
    LoadingIndicator { height: 3; }
    """

    def __init__(self, api: APIClient, **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self._submitting = False

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("画像をアップロードして AI 解析", id="title")
            yield Input(placeholder="画像ファイルパス (例: /tmp/receipt.jpg)",
                        id="path")
            yield Input(placeholder="メモ（任意）", id="comment")
            yield Static("", id="error", classes="err")
            yield Static("", id="info", classes="info")
            with Horizontal(classes="actions"):
                yield Button("キャンセル", id="cancel")
                yield Button("解析", id="submit", variant="primary")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        if self._submitting:
            return
        path = self.query_one("#path", Input).value.strip()
        comment = self.query_one("#comment", Input).value.strip() or None
        if not path:
            self._show_error("画像ファイルパスを入力してください。")
            return
        if not os.path.isfile(path):
            self._show_error(f"ファイルが見つかりません: {path}")
            return
        self._show_info("AI 解析中... (数秒〜数十秒)")
        self._show_error("")
        self._submitting = True
        try:
            result = self.api.analyze_image(path, comment=comment)
        except APIError as e:
            self._show_error(f"解析失敗: {e.message}")
            return
        finally:
            self._submitting = False
        self.dismiss(result)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self.action_submit()
        else:
            self.action_cancel()

    def _show_error(self, msg: str) -> None:
        self.query_one("#error", Static).update(f"[red]{msg}[/red]" if msg else "")

    def _show_info(self, msg: str) -> None:
        self.query_one("#info", Static).update(msg)
