"""画像インラインプレビュー

textual-image を使って kitty graphics protocol / sixel / unicode half-block の
いずれかでレンダリングする。Image ウィジェットが端末を自動判定する。
"""

from __future__ import annotations

import io

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Static

try:
    from textual_image.widget import Image
    HAS_TEXTUAL_IMAGE = True
except ImportError:
    HAS_TEXTUAL_IMAGE = False


class ImagePreviewScreen(ModalScreen[None]):
    """画像をモーダルで全面表示する"""

    BINDINGS = [
        Binding("escape", "close", "閉じる"),
        Binding("q", "close", "閉じる"),
    ]

    DEFAULT_CSS = """
    ImagePreviewScreen {
        align: center middle;
    }
    #frame {
        width: 90%;
        height: 90%;
        background: $panel;
        border: thick $primary;
        padding: 1;
    }
    #title {
        height: 1;
        text-style: bold;
        padding-bottom: 1;
    }
    #image-area {
        height: 1fr;
        align: center middle;
    }
    .err {
        color: $error;
        text-align: center;
    }
    """

    def __init__(self, image_bytes: bytes, *, title: str = "証憑画像", **kwargs):
        super().__init__(**kwargs)
        self._image_bytes = image_bytes
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="frame"):
            yield Static(f"📎 {self._title}  (Esc で閉じる)", id="title")
            with Container(id="image-area"):
                if not HAS_TEXTUAL_IMAGE:
                    yield Static(
                        "[red]textual-image が見つかりません。\n"
                        "pip install textual-image で導入してください。[/red]",
                        classes="err",
                    )
                elif not self._image_bytes:
                    yield Static("[yellow]画像データがありません[/yellow]", classes="err")
                else:
                    try:
                        yield Image(io.BytesIO(self._image_bytes))
                    except Exception as e:
                        yield Static(
                            f"[red]画像の読み込みに失敗しました: {e}[/red]",
                            classes="err",
                        )
        yield Footer()

    def action_close(self) -> None:
        self.dismiss(None)
