"""OAuth 2.0 Device Authorization Grant (RFC 8628) クライアント"""

from __future__ import annotations

import io
import time
import webbrowser

import click

from iikanji_tui.api import APIClient, APIError


def render_qr_ascii(data: str) -> str:
    """文字列を QR コードの ASCII アートとして返す（端末表示用）。"""
    import qrcode

    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    buf = io.StringIO()
    qr.print_ascii(out=buf, invert=True)
    return buf.getvalue()


def perform_device_flow(
    api_url: str,
    client_name: str = "iikanji-tui",
    *,
    open_browser: bool = True,
    show_qr: bool = True,
    out=None,
    sleep=time.sleep,
) -> str:
    """OAuth Device Flow を実行してアクセストークンを取得する。

    Args:
        api_url: サーバーのベース URL
        client_name: 表示用のクライアント名
        open_browser: True なら webbrowser でブラウザを自動起動
        out: 出力先 (テスト用)。None なら click.echo
        sleep: ポーリングのスリープ関数 (テスト用)
    """
    def _echo(msg: str = ""):
        if out is None:
            click.echo(msg)
        else:
            out.write(msg + "\n")

    client = APIClient(base_url=api_url)
    response = client.oauth_device(client_name=client_name)

    user_code = response["user_code"]
    verification_uri = response["verification_uri"]
    verification_complete = response.get(
        "verification_uri_complete", verification_uri
    )
    device_code = response["device_code"]
    expires_in = int(response.get("expires_in", 600))
    interval = max(1, int(response.get("interval", 5)))

    _echo("ブラウザで以下のページにアクセスし、コードを入力してください:")
    _echo(f"  URL : {verification_uri}")
    _echo(f"  Code: {user_code}")
    _echo()
    _echo(f"または直接アクセス: {verification_complete}")
    if show_qr:
        try:
            qr_art = render_qr_ascii(verification_complete)
        except Exception:
            qr_art = ""
        if qr_art:
            _echo()
            _echo("PWA ログイン済みのスマホで以下の QR を読み取ってください:")
            _echo(qr_art)
    _echo("承認を待っています... (Ctrl+C でキャンセル)")

    if open_browser:
        try:
            webbrowser.open(verification_complete)
        except Exception:
            pass

    deadline = time.monotonic() + expires_in
    while time.monotonic() < deadline:
        sleep(interval)
        try:
            token_resp = client.oauth_token(device_code)
        except APIError as e:
            code = e.error_code or e.message.strip()
            if code == "authorization_pending":
                continue
            if code == "slow_down":
                interval += 5
                continue
            if code == "access_denied":
                raise click.ClickException("接続が拒否されました。")
            if code == "expired_token":
                raise click.ClickException("コードが期限切れです。再度実行してください。")
            raise click.ClickException(f"認証エラー: {e.message}")
        return token_resp["access_token"]

    raise click.ClickException("タイムアウトしました。再度実行してください。")
