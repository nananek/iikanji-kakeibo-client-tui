#!/bin/bash
# Dockerコンテナのエントリーポイント
# /config をマウントしたホストの UID/GID を検出して、
# その UID で iikanji-tui を実行する。これにより
# ボリューム上のファイルパーミッションがホスト側ユーザーと一致する。

set -e

CONFIG_DIR="${XDG_CONFIG_HOME:-/config}"

if [ -d "$CONFIG_DIR" ]; then
    HOST_UID=$(stat -c %u "$CONFIG_DIR" 2>/dev/null || echo 1000)
    HOST_GID=$(stat -c %g "$CONFIG_DIR" 2>/dev/null || echo 1000)
else
    HOST_UID=1000
    HOST_GID=1000
fi

# UID 0 (root) で書きたい場合はそのまま実行
if [ "$HOST_UID" = "0" ]; then
    exec iikanji-tui "$@"
fi

# 既定の HOME / XDG ディレクトリを target user 用に揃える
mkdir -p "$CONFIG_DIR"
chown "$HOST_UID:$HOST_GID" "$CONFIG_DIR" 2>/dev/null || true

exec gosu "$HOST_UID:$HOST_GID" iikanji-tui "$@"
