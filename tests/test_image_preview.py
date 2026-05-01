"""画像プレビュー画面のテスト

textual-image の Image ウィジェットは実際のターミナルサイズに依存して
レンダリングするため、ヘッドレステストでは Static で差し替える。
"""

from __future__ import annotations

import io

import pytest
from textual.widgets import Static


@pytest.fixture(autouse=True)
def _stub_image(monkeypatch):
    """Image ウィジェットを Static にモック（ターミナル依存の描画を回避）"""
    import iikanji_tui.screens.image_preview as mod

    def _stub(image=None, **kwargs):
        return Static("[image-stub]", **{
            k: v for k, v in kwargs.items()
            if k in ("id", "classes", "name")
        })

    monkeypatch.setattr(mod, "Image", _stub)
    monkeypatch.setattr(mod, "HAS_TEXTUAL_IMAGE", True)


def _png_bytes() -> bytes:
    """テスト用の最小限の PNG 画像を生成"""
    try:
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("Pillow が無い環境")
    img = PILImage.new("RGB", (10, 10), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestImagePreviewScreen:
    @pytest.mark.asyncio
    async def test_screen_mounts_with_valid_image(self):
        """有効な画像で画面が落ちずにマウントできる"""
        from textual.app import App

        from iikanji_tui.screens.image_preview import ImagePreviewScreen

        class A(App):
            def on_mount(self):
                self.push_screen(ImagePreviewScreen(_png_bytes(), title="test"))

        app = A()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ImagePreviewScreen)

    @pytest.mark.asyncio
    async def test_empty_bytes_shows_message(self):
        from textual.app import App

        from iikanji_tui.screens.image_preview import ImagePreviewScreen

        class A(App):
            def on_mount(self):
                self.push_screen(ImagePreviewScreen(b"", title="empty"))

        app = A()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            statics = list(app.screen.query("Static"))
            assert any(
                "画像データがありません" in str(s.render()) for s in statics
            )

    @pytest.mark.asyncio
    async def test_escape_closes(self):
        from textual.app import App

        from iikanji_tui.screens.image_preview import ImagePreviewScreen

        class A(App):
            def on_mount(self):
                self.push_screen(ImagePreviewScreen(_png_bytes(), title="x"))

        app = A()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_close()
            await pilot.pause()
            assert not isinstance(app.screen, ImagePreviewScreen)


class TestVoucherPreviewIntegration:
    """vouchers 画面 → preview 画面の遷移"""

    def _make_app(self, voucher_dict: dict, *, image_bytes: bytes = b"\x89PNG\r\n\x1a\n"):
        from unittest.mock import MagicMock

        from iikanji_tui.api import APIClient
        from iikanji_tui.app import IikanjiTUI
        from iikanji_tui.config import Config

        api = MagicMock(spec=APIClient)
        api.list_journals.return_value = {
            "ok": True, "journals": [], "total": 0, "page": 1, "per_page": 50,
        }
        api.list_vouchers.return_value = {
            "ok": True, "vouchers": [voucher_dict],
            "total": 1, "page": 1, "per_page": 50,
        }
        api.get_voucher_image.return_value = image_bytes
        config = Config(
            api_url="https://x", access_token="ikt_x" + "0" * 32,
        )
        return IikanjiTUI(config=config, api=api), api

    @pytest.mark.asyncio
    async def test_enter_pushes_preview(self):
        from iikanji_tui.screens.image_preview import ImagePreviewScreen
        voucher = {
            "id": 7,
            "image_mime": "image/png",
            "uploaded_at": "2026-05-01T10:00:00",
            "deadline_exceeded": False,
            "journal": {"date": "2026-04-15",
                        "description": "セブン",
                        "amount": 500},
        }
        app, api = self._make_app(voucher, image_bytes=_png_bytes())
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            app.screen.action_preview()
            await pilot.pause()
            await pilot.pause()
            api.get_voucher_image.assert_called_with(7)
            assert isinstance(app.screen, ImagePreviewScreen)

    @pytest.mark.asyncio
    async def test_preview_with_no_selection(self):
        from unittest.mock import MagicMock

        from textual.widgets import Static

        from iikanji_tui.api import APIClient
        from iikanji_tui.app import IikanjiTUI
        from iikanji_tui.config import Config

        api = MagicMock(spec=APIClient)
        api.list_journals.return_value = {
            "ok": True, "journals": [], "total": 0, "page": 1, "per_page": 50,
        }
        api.list_vouchers.return_value = {
            "ok": True, "vouchers": [], "total": 0, "page": 1, "per_page": 50,
        }
        config = Config(
            api_url="https://x", access_token="ikt_x" + "0" * 32,
        )
        app = IikanjiTUI(config=config, api=api)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            app.screen.action_preview()
            await pilot.pause()
            api.get_voucher_image.assert_not_called()
            status = app.screen.query_one("#status", Static)
            assert "選択" in str(status.render())

    @pytest.mark.asyncio
    async def test_preview_api_error(self):
        from textual.widgets import Static

        from iikanji_tui.api import APIError
        voucher = {
            "id": 1, "image_mime": "image/jpeg",
            "uploaded_at": "2026-05-01T10:00:00",
            "deadline_exceeded": False,
            "journal": {"date": "2026-04-15", "description": "x", "amount": 100},
        }
        app, api = self._make_app(voucher)
        api.get_voucher_image.side_effect = APIError(404, "画像が見つかりません")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            app.screen.action_open_vouchers()
            await pilot.pause()
            await pilot.pause()
            app.screen.action_preview()
            await pilot.pause()
            status = app.screen.query_one("#status", Static)
            assert "見つかりません" in str(status.render())
