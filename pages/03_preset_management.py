"""
プリセット管理ページ
テイスト（イラストスタイル）とレイアウト（構成パターン）の参照画像を管理する。
"""

import streamlit as st


def get_pm():
    from lib.dependencies import get_preset_manager
    return get_preset_manager()


st.title("プリセット管理")
st.caption("画像生成時に参照するスタイル・レイアウトの見本画像を管理します")

pm = get_pm()

tab_taste, tab_layout = st.tabs(["🎨 テイスト（イラストスタイル）", "📐 レイアウト（構成パターン）"])

# =============================================
# テイストプリセット
# =============================================
with tab_taste:
    st.subheader("テイストカテゴリ")
    st.markdown("画像のイラストスタイルを決める参照画像です。生成時に「おまかせ」を選ぶと記事内容から最適なテイストを自動選択します。")

    taste_categories = pm.list_taste_categories()

    for cat in taste_categories:
        with st.expander(f"**{cat['name']}** ({cat['image_count']}枚) - {cat['description']}", expanded=False):
            # 既存画像の表示
            if cat["image_count"] > 0:
                thumbnails = pm.get_image_thumbnails("taste", cat["id"])
                cols = st.columns(min(4, len(thumbnails)) if thumbnails else 1)
                for i, (key, data) in enumerate(thumbnails):
                    with cols[i % 4]:
                        st.image(data, caption=key.split("/")[-1], use_container_width=True)
                        if st.button("削除", key=f"del_taste_{key}"):
                            pm.delete_image(key)
                            st.rerun()
            else:
                st.info("まだ参照画像がありません。下のアップロードから追加してください。")

            # アップロード
            uploaded = st.file_uploader(
                "参照画像をアップロード",
                accept_multiple_files=True,
                type=["png", "jpg", "jpeg", "webp"],
                key=f"upload_taste_{cat['id']}",
            )
            if uploaded:
                for file in uploaded:
                    pm.upload_image("taste", cat["id"], file.name, file.read())
                st.success(f"{len(uploaded)}枚アップロードしました。")
                st.rerun()

    # カスタムカテゴリへのアップロード（常に表示）
    st.divider()
    st.markdown("**カスタムテイストの追加**")
    st.caption("上記カテゴリに当てはまらないスタイルの参照画像はここにアップロード")
    custom_taste_upload = st.file_uploader(
        "カスタムテイスト画像",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg", "webp"],
        key="upload_taste_custom_extra",
    )
    if custom_taste_upload:
        for file in custom_taste_upload:
            pm.upload_image("taste", "custom", file.name, file.read())
        st.success(f"{len(custom_taste_upload)}枚アップロードしました。")
        st.rerun()

# =============================================
# レイアウトプリセット
# =============================================
with tab_layout:
    st.subheader("レイアウトカテゴリ")
    st.markdown("画像の構成パターンの参照画像です。記事のH2/H3構造に基づいて最適なレイアウトが自動提案されます。")

    layout_categories = pm.list_layout_categories()

    for cat in layout_categories:
        with st.expander(f"**{cat['name']}** ({cat['image_count']}枚) - {cat['description']}", expanded=False):
            # 既存画像の表示
            if cat["image_count"] > 0:
                thumbnails = pm.get_image_thumbnails("layout", cat["id"])
                cols = st.columns(min(4, len(thumbnails)) if thumbnails else 1)
                for i, (key, data) in enumerate(thumbnails):
                    with cols[i % 4]:
                        st.image(data, caption=key.split("/")[-1], use_container_width=True)
                        if st.button("削除", key=f"del_layout_{key}"):
                            pm.delete_image(key)
                            st.rerun()
            else:
                st.info("まだ参照画像がありません。下のアップロードから追加してください。")

            # アップロード
            uploaded = st.file_uploader(
                "参照画像をアップロード",
                accept_multiple_files=True,
                type=["png", "jpg", "jpeg", "webp"],
                key=f"upload_layout_{cat['id']}",
            )
            if uploaded:
                for file in uploaded:
                    pm.upload_image("layout", cat["id"], file.name, file.read())
                st.success(f"{len(uploaded)}枚アップロードしました。")
                st.rerun()

    # カスタムレイアウトへのアップロード
    st.divider()
    st.markdown("**カスタムレイアウトの追加**")
    custom_layout_upload = st.file_uploader(
        "カスタムレイアウト画像",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg", "webp"],
        key="upload_layout_custom_extra",
    )
    if custom_layout_upload:
        for file in custom_layout_upload:
            pm.upload_image("layout", "custom", file.name, file.read())
        st.success(f"{len(custom_layout_upload)}枚アップロードしました。")
        st.rerun()
