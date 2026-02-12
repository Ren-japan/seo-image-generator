"""
画像生成ページ（メイン）
記事テキスト入力 → 分析 → 画像案提案 → 生成 → 後処理 → ダウンロード
"""

import io
import json
import zipfile
import datetime
import streamlit as st
from PIL import Image

from lib.gemini_client import GeminiClient, SUPPORTED_ASPECT_RATIOS, SUPPORTED_IMAGE_SIZES
from lib.article_analyzer import extract_headings, propose_images
from lib.prompt_templates import render_design_system, render_generation_prompt
from lib.image_postprocessor import (
    trim_whitespace,
    resize_to_target,
    add_title_overlay,
    add_logo,
    image_to_bytes,
)


def get_pm():
    from lib.dependencies import get_preset_manager
    return get_preset_manager()


def get_cm():
    from lib.dependencies import get_config_manager
    return get_config_manager()


def refine_image(entry_index, refinement_text, config, site_name=None):
    """生成済み画像に微修正を加えて再生成する"""
    from google.genai import types

    gemini = GeminiClient(api_key=st.session_state.api_key)
    entry = st.session_state.generated_images[entry_index]
    current_img = entry.get("processed_image") or entry["image"]

    # サイト参照画像を取得
    cm = get_cm()
    site_ref_images = []
    if site_name:
        site_ref_images = cm.get_reference_pil_images(site_name)

    # contents組み立て: 参照画像 → 現在の画像 → 修正指示
    contents = []
    if site_ref_images:
        for ref_img in site_ref_images:
            contents.append(ref_img)
    contents.append(current_img)
    contents.append(
        "上記の画像を以下の指示に従って微修正してください。"
        "スタイル・テイスト・配色・イラストのタッチは変更せず、指示された部分のみを修正してください。\n\n"
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


def generate_single_image(proposal, idx, config, pm, aspect_ratio, image_size, taste_id, article_text, site_name=None):
    """1案分の画像を生成して session_state.generated_images に追加する"""
    gemini = GeminiClient(api_key=st.session_state.api_key)
    design_system = render_design_system(config)

    # 提案にrecommended_aspect_ratioがあればそちらを優先
    recommended = proposal.get("recommended_aspect_ratio", "")
    if recommended and recommended in SUPPORTED_ASPECT_RATIOS:
        aspect_ratio = recommended
        st.info(f"📐 情報量に応じてアスペクト比を自動調整: **{aspect_ratio}**")

    # サイト参照画像を優先で取得
    cm = get_cm()
    site_ref_images = []
    if site_name:
        site_ref_images = cm.get_reference_pil_images(site_name)

    if site_ref_images:
        # サイト参照画像がある場合はそれを使う
        reference_images = site_ref_images
        st.info(f"サイト参照画像を{len(site_ref_images)}枚使用")
    else:
        # なければ従来のテイストプリセットを使う
        actual_taste_id = taste_id
        if actual_taste_id == "auto":
            actual_taste_id = pm.auto_select_taste(article_text[:500], gemini)
            st.info(f"テイスト自動選択: **{actual_taste_id}**")

        taste_images = pm.get_images("taste", actual_taste_id)

        # レイアウト参照画像
        layout_id = pm.get_layout_id_for_type(proposal.get("layout_type", ""))
        layout_images = pm.get_images("layout", layout_id)
        reference_images = taste_images + layout_images

    # 生成プロンプト（参照画像がある場合はスタイルトランスファー指示を付与）
    gen_prompt = render_generation_prompt(
        design_system=design_system,
        proposal=proposal,
        aspect_ratio=aspect_ratio,
        language=config.get("language", "Japanese"),
        has_reference_images=bool(reference_images),
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
            j for j, e in enumerate(st.session_state.generated_images)
            if e["proposal_idx"] == idx
        ]
        entry = {
            "proposal_idx": idx,
            "proposal": proposal,
            "image": gen_image,
            "processed_image": None,
            "response_text": gen_text,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        if existing:
            st.session_state.generated_images[existing[0]] = entry
        else:
            st.session_state.generated_images.append(entry)
        return True, gen_text
    else:
        return False, gen_text


# =============================================
# ヘッダー
# =============================================
st.title("画像生成")

if not st.session_state.current_site:
    st.warning("サイドバーからサイトを選択するか、「サイト設定」から新規登録してください。")
    st.stop()

if not st.session_state.api_key:
    st.error("Gemini API Keyが設定されていません。サイドバーから入力してください。")
    st.stop()

config = st.session_state.site_config
pm = get_pm()

st.info(f"対象サイト: **{config.get('brand_name', st.session_state.current_site)}**")

# =============================================
# Step 1: 記事入力
# =============================================
st.subheader("Step 1: 記事テキストを入力")

article_title = st.text_input(
    "記事タイトル",
    value=st.session_state.article_title,
    placeholder="例: 看護師のパワハラ対策完全ガイド",
    key="input_article_title",
)
st.session_state.article_title = article_title

article_text = st.text_area(
    "記事本文（Markdown or HTML）",
    value=st.session_state.article_text,
    height=300,
    placeholder="記事の本文をここに貼り付けてください...\n## 見出し2\n### 見出し3\nなどのH2/H3構造を含む形式がベストです。",
    key="input_article_text",
)
st.session_state.article_text = article_text

# =============================================
# Step 2: 記事分析
# =============================================
st.subheader("Step 2: 記事を分析して画像案を生成")

analyze_col1, analyze_col2 = st.columns([1, 3])

with analyze_col1:
    btn_analyze = st.button(
        "記事を分析",
        type="primary",
        disabled=not article_text.strip(),
        width="stretch",
    )

if btn_analyze and article_text.strip():
    with st.status("記事を分析中...", expanded=True) as status:
        try:
            # H2/H3構造の抽出
            st.write("H2/H3構造を解析中...")
            headings = extract_headings(article_text)
            st.session_state.headings = headings

            if headings:
                heading_summary = "\n".join(
                    f"{'  ' if h['level'] == 3 else ''}{'##' if h['level'] == 2 else '###'} {h['text']}"
                    for h in headings
                )
                st.code(heading_summary, language="markdown")
            else:
                st.warning("H2/H3見出しが検出されませんでした。本文の内容から画像案を生成します。")

            # Geminiで画像案を生成
            st.write("Gemini APIで画像案を生成中...")
            gemini = GeminiClient(api_key=st.session_state.api_key)
            proposals = propose_images(article_text, config, gemini)

            if proposals:
                st.session_state.proposals = proposals
                st.session_state.selected_proposals = [True] * len(proposals)
                status.update(label=f"分析完了: {len(proposals)}個の画像案を生成", state="complete")
            else:
                status.update(label="画像案の生成に失敗しました", state="error")
                st.error("Geminiからの応答を解析できませんでした。記事テキストを確認してください。")

        except Exception as e:
            status.update(label="エラー発生", state="error")
            st.error(f"分析中にエラーが発生しました: {e}")

# =============================================
# Step 3〜5: 画像案表示・設定・生成（proposalsがある場合）
# =============================================
if st.session_state.proposals:
    proposals = st.session_state.proposals
    selected = st.session_state.selected_proposals

    # ----- Step 3: 画像案の一覧（選択のみ。編集は下のexpander） -----
    st.subheader("Step 3: 画像案を選択")
    for i, proposal in enumerate(proposals):
        layout_icon = {
            "分類型": "📊", "比較型": "⚖️", "フロー型": "➡️",
            "ピラミッド型": "🔺", "アイコン軽量型": "💡",
        }.get(proposal.get("layout_type", ""), "📋")

        rec_ar = proposal.get("recommended_aspect_ratio", "")
        ar_label = f" [{rec_ar}]" if rec_ar else ""
        selected[i] = st.checkbox(
            f"{layout_icon} 画像案{i+1}: {proposal.get('placement', '')} - {proposal.get('layout_type', '')}{ar_label}",
            value=selected[i],
            key=f"select_proposal_{i}",
        )

    st.session_state.selected_proposals = selected

    # ----- Step 4: 生成設定 -----
    st.subheader("Step 4: 生成設定")

    gen_col1, gen_col2, gen_col3 = st.columns(3)

    with gen_col1:
        aspect_ratio = st.selectbox(
            "アスペクト比",
            SUPPORTED_ASPECT_RATIOS,
            index=SUPPORTED_ASPECT_RATIOS.index("16:9"),
            key="gen_aspect_ratio",
        )

    with gen_col2:
        image_size = st.selectbox(
            "画像解像度",
            SUPPORTED_IMAGE_SIZES,
            index=SUPPORTED_IMAGE_SIZES.index("2K"),
            key="gen_image_size",
        )

    with gen_col3:
        image_type = st.selectbox(
            "画像タイプ",
            list(config.get("image_sizes", {}).keys()),
            key="gen_image_type",
        )

    # テイスト・レイアウトプリセット選択
    preset_col1, preset_col2 = st.columns(2)

    with preset_col1:
        taste_categories = pm.list_taste_categories()
        taste_options = ["おまかせ（自動選択）"] + [
            f"{c['name']} ({c['image_count']}枚)" for c in taste_categories if c["image_count"] > 0
        ]
        taste_ids = ["auto"] + [c["id"] for c in taste_categories if c["image_count"] > 0]

        taste_selection = st.selectbox("テイストプリセット", taste_options, key="gen_taste")
        selected_taste_id = taste_ids[taste_options.index(taste_selection)]
        st.session_state.selected_taste_id = selected_taste_id

    with preset_col2:
        layout_options = ["提案に従う（自動）", "指定する"]
        layout_mode = st.selectbox("レイアウトプリセット", layout_options, key="gen_layout_mode")

    # ----- Step 5: 画像生成ボタン -----
    selected_count = sum(1 for s in selected if s)
    st.divider()

    # generation_in_progressがTrueのまま残ることを防止
    if st.session_state.generation_in_progress:
        st.session_state.generation_in_progress = False

    if selected_count == 0:
        st.warning("生成する画像案を選択してください（上のチェックボックス）")

    # 一括生成ボタン
    batch_btn = st.button(
        f"選択した{selected_count}案を一括生成",
        type="primary",
        disabled=(selected_count == 0),
        width="stretch",
    )

    # 個別生成ボタン群
    st.caption("または1案ずつ生成:")
    single_cols = st.columns(min(len(proposals), 4))
    single_btns = {}
    for i, proposal in enumerate(proposals):
        with single_cols[i % 4]:
            single_btns[i] = st.button(
                f"案{i+1}を生成",
                key=f"gen_single_{i}",
                width="stretch",
            )

    # --- 個別生成の実行 ---
    for i, clicked in single_btns.items():
        if clicked:
            proposal = proposals[i]
            with st.status(f"画像案{i+1}を生成中...", expanded=True) as status:
                try:
                    ok, text = generate_single_image(
                        proposal, i, config, pm,
                        aspect_ratio, image_size,
                        selected_taste_id, article_text,
                        site_name=st.session_state.current_site,
                    )
                    if ok:
                        status.update(label=f"画像案{i+1}の生成完了!", state="complete")
                    else:
                        status.update(label=f"画像案{i+1}の生成に失敗", state="error")
                        st.warning(text or "")
                except Exception as e:
                    status.update(label="エラー発生", state="error")
                    st.error(f"画像案{i+1}の生成中にエラー: {e}")
            st.rerun()

    # --- 一括生成の実行 ---
    if batch_btn:
        st.session_state.generation_in_progress = True
        st.session_state.generated_images = []

        progress_bar = st.progress(0, text="画像を生成中...")
        selected_indices = [i for i, s in enumerate(selected) if s]

        for step, idx in enumerate(selected_indices):
            proposal = proposals[idx]
            progress = (step + 1) / len(selected_indices)
            progress_bar.progress(progress, text=f"画像案{idx+1}を生成中... ({step+1}/{len(selected_indices)})")

            try:
                ok, text = generate_single_image(
                    proposal, idx, config, pm,
                    aspect_ratio, image_size,
                    selected_taste_id, article_text,
                    site_name=st.session_state.current_site,
                )
                if not ok:
                    st.warning(f"画像案{idx+1}の生成に失敗しました。{text or ''}")
            except Exception as e:
                st.error(f"画像案{idx+1}の生成中にエラー: {e}")

        progress_bar.progress(1.0, text="生成完了!")
        st.session_state.generation_in_progress = False
        st.rerun()

    # ----- 画像案の詳細編集（折りたたみ） -----
    st.divider()
    with st.expander("画像案の詳細を編集", expanded=False):
        for i, proposal in enumerate(proposals):
            st.markdown(f"**画像案{i+1}**")
            proposal["placement"] = st.text_input(
                "配置場所", value=proposal.get("placement", ""), key=f"prop_place_{i}"
            )
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                proposal["purpose"] = st.text_input(
                    "目的", value=proposal.get("purpose", ""), key=f"prop_purpose_{i}"
                )
            with p_col2:
                proposal["conclusion"] = st.text_input(
                    "結論", value=proposal.get("conclusion", ""), key=f"prop_conclusion_{i}"
                )

            proposal["layout_type"] = st.selectbox(
                "構図タイプ",
                config.get("layout_types", ["分類型", "比較型", "フロー型", "ピラミッド型", "アイコン軽量型"]),
                index=config.get("layout_types", []).index(proposal.get("layout_type", "分類型"))
                if proposal.get("layout_type") in config.get("layout_types", [])
                else 0,
                key=f"prop_layout_{i}",
            )

            # ブロック内容
            blocks = proposal.get("blocks", [])
            if blocks and isinstance(blocks[0], dict):
                block_text = "\n".join(
                    f"{b.get('heading', '')}: {b.get('description', '')}"
                    for b in blocks
                )
            else:
                block_text = "\n".join(str(b) for b in blocks)

            edited_blocks = st.text_area(
                "ブロック内容（1行1ブロック、「見出し: 説明」形式）",
                value=block_text,
                height=100,
                key=f"prop_blocks_{i}",
            )
            new_blocks = []
            for line in edited_blocks.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                if ": " in line:
                    heading, desc = line.split(": ", 1)
                    new_blocks.append({"heading": heading, "description": desc})
                else:
                    new_blocks.append({"heading": line, "description": ""})
            proposal["blocks"] = new_blocks

            proposal["composition_description"] = st.text_area(
                "構成イメージ説明",
                value=proposal.get("composition_description", ""),
                height=80,
                key=f"prop_comp_{i}",
            )
            st.divider()

# =============================================
# 生成結果の表示・後処理・ダウンロード
# =============================================
if st.session_state.generated_images:
    st.subheader("生成結果")

    images = st.session_state.generated_images

    for i, entry in enumerate(images):
        proposal = entry["proposal"]
        img = entry["image"]
        processed = entry.get("processed_image")

        st.markdown(f"### 画像案{entry['proposal_idx']+1}: {proposal.get('placement', '')}")
        st.caption(f"構図: {proposal.get('layout_type', '')} | 目的: {proposal.get('purpose', '')}")

        display_col, control_col = st.columns([2, 1])

        with display_col:
            display_img = processed if processed else img
            st.image(display_img, width="stretch")

        with control_col:
            # --- 微修正 ---
            st.markdown("**✏️ 微修正**")
            refine_text = st.text_area(
                "修正指示",
                placeholder="例: 背景をもう少し薄い水色に、見出しのフォントを大きく",
                height=80,
                key=f"refine_text_{i}",
            )
            if st.button("微修正して再生成", key=f"refine_btn_{i}", disabled=not refine_text.strip()):
                with st.spinner("微修正中..."):
                    try:
                        ok, text = refine_image(
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
            if st.button("🔄 同じ案で再生成", key=f"regen_btn_{i}", use_container_width=True):
                with st.spinner("再生成中..."):
                    try:
                        ok, text = generate_single_image(
                            proposal, entry["proposal_idx"], config, pm,
                            st.session_state.get("gen_aspect_ratio", "16:9"),
                            st.session_state.get("gen_image_size", "2K"),
                            st.session_state.get("selected_taste_id", "auto"),
                            st.session_state.article_text,
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
            if st.button("余白トリミング", key=f"trim_{i}"):
                trimmed = trim_whitespace(img)
                entry["processed_image"] = trimmed
                st.rerun()

            # リサイズ（px指定）
            current_img = processed if processed else img
            cur_w, cur_h = current_img.size
            st.caption(f"現在: {cur_w}×{cur_h}px")
            resize_c1, resize_c2 = st.columns(2)
            with resize_c1:
                target_w = st.number_input(
                    "幅(px)", value=886, min_value=100, max_value=4096,
                    key=f"resize_w_{i}",
                )
            with resize_c2:
                target_h = st.number_input(
                    "高さ(px)", value=600, min_value=100, max_value=4096,
                    key=f"resize_h_{i}",
                )
            if st.button(f"リサイズ ({target_w}×{target_h})", key=f"resize_{i}"):
                source = processed if processed else img
                resized = resize_to_target(source, target_w, target_h)
                entry["processed_image"] = resized
                st.rerun()

            # タイトル合成
            title_for_overlay = st.text_input(
                "タイトルテキスト",
                value=article_title,
                key=f"title_input_{i}",
            )
            if st.button("タイトルを合成", key=f"add_title_{i}"):
                source = processed if processed else img
                titled = add_title_overlay(
                    source,
                    title_for_overlay,
                    font_size=32,
                    bg_color=config.get("primary_color", "#000000"),
                    bg_opacity=0.8,
                )
                entry["processed_image"] = titled
                st.rerun()

            # ダウンロード
            st.divider()
            download_img = processed if processed else img
            img_bytes = image_to_bytes(download_img)
            st.download_button(
                "この画像をダウンロード",
                data=img_bytes,
                file_name=f"seo_image_{entry['proposal_idx']+1}_{i}.png",
                mime="image/png",
                key=f"dl_{i}",
                width="stretch",
            )

        st.divider()

    # 一括ダウンロード
    st.subheader("一括ダウンロード")
    if st.button("全画像をZIPでダウンロード", width="stretch", key="dl_all_zip"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, entry in enumerate(images):
                dl_img = entry.get("processed_image") or entry["image"]
                img_bytes = image_to_bytes(dl_img)
                filename = f"seo_image_{entry['proposal_idx']+1}.png"
                zf.writestr(filename, img_bytes)

        st.download_button(
            "ZIPファイルをダウンロード",
            data=buf.getvalue(),
            file_name=f"seo_images_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            key="dl_zip_file",
            width="stretch",
        )
