"""証憑一覧スクリーン

- ↑↓ + Page Up/Down でカーソル移動・ページング
- / で検索（摘要に対する API サーバ側検索）
- v で選択証憑のハッシュ検証
- s で画像をローカル保存
- o で外部ビューアで画像を開く（xdg-open / open）
- Esc で戻る
"""

from __future__ import annotations

import os
import platform
import subprocess
import tempfile
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static

from iikanji_tui.api import APIClient, APIError


PER_PAGE = 50


class VouchersScreen(Screen):
    BINDINGS = [
        Binding("r", "refresh", "更新"),
        Binding("slash", "focus_search", "検索"),
        Binding("escape", "close_or_clear", "戻る"),
        Binding("n", "next_page", "次"),
        Binding("p", "prev_page", "前"),
        Binding("v", "verify", "検証"),
        Binding("s", "save", "保存"),
        Binding("o", "open_external", "外部表示"),
        Binding("q", "app.quit", "終了"),
    ]

    DEFAULT_CSS = """
    VouchersScreen { layout: vertical; }
    #search_bar { height: 3; padding: 0 1; }
    #status { height: 1; padding: 0 1; color: $text-muted; }
    DataTable { height: 1fr; }
    """

    def __init__(self, api: APIClient, *,
                 save_dir: str | None = None,
                 opener=None, **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self.page = 1
        self.total = 0
        self.search_query = ""
        self._vouchers: list[dict] = []
        self._loading = False
        self.save_dir = save_dir or str(Path.home() / "Downloads")
        self._opener = opener  # テスト時に差し替え可能

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="search_bar"):
            yield Input(placeholder="検索（摘要）", id="search")
        yield Static(" ", id="status")
        yield DataTable(id="vouchers", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#vouchers", DataTable)
        table.cursor_type = "row"
        table.add_columns("日付", "摘要", "金額", "ID", "MIME", "アップロード", "期限")
        self.run_worker(self.load_page(), exclusive=True)

    async def load_page(self) -> None:
        if self._loading:
            return
        self._loading = True
        try:
            self._set_status("読み込み中...")
            try:
                payload = self.api.list_vouchers(
                    page=self.page, per_page=PER_PAGE,
                    search=self.search_query or None,
                )
            except APIError as e:
                self._set_status(f"エラー: {e.message}")
                return
            self.total = int(payload.get("total", 0))
            self._vouchers = payload.get("vouchers", [])
            self._render_rows()
            self._update_status()
        finally:
            self._loading = False

    def _render_rows(self) -> None:
        table = self.query_one("#vouchers", DataTable)
        table.clear()
        for v in self._vouchers:
            j = v.get("journal") or {}
            uploaded = (v.get("uploaded_at") or "")[:16].replace("T", " ")
            deadline = "⚠" if v.get("deadline_exceeded") else ""
            amount = j.get("amount", 0)
            table.add_row(
                j.get("date", "") or "-",
                j.get("description", "") or "-",
                f"¥{amount:,}" if amount else "-",
                str(v.get("id")),
                v.get("image_mime", ""),
                uploaded,
                deadline,
                key=str(v.get("id")),
            )

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def _update_status(self) -> None:
        max_page = max(1, (self.total + PER_PAGE - 1) // PER_PAGE)
        msg = (
            f"ページ {self.page}/{max_page}  全 {self.total} 件  "
            f"表示 {len(self._vouchers)} 件"
        )
        if self.search_query:
            msg += f"  検索: {self.search_query!r}"
        self._set_status(msg)

    def _selected_voucher(self) -> dict | None:
        table = self.query_one("#vouchers", DataTable)
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
        for v in self._vouchers:
            if str(v.get("id")) == str(target):
                return v
        return None

    # --- アクション ---

    def action_refresh(self) -> None:
        self.run_worker(self.load_page(), exclusive=True)

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_close_or_clear(self) -> None:
        if self.search_query:
            self.query_one("#search", Input).value = ""
            self.search_query = ""
            self.page = 1
            self.run_worker(self.load_page(), exclusive=True)
        else:
            self.app.pop_screen()

    def action_next_page(self) -> None:
        max_page = max(1, (self.total + PER_PAGE - 1) // PER_PAGE)
        if self.page < max_page:
            self.page += 1
            self.run_worker(self.load_page(), exclusive=True)

    def action_prev_page(self) -> None:
        if self.page > 1:
            self.page -= 1
            self.run_worker(self.load_page(), exclusive=True)

    def action_verify(self) -> None:
        target = self._selected_voucher()
        if target is None:
            self._set_status("対象の証憑が選択されていません。")
            return
        try:
            res = self.api.verify_voucher(int(target["id"]))
        except APIError as e:
            self._set_status(f"検証失敗: {e.message}")
            return
        verified = res.get("verified")
        if verified is True:
            self._set_status(
                f"✅ 改ざんなし (hash 一致 / id={target['id']})"
            )
        elif verified is False:
            self._set_status(
                f"❌ 改ざん検出 (hash 不一致 / id={target['id']})"
            )
        else:
            self._set_status(res.get("message") or "ハッシュ未記録")

    def action_save(self) -> None:
        target = self._selected_voucher()
        if target is None:
            self._set_status("対象の証憑が選択されていません。")
            return
        try:
            data = self.api.get_voucher_image(int(target["id"]))
        except APIError as e:
            self._set_status(f"取得失敗: {e.message}")
            return
        ext = _ext_from_mime(target.get("image_mime", ""))
        path = Path(self.save_dir) / f"voucher_{target['id']}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._set_status(f"保存しました: {path}")

    def action_open_external(self) -> None:
        target = self._selected_voucher()
        if target is None:
            self._set_status("対象の証憑が選択されていません。")
            return
        try:
            data = self.api.get_voucher_image(int(target["id"]))
        except APIError as e:
            self._set_status(f"取得失敗: {e.message}")
            return
        ext = _ext_from_mime(target.get("image_mime", ""))
        with tempfile.NamedTemporaryFile(
            suffix=ext, delete=False
        ) as f:
            f.write(data)
            tmp_path = f.name
        opener = self._opener or _default_opener()
        try:
            opener(tmp_path)
        except Exception as e:
            self._set_status(f"外部表示失敗: {e}")
            return
        self._set_status(f"外部ビューアで開きました: {tmp_path}")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.search_query = event.value
            self.page = 1
            self.run_worker(self.load_page(), exclusive=True)


def _ext_from_mime(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime, ".bin")


def _default_opener():
    """OS 既定の opener を返す"""
    system = platform.system()
    if system == "Darwin":
        return lambda path: subprocess.run(["open", path], check=False)
    if system == "Windows":
        return lambda path: os.startfile(path)  # type: ignore[attr-defined]
    return lambda path: subprocess.run(["xdg-open", path], check=False)
