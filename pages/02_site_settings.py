"""
サイト設定ページ
サイトの登録・デザインシステム・カラーパレット・画像サイズを管理する。
"""

import os
import streamlit as st
from lib.color_extractor import extract_colors_from_url
from lib.prompt_templates import render_design_system, MV_DESIGN_SPEC_DEFAULT


def get_cm():
    from lib.dependencies import get_config_manager
    return get_config_manager()


def get_gemini_client():
    """GeminiClientを取得（参照画像分析用）"""
    from lib.gemini_client import GeminiClient
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    return GeminiClient(api_key=api_key)


def run_ref_image_analysis(cm, site_name, config, category="article"):
    """参照画像をGeminiで分析してデザイン特徴を抽出し、設定に反映する"""
    gc = get_gemini_client()
    if gc is None:
        st.error("GEMINI_API_KEYが設定されていません。")
        return config

    label = "記事内画像" if category == "article" else "MV画像"
    config_key = "ref_image_analysis" if category == "article" else "mv_ref_image_analysis"

    with st.spinner(f"{label}の参照画像を分析中... Geminiでデザイン特徴を抽出しています"):
        try:
            analysis = cm.analyze_reference_images(site_name, gc, category=category)
            if analysis:
                config[config_key] = analysis
                cm.save(site_name, config)
                st.session_state.site_config = config
                st.session_state[f"show_{category}_analysis_result"] = True
                st.success(f"{label}の参照画像分析が完了しました。")
            else:
                st.warning("分析結果を取得できませんでした。")
        except Exception as e:
            st.error(f"分析中にエラーが発生しました: {e}")

    return config


# =============================================
# サイト管理セクション
# =============================================
st.title("サイト設定")

cm = get_cm()
sites = cm.list_sites()

tab_new, tab_edit = st.tabs(["新規サイト登録", "既存サイト編集"])

# ----- 新規サイト登録 -----
with tab_new:
    st.subheader("新しいサイトを登録")

    new_site_name = st.text_input(
        "サイト識別名（英数字・ハイフン推奨）",
        placeholder="例: djob-kango",
        key="new_site_name",
    )
    new_brand_name = st.text_input(
        "ブランド名（表示名）",
        placeholder="例: dジョブ看護",
        key="new_brand_name",
    )

    if st.button("サイトを登録", type="primary", key="btn_create_site"):
        if not new_site_name:
            st.error("サイト識別名を入力してください。")
        elif new_site_name in sites:
            st.error(f"「{new_site_name}」は既に登録されています。")
        else:
            config = cm.get_default()
            config["brand_name"] = new_brand_name or new_site_name
            cm.save(new_site_name, config)
            st.session_state.current_site = new_site_name
            st.session_state.site_config = config
            st.success(f"「{new_site_name}」を登録しました。")
            st.rerun()

# ----- 既存サイト編集 -----
with tab_edit:
    if not st.session_state.current_site:
        st.info("サイドバーからサイトを選択するか、新規登録してください。")
        st.stop()

    site_name = st.session_state.current_site
    config = st.session_state.site_config.copy()

    st.subheader(f"サイト: {config.get('brand_name', site_name)}")

    # =============================================
    # カラー自動抽出
    # =============================================
    with st.expander("🎨 カラーパレット自動抽出", expanded=False):
        url_input = st.text_input(
            "サイトURL",
            value=config.get("site_url", ""),
            placeholder="https://example.com",
            key="color_extract_url",
        )

        if st.button("URLからカラーを抽出", key="btn_extract_colors"):
            if not url_input:
                st.error("URLを入力してください。")
            else:
                with st.spinner("CSSを解析中..."):
                    try:
                        result = extract_colors_from_url(url_input)
                        st.session_state.extracted_colors = result
                        st.session_state.extracted_url = url_input
                        st.rerun()
                    except Exception as e:
                        st.error(f"カラー抽出に失敗しました: {e}")

        # 抽出結果の表示（session_stateに保持）
        if "extracted_colors" in st.session_state:
            result = st.session_state.extracted_colors
            suggested = result["suggested"]

            st.success("カラーパレットを抽出しました。")

            st.markdown("**抽出されたカラー候補:**")
            cols = st.columns(5)
            labels = ["Primary", "Secondary", "Accent", "Background", "Text"]
            keys = ["primary", "secondary", "accent", "background", "text"]
            for i, (label, key) in enumerate(zip(labels, keys)):
                with cols[i]:
                    color = suggested[key]
                    st.markdown(
                        f'<div style="background:{color};width:60px;height:60px;'
                        f'border-radius:8px;border:1px solid #ddd;"></div>',
                        unsafe_allow_html=True,
                    )
                    st.caption(f"{label}\n{color}")

            if result["all_colors"]:
                st.markdown("**検出された全カラー（上位20色）:**")
                color_html_parts = []
                for c in result["all_colors"][:20]:
                    color_html_parts.append(
                        f'<span style="display:inline-block;width:28px;height:28px;'
                        f'background:{c["hex"]};border:1px solid #ddd;border-radius:4px;'
                        f'margin:2px;" title="{c["hex"]} ({c["count"]}回)"></span>'
                    )
                st.markdown(" ".join(color_html_parts), unsafe_allow_html=True)

            if st.button("この配色を適用", key="btn_apply_colors"):
                config["site_url"] = st.session_state.get("extracted_url", url_input)
                config["primary_color"] = suggested["primary"]
                config["secondary_color"] = suggested["secondary"]
                config["accent_color"] = suggested["accent"]
                config["background_color"] = suggested["background"]
                config["text_color"] = suggested["text"]
                cm.save(site_name, config)
                st.session_state.site_config = config
                del st.session_state.extracted_colors
                st.rerun()

    # =============================================
    # 基本情報
    # =============================================
    st.subheader("基本情報")
    col1, col2 = st.columns(2)
    with col1:
        config["brand_name"] = st.text_input("ブランド名", value=config.get("brand_name", ""), key="edit_brand_name")
        config["site_url"] = st.text_input("サイトURL", value=config.get("site_url", ""), key="edit_site_url")
    with col2:
        config["brand_tone"] = st.text_input("ブランドトーン", value=config.get("brand_tone", ""), key="edit_brand_tone")
        config["language"] = st.selectbox(
            "言語",
            ["Japanese", "English"],
            index=0 if config.get("language") == "Japanese" else 1,
            key="edit_language",
        )

    # =============================================
    # カラーパレット（手動編集）
    # =============================================
    st.subheader("カラーパレット")
    cc1, cc2, cc3, cc4, cc5, cc6 = st.columns(6)
    with cc1:
        config["primary_color"] = st.color_picker("メイン色", value=config.get("primary_color", "#3B82F6"), key="cp_primary")
    with cc2:
        config["secondary_color"] = st.color_picker("サブ色", value=config.get("secondary_color", "#10B981"), key="cp_secondary")
    with cc3:
        config["accent_color"] = st.color_picker("アクセント色", value=config.get("accent_color", "#F59E0B"), key="cp_accent")
    with cc4:
        config["background_color"] = st.color_picker("背景色", value=config.get("background_color", "#FFFFFF"), key="cp_bg")
    with cc5:
        config["text_color"] = st.color_picker("テキスト色", value=config.get("text_color", "#1F2937"), key="cp_text")
    with cc6:
        config["danger_color"] = st.color_picker("警告色", value=config.get("danger_color", "#E74A3B"), key="cp_danger")

    # =============================================
    # イラストスタイル
    # =============================================
    st.subheader("イラストスタイル")
    config["illustration_style"] = st.text_input(
        "スタイル",
        value=config.get("illustration_style", ""),
        key="edit_illust_style",
    )
    col_a, col_b = st.columns(2)
    with col_a:
        config["line_weight"] = st.text_input("線の太さ・質感", value=config.get("line_weight", ""), key="edit_line_weight")
        config["character_style"] = st.text_input("人物造形", value=config.get("character_style", ""), key="edit_char_style")
    with col_b:
        config["fill_style"] = st.text_input("塗りスタイル", value=config.get("fill_style", ""), key="edit_fill_style")
        config["font_family"] = st.text_input("フォント", value=config.get("font_family", ""), key="edit_font")

    # =============================================
    # レイアウト・UIルール
    # =============================================
    st.subheader("レイアウト・UIルール")
    config["card_style"] = st.text_input("カードスタイル", value=config.get("card_style", ""), key="edit_card_style")
    config["spacing"] = st.text_input("余白ルール", value=config.get("spacing", ""), key="edit_spacing")

    # =============================================
    # 画像サイズ
    # =============================================
    st.subheader("画像サイズ設定")
    image_sizes = config.get("image_sizes", {})
    for size_key, size_data in image_sizes.items():
        st.markdown(f"**{size_data.get('label', size_key)}**")
        sc1, sc2 = st.columns(2)
        with sc1:
            image_sizes[size_key]["width"] = st.number_input(
                f"幅 ({size_key})", value=size_data.get("width", 886),
                min_value=100, max_value=4096, key=f"size_w_{size_key}",
            )
        with sc2:
            image_sizes[size_key]["height"] = st.number_input(
                f"高さ ({size_key})", value=size_data.get("height", 600),
                min_value=100, max_value=4096, key=f"size_h_{size_key}",
            )
    config["image_sizes"] = image_sizes

    # =============================================
    # 禁止事項・追加ノート
    # =============================================
    st.subheader("禁止事項・追加ノート")
    config["prohibited_elements"] = st.text_area(
        "禁止事項（改行区切り）",
        value=config.get("prohibited_elements", ""),
        height=120,
        key="edit_prohibited",
    )
    config["additional_notes"] = st.text_area(
        "追加スタイルノート",
        value=config.get("additional_notes", ""),
        height=80,
        key="edit_notes",
    )

    # =============================================
    # 参照画像（サイト固有スタイル）- カテゴリ別
    # =============================================
    st.subheader("参照画像（スタイルリファレンス）")
    st.caption("記事内画像とMV画像で別々の参照画像を登録できます。各カテゴリ最大5枚。アップロード時にGeminiが自動でデザイン特徴を分析します。")

    ref_tab_article, ref_tab_mv = st.tabs(["📊 記事内画像用", "🖼️ MV（アイキャッチ）用"])

    for ref_category, ref_tab in [("article", ref_tab_article), ("mv", ref_tab_mv)]:
        with ref_tab:
            cat_label = "記事内画像" if ref_category == "article" else "MV画像"
            config_key = "ref_image_analysis" if ref_category == "article" else "mv_ref_image_analysis"

            # 既存の参照画像を表示
            ref_keys = cm.list_reference_images(site_name, category=ref_category)
            if ref_keys:
                st.markdown(f"**登録済み: {len(ref_keys)}枚** (最大5枚)")
                ref_cols = st.columns(min(len(ref_keys), 5))
                for ri, rk in enumerate(ref_keys):
                    with ref_cols[ri % 5]:
                        try:
                            from PIL import Image as PILImage
                            import io as _io
                            ref_data = cm.load_reference_image(rk)
                            ref_img = PILImage.open(_io.BytesIO(ref_data))
                            st.image(ref_img, width="stretch")
                            fname = rk.split("/")[-1]
                            st.caption(fname)
                            if st.button("🗑", key=f"del_ref_{ref_category}_{ri}"):
                                cm.delete_reference_image(rk)
                                # 分析結果もクリア
                                if config_key in config:
                                    del config[config_key]
                                    cm.save(site_name, config)
                                    st.session_state.site_config = config
                                st.rerun()
                        except Exception:
                            st.warning(f"読込失敗: {rk}")

                # 再分析ボタン + スロット構造検出（MV用のみ）
                if ref_category == "mv":
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button(f"🔍 {cat_label}の参照画像を再分析", key=f"btn_reanalyze_ref_{ref_category}"):
                            config = run_ref_image_analysis(cm, site_name, config, category=ref_category)
                            st.rerun()
                    with btn_col2:
                        if st.button("🔲 スロット構造を検出", key="btn_detect_slot_structure"):
                            _slot_detect_success = False
                            with st.spinner("参照画像からスロット構造を検出中..."):
                                try:
                                    # APIキー: まず環境変数、次にsession_state
                                    from lib.gemini_client import GeminiClient
                                    _api_key = os.environ.get("GEMINI_API_KEY", "") or st.session_state.get("api_key", "")
                                    if not _api_key:
                                        st.error("GEMINI_API_KEYが設定されていません。サイドバーからAPIキーを入力してください。")
                                    else:
                                        gemini = GeminiClient(api_key=_api_key)
                                        slot_structure = cm.analyze_mv_slot_structure(site_name, gemini)
                                        if slot_structure and "slots" in slot_structure:
                                            config["mv_slot_structure"] = slot_structure
                                            cm.save(site_name, config)
                                            st.session_state.site_config = config
                                            st.success(f"スロット構造を検出: {len(slot_structure['slots'])}スロット")
                                            _slot_detect_success = True
                                        else:
                                            st.error("スロット構造の検出に失敗しました。")
                                except Exception as e:
                                    import traceback
                                    st.error(f"検出エラー: {e}")
                                    st.code(traceback.format_exc())
                            if _slot_detect_success:
                                st.rerun()

                    # スロット構造の表示・編集
                    if config.get("mv_slot_structure"):
                        with st.expander("検出済みスロット構造", expanded=False):
                            slot_struct = config["mv_slot_structure"]
                            for s in slot_struct.get("slots", []):
                                st.markdown(f"- **{s['role']}**: {s.get('description', '')}")
                            absent = slot_struct.get("absent_slots", [])
                            if absent:
                                st.caption(f"不在スロット: {', '.join(absent)}")
                            if slot_struct.get("person_style"):
                                st.caption(f"人物: {slot_struct['person_style']}")
                            if slot_struct.get("background_summary"):
                                st.caption(f"背景: {slot_struct['background_summary']}")

                            # JSON編集
                            import json as _json
                            edited_json = st.text_area(
                                "JSON編集（手動修正）",
                                value=_json.dumps(slot_struct, ensure_ascii=False, indent=2),
                                height=200,
                                key="edit_slot_structure",
                            )
                            if st.button("スロット構造を保存", key="save_slot_structure"):
                                try:
                                    config["mv_slot_structure"] = _json.loads(edited_json)
                                    cm.save(site_name, config)
                                    st.session_state.site_config = config
                                    st.success("保存しました")
                                    st.rerun()
                                except _json.JSONDecodeError:
                                    st.error("JSONの形式が不正です")

                            if st.button("スロット構造をクリア", key="clear_slot_structure"):
                                if "mv_slot_structure" in config:
                                    del config["mv_slot_structure"]
                                    cm.save(site_name, config)
                                    st.session_state.site_config = config
                                    st.rerun()
                else:
                    if st.button(f"🔍 {cat_label}の参照画像を再分析", key=f"btn_reanalyze_ref_{ref_category}"):
                        config = run_ref_image_analysis(cm, site_name, config, category=ref_category)
                        st.rerun()

            else:
                st.info(f"{cat_label}の参照画像がまだ登録されていません。")

            # アップロード
            if len(ref_keys) < 5:
                uploaded_refs = st.file_uploader(
                    f"{cat_label}の参照画像をアップロード",
                    type=["png", "jpg", "jpeg", "webp"],
                    accept_multiple_files=True,
                    key=f"upload_ref_images_{ref_category}",
                )
                if uploaded_refs:
                    added = 0
                    for uf in uploaded_refs:
                        if len(ref_keys) + added >= 5:
                            st.warning("最大5枚まで登録できます。")
                            break
                        cm.add_reference_image(site_name, uf.name, uf.getvalue(), category=ref_category)
                        added += 1
                    if added > 0:
                        st.success(f"{added}枚アップロードしました。")
                        # 自動でデザイン分析を実行
                        st.session_state[f"trigger_ref_analysis_{ref_category}"] = True
                        st.rerun()
            else:
                st.info("上限の5枚に達しています。削除してから追加してください。")

            # アップロード後の自動分析トリガー
            trigger_key = f"trigger_ref_analysis_{ref_category}"
            if st.session_state.get(trigger_key, False):
                del st.session_state[trigger_key]
                config = run_ref_image_analysis(cm, site_name, config, category=ref_category)

            # 分析結果の表示・編集
            existing_analysis = config.get(config_key, "")
            if existing_analysis:
                show_key = f"show_{ref_category}_analysis_result"
                with st.expander(f"🎯 {cat_label}参照画像デザイン分析結果（編集可）", expanded=st.session_state.get(show_key, False)):
                    edited_analysis = st.text_area(
                        f"{cat_label}デザイン分析結果",
                        value=existing_analysis,
                        height=400,
                        key=f"edit_analysis_{ref_category}",
                        help="AI分析結果を手動で修正できます。色コード・サイズ・位置などを実際の参照画像に合わせて微調整してください。",
                    )
                    if st.button(f"分析結果を保存", key=f"btn_save_analysis_{ref_category}", type="primary"):
                        config[config_key] = edited_analysis
                        cm.save(site_name, config)
                        st.session_state.site_config = config
                        st.success("分析結果を保存しました。")
                # 表示フラグをリセット
                if st.session_state.get(show_key, False):
                    st.session_state[show_key] = False

            # MV用: 手動デザイン仕様書（Gemini分析より優先される）
            if ref_category == "mv":
                with st.expander("📐 MVデザイン仕様書（レイアウト・装飾・比率ルール）", expanded=False):
                    st.caption(
                        "⚠️ **色の指定は不要**です（サイトのカラーパレットから自動適用されます）。\n\n"
                        "ここには **レイアウト構造・テキスト装飾・サイズ比率・配置バランス** など"
                        "色以外のデザインルールを記述してください。"
                        "参照画像の色は記事テーマごとに変わるため、固定HEXではなく"
                        "「テーマカラー」「アクセントカラー」等の役割名で指定すると安定します。"
                    )
                    existing_spec = config.get("mv_design_spec", "")
                    edited_spec = st.text_area(
                        "MVデザイン仕様書",
                        value=existing_spec,
                        height=500,
                        key="edit_mv_design_spec",
                        placeholder=MV_DESIGN_SPEC_DEFAULT,
                    )
                    col_save, col_default = st.columns([2, 1])
                    with col_save:
                        if st.button("デザイン仕様書を保存", key="btn_save_mv_design_spec", type="primary"):
                            config["mv_design_spec"] = edited_spec
                            cm.save(site_name, config)
                            st.session_state.site_config = config
                            st.success("MVデザイン仕様書を保存しました。")
                    with col_default:
                        if st.button("デフォルト仕様書を挿入", key="btn_insert_default_spec"):
                            config["mv_design_spec"] = MV_DESIGN_SPEC_DEFAULT
                            cm.save(site_name, config)
                            st.session_state.site_config = config
                            st.rerun()

    # =============================================
    # デザインシステムプロンプトのプレビュー
    # =============================================
    with st.expander("📋 デザインシステムプロンプト（プレビュー）", expanded=False):
        preview = render_design_system(config)
        st.code(preview, language="text")

    # =============================================
    # 保存・削除
    # =============================================
    st.divider()
    save_col, delete_col = st.columns([3, 1])
    with save_col:
        if st.button("設定を保存", type="primary", key="btn_save_config", use_container_width=True):
            cm.save(site_name, config)
            st.session_state.site_config = config
            st.success("設定を保存しました。")

    with delete_col:
        if st.button("🗑️ このサイトを削除", type="secondary", key="btn_delete_site", use_container_width=True):
            st.session_state.confirm_delete_site = True

    # 削除確認ダイアログ
    if st.session_state.get("confirm_delete_site"):
        st.warning(f"⚠️ 「{site_name}」を本当に削除しますか？参照画像や設定も全て削除されます。")
        confirm_col1, confirm_col2 = st.columns(2)
        with confirm_col1:
            if st.button("はい、削除する", type="primary", key="btn_confirm_delete"):
                cm.delete(site_name)
                st.session_state.current_site = None
                st.session_state.site_config = {}
                st.session_state.confirm_delete_site = False
                st.warning(f"「{site_name}」を削除しました。")
                st.rerun()
        with confirm_col2:
            if st.button("キャンセル", key="btn_cancel_delete"):
                st.session_state.confirm_delete_site = False
                st.rerun()
