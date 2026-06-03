"""コマンドラインエントリーポイント"""

from __future__ import annotations

import sys

import click

from iikanji_tui.auth import perform_device_flow
from iikanji_tui.config import (
    clear_config,
    default_config_path,
    load_config,
    save_config,
)


def _emit_deprecation_warning() -> None:
    """v5.0 廃止予告を stderr に出力する (stdout/TUI 描画を汚さない)。

    いいかんじ™家計簿 v5.0 の E2EE 化に伴い iikanji-tui は廃止。CLI クライアント
    の E2EE 対応は client-py (iikanji パッケージ) に一本化される。
    """
    print(
        "⚠️  iikanji-tui は廃止されました (DEPRECATED)。\n"
        "    v5.0 (E2EE) 以降は動作しません。v4.x 系サーバー専用の最終版です。\n"
        "    代替: client-py (https://github.com/nananek/iikanji-kakeibo-client-py)。",
        file=sys.stderr,
    )


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """いいかんじ™家計簿 TUI クライアント (DEPRECATED — client-py を利用)"""
    _emit_deprecation_warning()
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
    # AI 設定 (E2 PR-D-d)
    click.echo(f"AI provider: {config.ai_provider}")
    click.echo(f"AI key: {'設定済み' if config.has_ai_key() else '未設定'}")


@main.command("set-ai-config")
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic", "google"]),
    required=True,
    help="使用する AI provider",
)
@click.option(
    "--api-key",
    prompt=True, hide_input=True, confirmation_prompt=True,
    help="LLM API キー (入力時はマスクされます)",
)
def set_ai_config(provider: str, api_key: str) -> None:
    """E2 PR-D-d: クライアント完結 AI 解析用の provider + API キーを保存する。

    サーバ E2EE blob はブラウザでしか復号できないため、TUI クライアントは
    オーナーが直接 LLM API キーを保持する設計。

    例:
        iikanji-tui set-ai-config --provider openai --api-key sk-...
        (--api-key を省略すると対話入力 + 二重確認)
    """
    config = load_config()
    config.ai_provider = provider
    if provider == "openai":
        config.openai_api_key = api_key
    elif provider == "anthropic":
        config.anthropic_api_key = api_key
    elif provider == "google":
        config.google_api_key = api_key
    save_config(config)
    click.echo(f"AI 設定を保存しました ({provider}): {default_config_path()}")


@main.command("clear-ai-config")
@click.confirmation_option(prompt="3 provider 全ての API キーを削除しますか?")
def clear_ai_config() -> None:
    """全 provider の API キーと ai_provider 設定をリセットする。"""
    config = load_config()
    config.ai_provider = "openai"
    config.openai_api_key = ""
    config.anthropic_api_key = ""
    config.google_api_key = ""
    save_config(config)
    click.echo("AI 設定を削除しました。")
