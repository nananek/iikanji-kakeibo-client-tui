"""仕訳新規作成/編集モーダル

- 日付・摘要・明細行（複数）の入力
- 借方/貸方の合計をリアルタイム表示
- バランス済み + 必須項目を満たすと保存ボタン有効
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_cls
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.validation import Validator, ValidationResult
from textual.widgets import Button, Input, Label, Static

from iikanji_tui.api import APIClient, APIError


@dataclass
class JournalDraft:
    """編集中の仕訳データ"""

    date: str = ""
    description: str = ""
    lines: list[dict] = field(default_factory=list)
    entry_id: int | None = None  # 編集時のみ

    @classmethod
    def empty(cls, today: date_cls | None = None) -> "JournalDraft":
        d = (today or date_cls.today()).isoformat()
        return cls(
            date=d,
            description="",
            lines=[
                {"account_code": "", "debit": 0, "credit": 0, "description": ""},
                {"account_code": "", "debit": 0, "credit": 0, "description": ""},
            ],
        )

    @classmethod
    def from_journal(cls, journal: dict, *, copy: bool = False) -> "JournalDraft":
        """既存仕訳を JournalDraft に変換する。copy=True なら新規モード（id を破棄、日付は今日に）"""
        lines = [
            {
                "account_code": l.get("account_code", ""),
                "debit": int(l.get("debit") or 0),
                "credit": int(l.get("credit") or 0),
                "description": l.get("description") or "",
            }
            for l in journal.get("lines", [])
        ]
        if copy:
            return cls(
                date=date_cls.today().isoformat(),
                description=journal.get("description", "") or "",
                lines=lines,
                entry_id=None,
            )
        return cls(
            date=journal.get("date", "") or "",
            description=journal.get("description", "") or "",
            lines=lines,
            entry_id=int(journal.get("id")) if journal.get("id") else None,
        )

    def total_debit(self) -> int:
        return sum(int(l.get("debit") or 0) for l in self.lines)

    def total_credit(self) -> int:
        return sum(int(l.get("credit") or 0) for l in self.lines)

    def is_balanced(self) -> bool:
        return self.total_debit() == self.total_credit() and self.total_debit() > 0

    def validate(self) -> str | None:
        """エラーメッセージを返す。問題なければ None。"""
        if not self.date:
            return "日付は必須です。"
        try:
            date_cls.fromisoformat(self.date)
        except ValueError:
            return "日付は YYYY-MM-DD 形式で入力してください。"
        if not self.description.strip():
            return "摘要は必須です。"
        non_empty_lines = [
            l for l in self.lines
            if l.get("account_code") or l.get("debit") or l.get("credit")
        ]
        if len(non_empty_lines) < 2:
            return "明細は最低2行必要です。"
        for i, l in enumerate(non_empty_lines, 1):
            if not l.get("account_code"):
                return f"明細{i}: 科目コードは必須です。"
            d = int(l.get("debit") or 0)
            c = int(l.get("credit") or 0)
            if d == 0 and c == 0:
                return f"明細{i}: 借方または貸方の金額が必要です。"
            if d > 0 and c > 0:
                return f"明細{i}: 借方と貸方は同時に入力できません。"
        if not self.is_balanced():
            return f"貸借が一致しません（借方 {self.total_debit():,} / 貸方 {self.total_credit():,}）。"
        return None

    def to_api_payload(self) -> dict:
        """API 送信用 dict に変換する（空行を除外）"""
        non_empty = [
            l for l in self.lines
            if l.get("account_code") and (
                int(l.get("debit") or 0) > 0 or int(l.get("credit") or 0) > 0
            )
        ]
        return {
            "date": self.date,
            "description": self.description.strip(),
            "lines": [
                {
                    "account_code": l["account_code"],
                    "debit": int(l.get("debit") or 0),
                    "credit": int(l.get("credit") or 0),
                    "description": l.get("description", "") or "",
                }
                for l in non_empty
            ],
        }


class JournalEditScreen(ModalScreen[dict | None]):
    """仕訳の新規/編集/複写モーダル

    dismiss 時の戻り値: 保存成功なら API レスポンス dict、キャンセル時は None。
    """

    BINDINGS = [
        Binding("escape", "cancel", "キャンセル"),
        Binding("ctrl+s", "save", "保存"),
        Binding("ctrl+plus", "add_line", "明細追加"),
    ]

    DEFAULT_CSS = """
    JournalEditScreen {
        align: center middle;
    }
    #editor {
        width: 80%;
        height: 80%;
        background: $panel;
        border: thick $primary;
        padding: 1 2;
    }
    #title { text-style: bold; padding-bottom: 1; }
    #lines { height: 1fr; overflow: auto; }
    .line-row {
        height: 3;
        layout: horizontal;
    }
    .line-row Input { width: 1fr; margin-right: 1; }
    .err {
        color: $error;
        height: 1;
    }
    .totals {
        height: 1;
        text-style: bold;
    }
    .actions {
        height: 3;
        align-horizontal: right;
    }
    """

    def __init__(self, api: APIClient, draft: JournalDraft, *,
                 mode: str = "new", **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self.draft = draft
        self.mode = mode  # new / edit / copy
        self._submitting = False

    @property
    def title_text(self) -> str:
        return {
            "new": "仕訳を新規作成",
            "edit": f"仕訳を編集 (id={self.draft.entry_id})",
            "copy": "仕訳を複写して新規作成",
        }.get(self.mode, "仕訳")

    def compose(self) -> ComposeResult:
        with Vertical(id="editor"):
            yield Label(self.title_text, id="title")
            with Horizontal():
                yield Input(value=self.draft.date, placeholder="YYYY-MM-DD",
                            id="date", classes="date-field")
                yield Input(value=self.draft.description, placeholder="摘要",
                            id="description", classes="desc-field")
            with Vertical(id="lines"):
                for i, line in enumerate(self.draft.lines):
                    with Horizontal(classes="line-row"):
                        yield Input(value=line.get("account_code", ""),
                                    placeholder="科目", id=f"acct_{i}")
                        yield Input(value=str(line.get("debit") or "") or "",
                                    placeholder="借方", id=f"debit_{i}")
                        yield Input(value=str(line.get("credit") or "") or "",
                                    placeholder="貸方", id=f"credit_{i}")
                        yield Input(value=line.get("description", ""),
                                    placeholder="行摘要", id=f"ldesc_{i}")
            yield Static("", id="totals", classes="totals")
            yield Static("", id="error", classes="err")
            with Horizontal(classes="actions"):
                yield Button("追加行", id="add_line", variant="default")
                yield Button("キャンセル", id="cancel", variant="default")
                yield Button("保存", id="save", variant="primary")

    def on_mount(self) -> None:
        self._refresh_totals()

    # --- 入力同期 ---

    def on_input_changed(self, event: Input.Changed) -> None:
        wid = event.input.id or ""
        if wid == "date":
            self.draft.date = event.value
        elif wid == "description":
            self.draft.description = event.value
        elif "_" in wid:
            kind, idx_s = wid.rsplit("_", 1)
            try:
                idx = int(idx_s)
            except ValueError:
                return
            if idx >= len(self.draft.lines):
                return
            line = self.draft.lines[idx]
            if kind == "acct":
                line["account_code"] = event.value.strip()
            elif kind == "debit":
                line["debit"] = _parse_int(event.value)
            elif kind == "credit":
                line["credit"] = _parse_int(event.value)
            elif kind == "ldesc":
                line["description"] = event.value
        self._refresh_totals()

    def _refresh_totals(self) -> None:
        td = self.draft.total_debit()
        tc = self.draft.total_credit()
        diff = td - tc
        msg = f"借方 ¥{td:,}  貸方 ¥{tc:,}"
        if diff == 0 and td > 0:
            msg += "  [green]一致 ✓[/green]"
        elif diff != 0:
            msg += f"  [red]差額 ¥{diff:,}[/red]"
        self.query_one("#totals", Static).update(msg)

    def _show_error(self, msg: str) -> None:
        self.query_one("#error", Static).update(f"[red]{msg}[/red]")

    def _clear_error(self) -> None:
        self.query_one("#error", Static).update("")

    # --- アクション ---

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "save":
            self.action_save()
        elif bid == "cancel":
            self.action_cancel()
        elif bid == "add_line":
            self.action_add_line()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_add_line(self) -> None:
        self.draft.lines.append(
            {"account_code": "", "debit": 0, "credit": 0, "description": ""}
        )
        # 簡易: モーダルを閉じて再度開くのは煩雑なので、入力欄を動的追加
        idx = len(self.draft.lines) - 1
        from textual.containers import Horizontal
        row = Horizontal(classes="line-row")
        # widget mount は async なので run_after_idle
        self.query_one("#lines").mount(row)
        row.mount(Input(placeholder="科目", id=f"acct_{idx}"))
        row.mount(Input(placeholder="借方", id=f"debit_{idx}"))
        row.mount(Input(placeholder="貸方", id=f"credit_{idx}"))
        row.mount(Input(placeholder="行摘要", id=f"ldesc_{idx}"))

    def action_save(self) -> None:
        if self._submitting:
            return
        err = self.draft.validate()
        if err:
            self._show_error(err)
            return
        self._clear_error()
        self._submitting = True
        try:
            payload = self.draft.to_api_payload()
            if self.mode == "edit" and self.draft.entry_id is not None:
                # 編集 API は外部 API には未公開なので、削除→再作成方式は使わず
                # 編集機能は将来サーバー側で /api/v1/journals/<id> PUT を実装してから対応
                self._show_error("編集 API は未対応です（サーバー側で PUT 実装が必要）")
                return
            else:
                resp = self.api.create_journal(**payload)
        except APIError as e:
            self._show_error(f"保存失敗: {e.message}")
            return
        finally:
            self._submitting = False
        self.dismiss(resp)


def _parse_int(value: str) -> int:
    try:
        v = value.replace(",", "").strip()
        return int(v) if v else 0
    except (ValueError, TypeError):
        return 0
