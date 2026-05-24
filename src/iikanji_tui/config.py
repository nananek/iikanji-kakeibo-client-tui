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
    # E2 PR-D-c: クライアント完結 AI 解析用の LLM API キー (オーナーがローカル保持)。
    # サーバ E2EE blob はブラウザ SharedWorker でしか復号できないため、Python
    # クライアントは LLM API キーを直接持つ。ai_provider で使用する provider を指定。
    ai_provider: str = "openai"  # "openai" / "anthropic" / "google"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    def is_authenticated(self) -> bool:
        return bool(self.api_url and self.access_token)

    def has_ai_key(self) -> bool:
        """ai_provider に対応する LLM API キーが設定されているか。"""
        key_map = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "google": self.google_api_key,
        }
        return bool(key_map.get(self.ai_provider))


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
        ai_provider=str(data.get("ai_provider", "openai")),
        openai_api_key=str(data.get("openai_api_key", "")),
        anthropic_api_key=str(data.get("anthropic_api_key", "")),
        google_api_key=str(data.get("google_api_key", "")),
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
