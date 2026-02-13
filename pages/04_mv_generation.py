"""
MV（メインビジュアル/アイキャッチ）画像生成ページ
テンプレート型: レイアウト固定、テキスト内容だけ変えて生成
"""

import io
import json
import datetime
import streamlit as st
from PIL import Image

from lib.gemini_client import GeminiClient, SUPPORTED_ASPECT_RATIOS, SUPPORTED_IMAGE_SIZES
from lib.article_analyzer import propose_mv_images
from lib.prompt_templates import render_design_system, render_mv_generation_prompt
from lib.image_postprocessor import (
    trim_whitespace,
    resize_to_target,
    add_title_overlay,
    add_logo,
    image_to_bytes,
)


def get_cm():
    from lib.dependencies import get_config_manager
    return get_config_manager()


def generate_mv_image(mv_proposal, idx, config, aspect_ratio, image_size, site_name=None):
    """1案分のMV画像を生成して session_state.mv_generated_images に追加する"""
    gemini = GeminiClient(api_key=st.session_state.api_key)
    design_system = render_design_system(config)

    # MV用の参照画像を取得
    cm = get_cm()
    mv_ref_images = []
    if site_name:
        mv_ref_images = cm.get_reference_pil_images(site_name, category="mv")

    if mv_ref_images:
        reference_images = mv_ref_images
        st.info(f"MV参照画像を{len(mv_ref_images)}枚使用")
    else:
        reference_images = []

    # MV参照画像の分析結果を取得
    mv_design_analysis = config.get("mv_ref_image_analysis", "")

    # サイトカラー（MV生成で最優先される）
    site_colors = {
        "primary_color": config.get("primary_color", "#3B82F6"),
        "secondary_color": config.get("secondary_color", "#10B981"),
        "accent_color": config.get("accent_color", "#F59E0B"),
        "background_color": config.get("background_color", "#FFFFFF"),
        "text_color": config.get("text_color", "#1F2937"),
        "danger_color": config.get("danger_color", "#E74A3B"),
    }

    # MVデザイン仕様書（手動。Gemini分析より優先）
    mv_design_spec = config.get("mv_design_spec", "")

    # MV生成プロンプト
    gen_prompt = render_mv_generation_prompt(
        design_system=design_system,
        mv_proposal=mv_proposal,
        aspect_ratio=aspect_ratio,
        language=config.get("language", "Japanese"),
        has_reference_images=bool(reference_images),
        mv_design_analysis=mv_design_analysis,
        site_colors=site_colors,
        mv_design_spec=mv_design_spec,
    )

    # Gemini API呼び出し
    gen_image, gen_text = gemini.generate_image(
        prompt=gen_prompt,
        reference_images=reference_images if reference_images else None,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )

    if gen_image:
        # 既存の同じproposal_idxの結果を上書き
        existing = [
            j for j, e in enumerate(st.session_state.mv_generated_images)
            if e["proposal_idx"] == idx
        ]
        entry = {
            "proposal_idx": idx,
            "proposal": mv_proposal,
            "image": gen_image,
            "processed_image": None,
            "response_text": gen_text,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        if existing:
            st.session_state.mv_generated_images[existing[0]] = entry
        else:
            st.session_state.mv_generated_images.append(entry)
        return True, gen_text
    else:
        return False, gen_text


def refine_mv_image(entry_index, refinement_text, config, site_name=None):
    """生成済みMV画像に微修正を加えて再生成する"""
    from google.genai import types

    gemini = GeminiClient(api_key=st.session_state.api_key)
    entry = st.session_state.mv_generated_images[entry_index]
    current_img = entry.get("processed_image") or entry["image"]

    # MV参照画像を取得
    cm = get_cm()
    mv_ref_images = []
    if site_name:
        mv_ref_images = cm.get_reference_pil_images(site_name, category="mv")

    # contents組み立て: 参照画像 → 現在の画像 → 修正指示
    contents = []
    if mv_ref_images:
        for ref_img in mv_ref_images:
            contents.append(ref_img)
    contents.append(current_img)
    contents.append(
        "上記の画像を以下の指示に従って微修正してください。"
        "レイアウト構造・テキスト装飾スタイル・配色は変更せず、指示された部分のみを修正してください。\n\n"
        f"【修正指示】\n{refinement_text}"
    )

    response = gemini.client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    gen_image = None
    gen_text = None
    if response.parts:
        for part in response.parts:
            if part.text is not None:
                gen_text = part.text
            elif part.inline_data is not None:
                genai_img = part.as_image()
                gen_image = Image.open(io.BytesIO(genai_img.image_bytes))

    if gen_image:
        entry["image"] = gen_image
        entry["processed_image"] = None
        entry["response_text"] = gen_text
        entry["timestamp"] = datetime.datetime.now().isoformat()
        return True, gen_text
    return False, gen_text


# =============================================
# ヘッダー
# =============================================
st.title("MV画像生成")

if not st.session_state.current_site:
    st.warning("サイドバーからサイトを選択するか、「サイト設定」から新規登録してください。")
    st.stop()

if not st.session_state.api_key:
    st.error("Gemini API Keyが設定されていません。サイドバーから入力してください。")
    st.stop()

config = st.session_state.site_config

st.info(f"対象サイト: **{config.get('brand_name', st.session_state.current_site)}**")

# MV参照画像の有無を表示
cm = get_cm()
mv_ref_count = len(cm.list_reference_images(st.session_state.current_site, category="mv"))
if mv_ref_count > 0:
    st.success(f"MV参照画像: {mv_ref_count}枚登録済み")
else:
    st.warning("MV参照画像が未登録です。「サイト設定」→「参照画像」→「MV用」タブから登録すると、スタイルが安定します。")

# デザイン仕様書の有無を表示
if config.get("mv_design_spec", "").strip():
    st.success("MVデザイン仕様書: 登録済み（生成時に使用されます）")
else:
    st.info("MVデザイン仕様書: 未登録（参照画像のみで生成します）")

# =============================================
# Step 1: 記事入力
# =============================================
st.subheader("Step 1: 記事情報")

article_title = st.text_input(
    "記事タイトル",
    value=st.session_state.article_title,
    placeholder="例: リライブシャツの口コミ・評判を調査！本当に効果はある？",
    key="mv_input_article_title",
)
st.session_state.article_title = article_title

article_text = st.text_area(
    "記事本文（概要把握用。全文でなくてもOK）",
    value=st.session_state.article_text,
    height=200,
    placeholder="記事の本文をここに貼り付けてください...",
    key="mv_input_article_text",
)
st.session_state.article_text = article_text

# =============================================
# Step 2: MV案の自動生成 or 手動入力
# =============================================
st.subheader("Step 2: MVテキスト案")

st.caption("AIに自動生成させるか、各スロットを手動で入力できます")

auto_col, manual_col = st.columns(2)

with auto_col:
    btn_auto = st.button(
        "AIで自動生成",
        type="primary",
        disabled=not article_title.strip(),
        use_container_width=True,
    )

with manual_col:
    btn_manual = st.button(
        "手動で入力",
        use_container_width=True,
    )

if btn_auto and article_title.strip():
    with st.status("MVテキスト案を生成中...", expanded=True) as status:
        try:
            st.write("記事の主題を分析し、MVテキスト案を設計中...")
            gemini = GeminiClient(api_key=st.session_state.api_key)
            mv_proposals = propose_mv_images(article_title, article_text, gemini)

            if mv_proposals:
                st.session_state.mv_proposals = mv_proposals
                st.session_state.mv_selected_proposals = [True] * len(mv_proposals)
                status.update(label=f"MVテキスト案を{len(mv_proposals)}パターン生成", state="complete")
            else:
                status.update(label="生成に失敗しました", state="error")
                st.error("Geminiからの応答を解析できませんでした。")
        except Exception as e:
            status.update(label="エラー発生", state="error")
            st.error(f"エラー: {e}")

if btn_manual:
    # 空のテンプレートを1つ追加
    empty_proposal = {
        "hook_text": "",
        "main_title": "",
        "subtitle": "",
        "band_text": "",
        "supplement_text": "",
        "person_description": "",
    }
    st.session_state.mv_proposals = [empty_proposal]
    st.session_state.mv_selected_proposals = [True]

# =============================================
# Step 3: MV案の表示・編集
# =============================================
if st.session_state.mv_proposals:
    mv_proposals = st.session_state.mv_proposals
    mv_selected = st.session_state.mv_selected_proposals

    st.subheader("Step 3: MVテキスト内容を確認・編集")

    # テンプレートのレイアウト説明
    with st.expander("MVテンプレートの構造", expanded=False):
        st.code("""
┌─────────────────────────────────────┐
│ [煽りテキスト]（左上・小さめ）        │
│                                     │
│ [メインタイトル]（左寄せ・超大きい）   │
│                                     │
│ [サブタイトル]（左寄せ・大きい・赤）   │
│                                     │
│ ┌帯─────────────────┐              │
│ │[帯テキスト]        │ [メイン人物]  │
│ └────────────────────┘（右側・大きい）│
│ [補足テキスト]（左下）                │
└─────────────────────────────────────┘
背景: 上部カラーグラデーション → 下部ホワイト
        """, language="text")

    for i, mv_proposal in enumerate(mv_proposals):
        mv_selected[i] = st.checkbox(
            f"MV案{i+1}: {mv_proposal.get('main_title', '未設定')} - {mv_proposal.get('subtitle', '')}",
            value=mv_selected[i],
            key=f"mv_select_{i}",
        )

        with st.expander(f"MV案{i+1}を編集", expanded=(len(mv_proposals) == 1)):
            # プレビュー（現在の内容を表示）
            st.markdown("**現在のテキスト内容:**")
            preview_col1, preview_col2 = st.columns([2, 1])
            with preview_col1:
                hook = mv_proposal.get("hook_text", "")
                main = mv_proposal.get("main_title", "")
                sub = mv_proposal.get("subtitle", "")
                band = mv_proposal.get("band_text", "")
                supp = mv_proposal.get("supplement_text", "")

                if hook:
                    st.markdown(f"*{hook}*")
                if main:
                    st.markdown(f"### {main}")
                if sub:
                    st.markdown(f"**:red[{sub}]**")
                if band:
                    st.info(band)
                if supp:
                    st.caption(supp)

            with preview_col2:
                person = mv_proposal.get("person_description", "")
                if person:
                    st.markdown(f"**人物:** {person}")

            st.divider()
            st.markdown("**各スロットを編集:**")

            # 煽りテキスト + メインタイトル
            edit_c1, edit_c2 = st.columns(2)
            with edit_c1:
                mv_proposal["hook_text"] = st.text_input(
                    "煽りテキスト（5〜10文字）",
                    value=mv_proposal.get("hook_text", ""),
                    placeholder="例: 今話題の, 〇〇で人気",
                    key=f"mv_hook_{i}",
                )
            with edit_c2:
                mv_proposal["main_title"] = st.text_input(
                    "メインタイトル（2〜8文字）",
                    value=mv_proposal.get("main_title", ""),
                    placeholder="例: リライブシャツ, BAKUNE",
                    key=f"mv_main_{i}",
                )

            # サブタイトル
            mv_proposal["subtitle"] = st.text_input(
                "サブタイトル（8〜15文字・赤文字で表示）",
                value=mv_proposal.get("subtitle", ""),
                placeholder="例: 本当に効果はある？, 口コミ・評判を調査！",
                key=f"mv_sub_{i}",
            )

            # 帯テキスト
            mv_proposal["band_text"] = st.text_input(
                "帯テキスト（10〜20文字・青帯の上に白文字）",
                value=mv_proposal.get("band_text", ""),
                placeholder="例: リアルな口コミを調査！",
                key=f"mv_band_{i}",
            )

            # 補足テキスト
            mv_proposal["supplement_text"] = st.text_input(
                "補足テキスト（15〜25文字）",
                value=mv_proposal.get("supplement_text", ""),
                placeholder="例: 期待できる効果や安く買う方法まで紹介",
                key=f"mv_supp_{i}",
            )

            # メイン人物
            mv_proposal["person_description"] = st.text_area(
                "メイン人物の説明（右下に大きく配置される人物）",
                value=mv_proposal.get("person_description", ""),
                placeholder="例: スマホで口コミを見ている若い女性、リラックスした表情",
                height=80,
                key=f"mv_person_{i}",
            )

    st.session_state.mv_selected_proposals = mv_selected

    # ----- Step 4: 生成設定 -----
    st.subheader("Step 4: 生成設定")

    mv_gen_col1, mv_gen_col2 = st.columns(2)

    with mv_gen_col1:
        mv_aspect_ratio = st.selectbox(
            "アスペクト比",
            SUPPORTED_ASPECT_RATIOS,
            index=SUPPORTED_ASPECT_RATIOS.index("16:9"),
            key="mv_gen_aspect_ratio",
        )

    with mv_gen_col2:
        mv_image_size = st.selectbox(
            "画像解像度",
            SUPPORTED_IMAGE_SIZES,
            index=SUPPORTED_IMAGE_SIZES.index("2K"),
            key="mv_gen_image_size",
        )

    # ----- Step 5: MV生成ボタン -----
    st.divider()

    if st.session_state.mv_generation_in_progress:
        st.session_state.mv_generation_in_progress = False

    # 個別生成ボタン群
    single_cols = st.columns(min(len(mv_proposals), 3))
    single_btns = {}
    for i, mv_proposal in enumerate(mv_proposals):
        with single_cols[i % 3]:
            label = mv_proposal.get("main_title", f"案{i+1}")
            single_btns[i] = st.button(
                f"「{label}」を生成",
                key=f"mv_gen_single_{i}",
                width="stretch",
            )

    # --- 個別生成の実行 ---
    for i, clicked in single_btns.items():
        if clicked:
            mv_proposal = mv_proposals[i]
            with st.status(f"MV案{i+1}を生成中...", expanded=True) as status:
                try:
                    ok, text = generate_mv_image(
                        mv_proposal, i, config,
                        mv_aspect_ratio, mv_image_size,
                        site_name=st.session_state.current_site,
                    )
                    if ok:
                        status.update(label=f"MV案{i+1}の生成完了!", state="complete")
                    else:
                        status.update(label=f"MV案{i+1}の生成に失敗", state="error")
                        st.warning(text or "")
                except Exception as e:
                    status.update(label="エラー発生", state="error")
                    st.error(f"MV案{i+1}の生成中にエラー: {e}")
            st.rerun()

# =============================================
# 生成結果の表示・後処理・ダウンロード
# =============================================
if st.session_state.mv_generated_images:
    st.subheader("MV生成結果")

    mv_images = st.session_state.mv_generated_images

    for i, entry in enumerate(mv_images):
        mv_proposal = entry["proposal"]
        img = entry["image"]
        processed = entry.get("processed_image")

        st.markdown(f"### MV案{entry['proposal_idx']+1}: {mv_proposal.get('main_title', '')} - {mv_proposal.get('subtitle', '')}")

        display_col, control_col = st.columns([2, 1])

        with display_col:
            display_img = processed if processed else img
            st.image(display_img, width="stretch")

        with control_col:
            # --- 微修正 ---
            st.markdown("**✏️ 微修正**")
            refine_text = st.text_area(
                "修正指示",
                placeholder="例: 人物をもう少し大きく、背景の色をもう少し明るく",
                height=80,
                key=f"mv_refine_text_{i}",
            )
            if st.button("微修正して再生成", key=f"mv_refine_btn_{i}", disabled=not refine_text.strip()):
                with st.spinner("微修正中..."):
                    try:
                        ok, text = refine_mv_image(
                            i, refine_text, config,
                            site_name=st.session_state.current_site,
                        )
                        if ok:
                            st.success("微修正完了!")
                        else:
                            st.warning(f"微修正に失敗: {text or ''}")
                    except Exception as e:
                        st.error(f"微修正エラー: {e}")
                st.rerun()

            # --- 再生成 ---
            st.divider()
            if st.button("同じ案で再生成", key=f"mv_regen_btn_{i}", use_container_width=True):
                with st.spinner("再生成中..."):
                    try:
                        ok, text = generate_mv_image(
                            mv_proposal, entry["proposal_idx"], config,
                            st.session_state.get("mv_gen_aspect_ratio", "16:9"),
                            st.session_state.get("mv_gen_image_size", "2K"),
                            site_name=st.session_state.current_site,
                        )
                        if ok:
                            st.success("再生成完了!")
                        else:
                            st.warning(f"再生成に失敗: {text or ''}")
                    except Exception as e:
                        st.error(f"再生成エラー: {e}")
                st.rerun()

            # --- 後処理 ---
            st.divider()
            st.markdown("**後処理**")

            # トリミング
            if st.button("余白トリミング", key=f"mv_trim_{i}"):
                trimmed = trim_whitespace(img)
                entry["processed_image"] = trimmed
                st.rerun()

            # リサイズ
            current_img = processed if processed else img
            cur_w, cur_h = current_img.size
            st.caption(f"現在: {cur_w}×{cur_h}px")

            mv_size = config.get("image_sizes", {}).get("mv", {"width": 1200, "height": 630})
            resize_c1, resize_c2 = st.columns(2)
            with resize_c1:
                target_w = st.number_input(
                    "幅(px)", value=mv_size.get("width", 1200), min_value=100, max_value=4096,
                    key=f"mv_resize_w_{i}",
                )
            with resize_c2:
                target_h = st.number_input(
                    "高さ(px)", value=mv_size.get("height", 630), min_value=100, max_value=4096,
                    key=f"mv_resize_h_{i}",
                )
            if st.button(f"リサイズ ({target_w}×{target_h})", key=f"mv_resize_{i}"):
                source = processed if processed else img
                resized = resize_to_target(source, target_w, target_h)
                entry["processed_image"] = resized
                st.rerun()

            # ダウンロード
            st.divider()
            download_img = processed if processed else img
            img_bytes = image_to_bytes(download_img)
            st.download_button(
                "この画像をダウンロード",
                data=img_bytes,
                file_name=f"mv_image_{entry['proposal_idx']+1}_{i}.png",
                mime="image/png",
                key=f"mv_dl_{i}",
                width="stretch",
            )

        st.divider()
