"""
SEO記事画像自動生成ツール
エントリーポイント: ナビゲーション + 共通ステート初期化 + サイドバー
"""

import os
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path

# プロジェクトルートを基準にする
PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env")

# ----- ページ設定（最初に呼ぶ必要あり）-----
st.set_page_config(
    page_title="SEO Image Generator",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----- マネージャーは lib/dependencies.py から取得 -----
from lib.dependencies import get_config_manager, get_preset_manager


# ----- セッションステート初期化 -----
def init_session_state():
    defaults = {
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        # 画像生成プロバイダ: "gemini" or "openai"
        "image_provider": "gemini",
        "current_site": None,
        "site_config": {},
        # 記事内画像用
        "article_text": "",
        "article_title": "",
        "headings": [],
        "proposals": [],
        "selected_proposals": [],
        "generated_images": [],
        "generation_in_progress": False,
        # MV画像用
        "mv_proposals": [],
        "mv_selected_proposals": [],
        "mv_generated_images": [],
        "mv_generation_in_progress": False,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


init_session_state()

# ----- ナビゲーション定義 -----
pages = st.navigation(
    {
        "メイン": [
            st.Page("pages/01_image_generation.py", title="記事内画像生成", icon="🖼️", default=True),
            st.Page("pages/04_mv_generation.py", title="MV画像生成", icon="🎯"),
        ],
        "設定": [
            st.Page("pages/02_site_settings.py", title="サイト設定", icon="⚙️"),
            st.Page("pages/03_preset_management.py", title="プリセット管理", icon="🎨"),
        ],
    }
)

# ----- 共通サイドバー -----
with st.sidebar:
    st.markdown("### SEO Image Generator")
    st.caption("記事本文から最適な画像を自動生成")
    st.divider()

    # サイト選択
    cm = get_config_manager()
    sites = cm.list_sites()

    if sites:
        site_options = ["-- サイトを選択 --"] + sites
        current_idx = 0
        if st.session_state.current_site in sites:
            current_idx = sites.index(st.session_state.current_site) + 1

        selected = st.selectbox(
            "対象サイト",
            site_options,
            index=current_idx,
            key="sidebar_site_select",
        )

        if selected != "-- サイトを選択 --":
            if st.session_state.current_site != selected:
                st.session_state.current_site = selected
                st.session_state.site_config = cm.load(selected)
                st.rerun()
        else:
            st.session_state.current_site = None
            st.session_state.site_config = {}
    else:
        st.info("サイトが未登録です。\n「サイト設定」から登録してください。")

    # 現在のサイト情報表示
    if st.session_state.current_site:
        config = st.session_state.site_config
        st.divider()
        st.markdown(f"**{config.get('brand_name', st.session_state.current_site)}**")

        # カラーパレットのプレビュー
        colors = [
            config.get("primary_color", "#3B82F6"),
            config.get("secondary_color", "#10B981"),
            config.get("accent_color", "#F59E0B"),
            config.get("background_color", "#FFFFFF"),
            config.get("text_color", "#1F2937"),
        ]
        color_html = " ".join(
            f'<span style="display:inline-block;width:24px;height:24px;'
            f'background:{c};border:1px solid #ddd;border-radius:4px;"></span>'
            for c in colors
        )
        st.markdown(color_html, unsafe_allow_html=True)

    # 画像生成プロバイダ選択
    st.divider()
    st.markdown("### 画像生成プロバイダ")

    provider_options = {
        "gemini": "Gemini (gemini-3-pro-image-preview)",
        "openai": "OpenAI (gpt-image-2)",
    }
    current_provider = st.session_state.image_provider
    selected_provider = st.radio(
        "使用モデル",
        options=list(provider_options.keys()),
        format_func=lambda p: provider_options[p],
        index=list(provider_options.keys()).index(current_provider),
        key="sidebar_provider_select",
        help="記事分析は常に Gemini Flash。画像生成のみここで切替できる。",
    )
    if selected_provider != current_provider:
        st.session_state.image_provider = selected_provider
        st.rerun()

    # APIキー状態
    st.divider()
    st.markdown("### API Keys")

    # Gemini (記事分析 + 画像生成のGemini側で必須)
    if st.session_state.api_key:
        st.success("Gemini Key: 設定済み", icon="✅")
    else:
        st.warning("Gemini Key: 未設定（記事分析に必須）", icon="⚠️")
        api_key_input = st.text_input("Gemini API Key", type="password", key="sidebar_api_key")
        if api_key_input:
            st.session_state.api_key = api_key_input
            st.rerun()

    # OpenAI (OpenAI 画像生成を使う場合のみ必須)
    if st.session_state.openai_api_key:
        st.success("OpenAI Key: 設定済み", icon="✅")
    else:
        if st.session_state.image_provider == "openai":
            st.error("OpenAI Key: 未設定", icon="❌")
        else:
            st.caption("OpenAI Key: 未設定（OpenAI使用時に必要）")
        openai_key_input = st.text_input("OpenAI API Key", type="password", key="sidebar_openai_api_key")
        if openai_key_input:
            st.session_state.openai_api_key = openai_key_input
            st.rerun()

# ----- ページ実行 -----
pages.run()
