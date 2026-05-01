"""設定ファイルの読み書き

~/.config/iikanji/config.toml に api_url / access_token を保存する。
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def default_config_path() -> Path:
    """XDG_CONFIG_HOME を考慮した設定ファイルパス"""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "iikanji" / "config.toml"


@dataclass
class Config:
    api_url: str = ""
    access_token: str = ""
    last_used_at: str = ""

    def is_authenticated(self) -> bool:
        return bool(self.api_url and self.access_token)


def load_config(path: Path | None = None) -> Config:
    """設定ファイルを読み込む。存在しない場合は空の Config を返す。"""
    if path is None:
        path = default_config_path()
    if not path.exists():
        return Config()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Config(
        api_url=str(data.get("api_url", "")),
        access_token=str(data.get("access_token", "")),
        last_used_at=str(data.get("last_used_at", "")),
    )


def save_config(config: Config, path: Path | None = None) -> Path:
    """設定ファイルを保存する。ディレクトリは自動作成。パーミッションは 600。"""
    if path is None:
        path = default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {k: v for k, v in asdict(config).items() if v}
    payload = tomli_w.dumps(data)

    # アトミック書き込み + パーミッション
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def clear_config(path: Path | None = None) -> None:
    """設定ファイルを削除する（ログアウト用）"""
    if path is None:
        path = default_config_path()
    if path.exists():
        path.unlink()
