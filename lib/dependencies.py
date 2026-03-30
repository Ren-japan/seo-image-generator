"""
共有依存関係（マネージャーインスタンス）
app.pyの再実行を避けるため、ページからはこのモジュール経由でマネージャーにアクセスする。

ストレージバックエンド切り替え:
  - GOOGLE_DRIVE_FOLDER_ID が設定されていれば Google Drive を使用
  - 未設定ならローカルファイルシステム（従来どおり）
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from lib.storage import LocalStorage, StorageBackend
from lib.config_manager import ConfigManager
from lib.preset_manager import PresetManager

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _get_secret(key: str) -> str | None:
    """環境変数 or st.secrets から値を取得（Cloud/ローカル両対応）"""
    val = os.getenv(key)
    if val:
        return val
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return None


def _use_google_drive() -> bool:
    """Google Drive ストレージを使うかどうか"""
    return bool(_get_secret("GOOGLE_DRIVE_FOLDER_ID"))


@st.cache_resource
def _get_drive_storage(folder_id: str) -> StorageBackend:
    """Google Drive ストレージのシングルトン"""
    from lib.storage import GoogleDriveStorage
    return GoogleDriveStorage(
        folder_id=folder_id,
        credentials_json=_get_secret("GOOGLE_SERVICE_ACCOUNT_JSON"),
        credentials_file=_get_secret("GOOGLE_SERVICE_ACCOUNT_FILE"),
    )


@st.cache_resource
def get_storage():
    """全ストレージ共通: Drive or ローカル(プロジェクトルート)"""
    if _use_google_drive():
        return _get_drive_storage(_get_secret("GOOGLE_DRIVE_FOLDER_ID"))
    return LocalStorage(PROJECT_ROOT)


# 後方互換エイリアス
get_config_storage = get_storage
get_preset_storage = get_storage
get_output_storage = get_storage


@st.cache_resource
def get_config_manager():
    return ConfigManager(get_config_storage())


@st.cache_resource
def get_preset_manager():
    return PresetManager(get_preset_storage())
