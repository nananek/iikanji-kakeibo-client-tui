"""コマンドラインエントリーポイント"""

from __future__ import annotations

import sys

import click

from iikanji_tui.auth import perform_device_flow
from iikanji_tui.config import (
    Config, load_config, save_config, clear_config, default_config_path,
)


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """いいかんじ™家計簿 TUI クライアント"""
    if ctx.invoked_subcommand is None:
        ctx.invoke(run)


@main.command()
def run() -> None:
    """TUI を起動する"""
    from iikanji_tui.app import IikanjiTUI

    config = load_config()
    app = IikanjiTUI(config=config)
    app.run()


@main.command()
@click.option("--api-url", prompt="サーバーURL", help="API ベース URL")
@click.option("--no-qr", is_flag=True, help="QR コード表示を抑制する")
@click.option("--no-browser", is_flag=True, help="ブラウザの自動起動を抑制する")
def login(api_url: str, no_qr: bool, no_browser: bool) -> None:
    """OAuth Device Flow でログインする"""
    try:
        token = perform_device_flow(
            api_url.rstrip("/"),
            show_qr=not no_qr,
            open_browser=not no_browser,
        )
    except KeyboardInterrupt:
        click.echo("\nキャンセルしました。")
        sys.exit(1)

    config = load_config()
    config.api_url = api_url.rstrip("/")
    config.access_token = token
    save_config(config)
    click.echo(f"認証情報を保存しました: {default_config_path()}")


@main.command()
def logout() -> None:
    """設定ファイルを削除する"""
    clear_config()
    click.echo("ログアウトしました。")


@main.command()
def whoami() -> None:
    """現在の認証情報を表示する"""
    config = load_config()
    if not config.is_authenticated():
        click.echo("未認証です。`iikanji-tui login` を実行してください。")
        sys.exit(1)
    click.echo(f"接続先: {config.api_url}")
    click.echo(f"トークン: {config.access_token[:11]}...")
