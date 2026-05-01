"""TUI アプリ本体"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Static

from iikanji_tui.config import Config, load_config


class IikanjiTUI(App):
    """いいかんじ™家計簿 TUI クライアント"""

    CSS = """
    Screen {
        background: $surface;
    }
    #main {
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "終了"),
        Binding("?", "help", "ヘルプ"),
    ]

    TITLE = "いいかんじ™家計簿"
    SUB_TITLE = "TUI クライアント"

    def __init__(self, config: Config | None = None, **kwargs):
        super().__init__(**kwargs)
        self.config = config or load_config()

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main"):
            with Vertical():
                if self.config.is_authenticated():
                    yield Static(
                        f"接続先: [b]{self.config.api_url}[/b]\n"
                        f"認証済み (token: {self.config.access_token[:11]}...)\n\n"
                        "Phase 3 以降で仕訳一覧などを実装します。",
                        id="status",
                    )
                else:
                    yield Static(
                        "[yellow]未認証です。[/yellow]\n\n"
                        "[b]iikanji-tui login[/b] コマンドで OAuth 認証を行ってください。",
                        id="status",
                    )
        yield Footer()

    def action_help(self) -> None:
        self.notify("q: 終了 / ?: このヘルプ", title="ヘルプ")
