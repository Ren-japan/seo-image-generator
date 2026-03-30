"""
共有依存関係（マネージャーインスタンス）
app.pyの再実行を避けるため、ページからはこのモジュール経由でマネージャーにアクセスする。
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from lib.storage import LocalStorage
from lib.config_manager import ConfigManager
from lib.preset_manager import PresetManager

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@st.cache_resource
def get_config_storage():
    return LocalStorage(PROJECT_ROOT / "configs")


@st.cache_resource
def get_preset_storage():
    return LocalStorage(PROJECT_ROOT / "presets")


@st.cache_resource
def get_output_storage():
    return LocalStorage(PROJECT_ROOT / "output")


@st.cache_resource
def get_config_manager():
    return ConfigManager(get_config_storage())


@st.cache_resource
def get_preset_manager():
    return PresetManager(get_preset_storage())
