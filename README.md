# iikanji-tui

[いいかんじ™家計簿](https://github.com/nananek/iikanji-kakeibo) の TUI クライアント。

## インストール

```bash
pip install -e .
```

## 使い方

### ログイン

```bash
iikanji-tui login --api-url https://your-server.tailnet.ts.net
```

OAuth Device Flow でブラウザ認証します。ターミナルに QR コードが表示されるので、
PWA ログイン済みのスマートフォンでスキャンして承認することもできます。

オプション:
- `--no-qr`: QR コード表示を抑制
- `--no-browser`: ブラウザ自動起動を抑制

### TUI 起動

```bash
iikanji-tui
```

## 設定ファイル

`~/.config/iikanji/config.toml` に保存されます。

```toml
api_url = "https://example.tailnet.ts.net"
access_token = "ikt_..."
```

## キーバインド

- `q`: 終了
- `?`: ヘルプ

## 開発

```bash
pip install -e ".[dev]"
pytest
```
