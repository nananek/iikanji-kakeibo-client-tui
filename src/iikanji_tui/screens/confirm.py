"""シンプルな確認モーダル"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmScreen(ModalScreen[bool]):
    """Yes/No 確認ダイアログ。dismiss(True/False) で結果を返す。"""

    BINDINGS = [
        Binding("escape", "cancel", "キャンセル"),
        Binding("y", "confirm", "はい"),
        Binding("n", "cancel", "いいえ"),
    ]

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #dialog {
        width: 60%;
        max-width: 70;
        background: $panel;
        border: thick $error;
        padding: 1 2;
    }
    .actions {
        height: 3;
        align-horizontal: right;
    }
    """

    def __init__(self, message: str, *,
                 confirm_label: str = "削除",
                 confirm_variant: str = "error", **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.confirm_label = confirm_label
        self.confirm_variant = confirm_variant

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.message)
            with Horizontal(classes="actions"):
                yield Button("キャンセル", id="cancel")
                yield Button(self.confirm_label, id="confirm",
                             variant=self.confirm_variant)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
