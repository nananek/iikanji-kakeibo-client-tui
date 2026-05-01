# iikanji-tui

[いいかんじ™家計簿](https://github.com/nananek/iikanji-kakeibo) の TUI クライアント。

## インストール

```bash
pip install -e .
```

## 使い方

```bash
iikanji-tui
```

初回起動時、サーバーURL を尋ねられた後、OAuth Device Flow でブラウザ認証します。

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
