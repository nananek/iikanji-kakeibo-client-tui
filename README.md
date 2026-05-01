# iikanji-tui

[いいかんじ™家計簿](https://github.com/nananek/iikanji-kakeibo) の TUI クライアント。

仕訳の閲覧・新規作成・複写・削除、AI 証憑解析、証憑の閲覧・改ざん検証までターミナル上で完結します。

## 特徴

- **OAuth Device Flow** でログイン — API キーのコピペ不要
  - PWA ログイン済みのスマホで読み取れる **QR コード** を端末に表示
- 仕訳一覧・検索・ページング
- 仕訳の新規作成・複写・削除（貸借バランスを即時表示）
- AI 証憑解析: 画像アップロード → 候補選択 → 仕訳登録
- 証憑のハッシュ検証・ローカル保存・外部ビューア起動
- 設定は `~/.config/iikanji/config.toml` (パーミッション 0600) に保存

## インストール

```bash
pip install iikanji-tui
```

または GitHub から:

```bash
pip install git+https://github.com/nananek/iikanji-kakeibo-client-tui.git
```

### Docker

```bash
docker pull ghcr.io/nananek/iikanji-kakeibo-client-tui:latest
```

最低限のオプション:

| オプション | 必須 | 役割 |
|---|---|---|
| `-it` | ✅ | TTY を割り当てて TUI を表示 |
| `--rm` | 推奨 | コンテナ終了時に自動削除 |
| `-v "$HOME/.config/iikanji:/config/iikanji"` | 推奨 | `config.toml` をホスト側に永続化 |
| `--network host` | Linux + Tailscale 経由なら | ホストの Tailnet 経由でサーバーに到達 |
| `-e TERM=$TERM` | 任意 | カラー / 装飾を環境に合わせる |

#### ログイン

```bash
docker run --rm -it \
  -v "$HOME/.config/iikanji:/config/iikanji" \
  --network host \
  ghcr.io/nananek/iikanji-kakeibo-client-tui:latest \
  login --api-url https://your-server.tailnet.ts.net
```

ブラウザは表示できないので `--no-browser` を付けて、QR を端末に出して
スマホで承認するのがおすすめ:

```bash
docker run --rm -it \
  -v "$HOME/.config/iikanji:/config/iikanji" \
  --network host \
  ghcr.io/nananek/iikanji-kakeibo-client-tui:latest \
  login --api-url https://your-server.tailnet.ts.net --no-browser
```

#### TUI 起動

```bash
docker run --rm -it \
  -v "$HOME/.config/iikanji:/config/iikanji" \
  --network host \
  ghcr.io/nananek/iikanji-kakeibo-client-tui:latest
```

#### エイリアス（推奨）

`~/.bashrc` などに登録:

```bash
alias iikanji-tui='docker run --rm -it \
  -v "$HOME/.config/iikanji:/config/iikanji" \
  --network host \
  -e TERM="$TERM" \
  ghcr.io/nananek/iikanji-kakeibo-client-tui:latest'
```

以降は `iikanji-tui login --api-url ...` / `iikanji-tui` でネイティブ実行と同じ感覚で使えます。

#### よくある落とし穴

- **ボリューム権限**: エントリーポイントが `/config` の所有 UID/GID を検出して
  `gosu` で同じ UID にドロップしてから実行するので、通常は調整不要です。
  ホスト側でファイルを参照すると元の所有者で見えます。
  `--user` を渡せばその UID で動作します。
- **Tailscale 経由**: macOS/Windows の Docker Desktop はホストの Tailnet を
  そのまま参照できないため、Tailscale を別途コンテナ内に入れるか、
  ホスト側で `iikanji-tui` をネイティブ実行してください。
  Linux なら `--network host` で OK です。
- **画像保存・外部ビューア起動 (`s` / `o`)**: コンテナ内で完結するため
  `~/Downloads` への保存や `xdg-open` はホスト側からは見えません。
  使うならネイティブインストールが快適です。

## 使い方

### ログイン

```bash
iikanji-tui login --api-url https://your-server.tailnet.ts.net
```

ターミナルに表示される QR コードを PWA ログイン済みのスマホで読み取り、
ブラウザで承認すれば認証完了。

オプション:
- `--no-qr`: QR コード表示を抑制
- `--no-browser`: ブラウザ自動起動を抑制

### 起動

```bash
iikanji-tui          # 仕訳一覧で起動
iikanji-tui whoami   # 現在のログイン情報
iikanji-tui logout   # 設定を削除
```

## キーバインド

### 仕訳一覧（メイン画面）

| キー | 動作 |
|------|------|
| `↑`/`↓` | カーソル移動 |
| `n` / `p` | 次ページ / 前ページ |
| `g` / `G` | 先頭 / 末尾ページ |
| `/` | 検索バーにフォーカス |
| `Esc` | 検索クリア |
| `r` | 一覧再読込 |
| `a` | 新規仕訳モーダル |
| `c` | 選択行を複写して新規モーダル |
| `d` | 選択行を削除 (確認あり) |
| `i` | AI 証憑下書きスクリーン |
| `v` | 証憑一覧スクリーン |
| `q` | 終了 |

### 仕訳新規/複写モーダル

| キー | 動作 |
|------|------|
| `Tab` / `Shift+Tab` | 入力欄移動 |
| `Ctrl+S` | 保存 |
| `Esc` | キャンセル |

### AI 証憑下書き (`i`)

| キー | 動作 |
|------|------|
| `u` | 画像アップロード → AI 解析 |
| `a` | 案1で即仕訳登録（クイックアクセプト） |
| `Enter` | 詳細モーダル（候補切替・登録） |
| `d` | 下書き削除 |
| `r` | 再読込 |
| `Esc` | 戻る |

### 証憑一覧 (`v`)

| キー | 動作 |
|------|------|
| `/` | 摘要検索 |
| `v` | ハッシュ検証 |
| `s` | 画像をローカル保存 (~/Downloads) |
| `o` | 外部ビューアで開く |
| `Esc` | 検索クリア / 戻る |

## 設定ファイル

`~/.config/iikanji/config.toml` (XDG_CONFIG_HOME 準拠、パーミッション 0600):

```toml
api_url = "https://your-server.tailnet.ts.net"
access_token = "ikt_..."
last_used_at = "2026-05-01T12:00:00"
```

## 開発

```bash
git clone https://github.com/nananek/iikanji-kakeibo-client-tui.git
cd iikanji-kakeibo-client-tui
pip install -e ".[dev]"
pytest                  # テスト
ruff check src/ tests/  # lint
mypy src/               # 型チェック
```

## ライセンス

[いいかんじ™ライセンス (IKL) v1.0](LICENSE) — MIT 互換。
