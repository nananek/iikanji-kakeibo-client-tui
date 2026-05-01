"""TUI アプリ本体"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Static

from iikanji_tui.api import APIClient
from iikanji_tui.config import Config, load_config


class WelcomeScreen(App):
    pass


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

    def __init__(self, config: Config | None = None,
                 api: APIClient | None = None, **kwargs):
        super().__init__(**kwargs)
        self.config = config or load_config()
        self._api = api

    @property
    def api(self) -> APIClient:
        if self._api is None:
            self._api = APIClient(
                base_url=self.config.api_url,
                access_token=self.config.access_token,
            )
        return self._api

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main"):
            with Vertical():
                if self.config.is_authenticated():
                    yield Static(
                        f"接続先: [b]{self.config.api_url}[/b]\n"
                        f"認証済み (token: {self.config.access_token[:11]}...)",
                        id="status",
                    )
                else:
                    yield Static(
                        "[yellow]未認証です。[/yellow]\n\n"
                        "[b]iikanji-tui login[/b] コマンドで OAuth 認証を行ってください。",
                        id="status",
                    )
        yield Footer()

    def on_mount(self) -> None:
        if self.config.is_authenticated():
            from iikanji_tui.screens.journal_list import JournalListScreen
            self.push_screen(JournalListScreen(self.api))

    def action_help(self) -> None:
        self.notify(
            "q: 終了 / r: 更新 / /: 検索 / n,p: ページ / g,G: 先頭・末尾",
            title="ヘルプ",
        )
