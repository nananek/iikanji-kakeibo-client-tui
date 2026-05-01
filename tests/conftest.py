"""pytest フィクスチャ"""

import pytest


@pytest.fixture
def tmp_config_path(tmp_path):
    """テスト用の設定ファイルパス"""
    return tmp_path / "config.toml"
