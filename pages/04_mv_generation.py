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


def _get_preset_data(config, site_name):
    """選択中プリセットのデータを取得する。プリセット未使用時はサイトレベルを返す。"""
    cm = get_cm()
    mv_presets = config.get("mv_presets", [])
    preset_id = st.session_state.get("mv_active_preset_id", None)

    if preset_id and mv_presets:
        preset = next((p for p in mv_presets if p["id"] == preset_id), None)
        if preset:
            return {
                "preset_id": preset_id,
                "mv_ref_images": cm.get_reference_pil_images(site_name, category="mv", preset_id=preset_id) if site_name else [],
                "mv_design_analysis": preset.get("mv_ref_image_analysis", ""),
                "mv_design_spec": preset.get("mv_design_spec", ""),
                "mv_style_hints": preset.get("mv_style_hints", None),
                "mv_slot_structure": preset.get("mv_slot_structure", None),
            }

    # 後方互換: サイトレベルのデータを使用
    return {
        "preset_id": None,
        "mv_ref_images": cm.get_reference_pil_images(site_name, category="mv") if site_name else [],
        "mv_design_analysis": config.get("mv_ref_image_analysis", ""),
        "mv_design_spec": config.get("mv_design_spec", ""),
        "mv_style_hints": config.get("mv_style_hints", None),
        "mv_slot_structure": config.get("mv_slot_structure", None),
    }


def generate_mv_image(mv_proposal, idx, config, aspect_ratio, image_size, site_name=None):
    """1案分のMV画像を生成して session_state.mv_generated_images に追加する"""
    gemini = GeminiClient(api_key=st.session_state.api_key)
    design_system = render_design_system(config)

    # プリセットまたはサイトレベルのデータを取得
    pd = _get_preset_data(config, site_name)

    mv_ref_images = pd["mv_ref_images"]
    if mv_ref_images:
        reference_images = mv_ref_images
        st.info(f"MV参照画像を{len(mv_ref_images)}枚使用")
    else:
        reference_images = []

    # MV参照画像の分析結果を取得
    mv_design_analysis = pd["mv_design_analysis"]

    # サイトカラー（MV生成で最優先される）
    site_colors = {
        "primary_color": config.get("primary_color", "#3B82F6"),
        "secondary_color": config.get("secondary_color", "#10B981"),
        "accent_color": config.get("accent_color", "#F59E0B"),
        "background_color": config.get("background_color", "#FFFFFF"),
        "text_color": config.get("text_color", "#1F2937"),
        "danger_color": config.get("danger_color", "#E74A3B"),
    }

    # MVデザイン仕様書
    mv_design_spec = pd["mv_design_spec"]

    # サイト別MVスタイル補強ヒント
    mv_style_hints = pd["mv_style_hints"]

    # MVスロット構造
    mv_slot_structure = pd["mv_slot_structure"]

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
        mv_style_hints=mv_style_hints,
        mv_slot_structure=mv_slot_structure,
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
            "generation_prompt": gen_prompt,
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

    # MV参照画像を取得（プリセット対応）
    pd = _get_preset_data(config, site_name)
    mv_ref_images = pd["mv_ref_images"]

    # contents組み立て: 参照画像 → 生成済み画像（修正対象） → 元プロンプト+修正指示
    contents = []

    # 1. 参照画像（スタイルの基準）
    if mv_ref_images:
        for ref_img in mv_ref_images:
            contents.append(ref_img)

    # 2. 生成済み画像（修正対象として明示）
    contents.append(current_img)

    # 3. 元の生成プロンプト + 修正指示
    original_prompt = entry.get("generation_prompt", "")
    if original_prompt:
        contents.append(
            f"上記の最後の1枚は、以下のプロンプトで生成した画像です。\n\n"
            f"--- 元のプロンプト ---\n{original_prompt}\n--- ここまで ---\n\n"
            f"この画像を以下の点だけ修正してください。それ以外のレイアウト・テキスト内容・配色・装飾はすべて維持すること。\n\n"
            f"【修正指示】\n{refinement_text}"
        )
    else:
        # フォールバック（generation_prompt未保存の古いエントリ）
        contents.append(
            "上記の最後の1枚を以下の指示に従って微修正してください。"
            "レイアウト構造・テキスト内容・テキスト装飾スタイル・配色は変更せず、指示された部分のみを修正してください。\n\n"
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

# --- MVプリセット選択 ---
cm = get_cm()
mv_presets = config.get("mv_presets", [])

if mv_presets:
    # プリセットがある場合はプルダウン表示
    preset_labels = []
    for p in mv_presets:
        slot_info = ""
        slot_struct = p.get("mv_slot_structure", {})
        if slot_struct and slot_struct.get("slots"):
            roles = [s["role"] for s in slot_struct["slots"]]
            slot_info = f"（{', '.join(roles)}）"
        preset_labels.append(f"{p['name']}{slot_info}")

    # 初期値をセッションステートから復元
    active_preset_id = st.session_state.get("mv_active_preset_id", mv_presets[0]["id"])
    active_idx = 0
    for pi, p in enumerate(mv_presets):
        if p["id"] == active_preset_id:
            active_idx = pi
            break

    selected_preset_label = st.selectbox(
        "MVプリセット",
        preset_labels,
        index=active_idx,
        key="mv_gen_preset_selector",
    )
    selected_idx = preset_labels.index(selected_preset_label)
    st.session_state.mv_active_preset_id = mv_presets[selected_idx]["id"]

    # 選択中プリセットの情報を表示
    active_preset = mv_presets[selected_idx]
    pd = _get_preset_data(config, st.session_state.current_site)

    ref_count = len(pd["mv_ref_images"])
    if ref_count > 0:
        st.success(f"MV参照画像: {ref_count}枚登録済み（{active_preset['name']}）")
    else:
        st.warning(f"MV参照画像が未登録です（{active_preset['name']}）。「サイト設定」→「参照画像」→「MV用」タブから登録してください。")

    slot_struct = pd["mv_slot_structure"]
    if slot_struct and slot_struct.get("slots"):
        slot_roles = [s["role"] for s in slot_struct["slots"]]
        st.success(f"MVスロット構造: 検出済み（{', '.join(slot_roles)}）→ V2テンプレートで生成")
    elif pd["mv_design_spec"].strip():
        st.success("MVデザイン仕様書: 登録済み（生成時に使用されます）")
    else:
        st.info("MVデザイン仕様書: 未登録（参照画像のみで生成します）")
else:
    # プリセットなし → 従来通りサイトレベル
    st.session_state.mv_active_preset_id = None

    mv_ref_count = len(cm.list_reference_images(st.session_state.current_site, category="mv"))
    if mv_ref_count > 0:
        st.success(f"MV参照画像: {mv_ref_count}枚登録済み")
    else:
        st.warning("MV参照画像が未登録です。「サイト設定」→「参照画像」→「MV用」タブから登録すると、スタイルが安定します。")

    if config.get("mv_slot_structure"):
        slot_roles = [s["role"] for s in config["mv_slot_structure"].get("slots", [])]
        st.success(f"MVスロット構造: 検出済み（{', '.join(slot_roles)}）→ V2テンプレートで生成")
    elif config.get("mv_design_spec", "").strip():
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
            _pd = _get_preset_data(config, st.session_state.current_site)
            mv_slot_structure = _pd["mv_slot_structure"]
            mv_proposals = propose_mv_images(
                article_title, article_text, gemini,
                mv_slot_structure=mv_slot_structure,
            )

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
    # 空のテンプレートを1つ追加（スロット構造がある場合はそのスロットのみ）
    _pd_manual = _get_preset_data(config, st.session_state.current_site)
    mv_slot_structure = _pd_manual["mv_slot_structure"]
    empty_proposal = {"person_description": ""}
    if mv_slot_structure and "slots" in mv_slot_structure:
        for s in mv_slot_structure["slots"]:
            empty_proposal[s["role"]] = ""
    else:
        empty_proposal.update({
            "hook_text": "",
            "main_title": "",
            "subtitle": "",
            "band_text": "",
            "supplement_text": "",
        })
    st.session_state.mv_proposals = [empty_proposal]
    st.session_state.mv_selected_proposals = [True]

# =============================================
# Step 3: MV案の表示・編集
# =============================================
if st.session_state.mv_proposals:
    mv_proposals = st.session_state.mv_proposals
    mv_selected = st.session_state.mv_selected_proposals

    st.subheader("Step 3: MVテキスト内容を確認・編集")

    # スロット構造情報（プリセット対応）
    _pd_step3 = _get_preset_data(config, st.session_state.current_site)
    mv_slot_structure = _pd_step3["mv_slot_structure"]
    active_roles = None  # None = 全スロット表示（従来互換）
    if mv_slot_structure and "slots" in mv_slot_structure:
        active_roles = [s["role"] for s in mv_slot_structure["slots"]]
        absent = mv_slot_structure.get("absent_slots", [])
        with st.expander("検出されたMVスロット構造", expanded=False):
            for s in mv_slot_structure["slots"]:
                st.markdown(f"- **{s['role']}**: {s.get('description', '')}")
            if absent:
                st.caption(f"存在しないスロット: {', '.join(absent)}")
            if mv_slot_structure.get("person_style"):
                st.caption(f"人物スタイル: {mv_slot_structure['person_style']}")
            if mv_slot_structure.get("background_summary"):
                st.caption(f"背景: {mv_slot_structure['background_summary']}")
    else:
        # 従来のテンプレート構造説明
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

    # スロット入力UIの設定
    # V2 slot structure uses "hook", V1 uses "hook_text" — 両方対応
    slot_ui_config = {
        "hook_text": {"label": "煽りテキスト（5〜10文字）", "placeholder": "例: 今話題の, 〇〇で人気"},
        "hook": {"label": "煽りテキスト（5〜10文字）", "placeholder": "例: 今話題の, 〇〇で人気"},
        "main_title": {"label": "メインタイトル（2〜15文字）", "placeholder": "例: リライブシャツ, 看護師ボーナス"},
        "subtitle": {"label": "サブタイトル（8〜15文字）", "placeholder": "例: 本当に効果はある？"},
        "band_text": {"label": "帯テキスト（10〜20文字）", "placeholder": "例: リアルな口コミを調査！"},
        "supplement_text": {"label": "補足テキスト（15〜25文字）", "placeholder": "例: 期待できる効果や安く買う方法まで紹介"},
    }

    for i, mv_proposal in enumerate(mv_proposals):
        mv_selected[i] = st.checkbox(
            f"MV案{i+1}: {mv_proposal.get('main_title', '未設定')}",
            value=mv_selected[i],
            key=f"mv_select_{i}",
        )

        with st.expander(f"MV案{i+1}を編集", expanded=(len(mv_proposals) == 1)):
            # プレビュー（現在の内容を表示）
            st.markdown("**現在のテキスト内容:**")
            preview_col1, preview_col2 = st.columns([2, 1])
            with preview_col1:
                for role in (active_roles or ["hook_text", "main_title", "subtitle", "band_text", "supplement_text"]):
                    val = mv_proposal.get(role, "")
                    if val:
                        if role == "main_title":
                            st.markdown(f"### {val}")
                        elif role == "band_text":
                            st.info(val)
                        elif role == "supplement_text":
                            st.caption(val)
                        else:
                            st.markdown(f"*{val}*")

            with preview_col2:
                person = mv_proposal.get("person_description", "")
                if person:
                    st.markdown(f"**人物:** {person}")

            st.divider()
            st.markdown("**各スロットを編集:**")

            # 動的スロットUI: active_rolesがある場合はそのスロットのみ表示
            display_roles = active_roles or ["hook_text", "main_title", "subtitle", "band_text", "supplement_text"]
            for role in display_roles:
                ui_conf = slot_ui_config.get(role, {"label": role, "placeholder": ""})
                mv_proposal[role] = st.text_input(
                    ui_conf["label"],
                    value=mv_proposal.get(role, ""),
                    placeholder=ui_conf["placeholder"],
                    key=f"mv_{role}_{i}",
                )

            # メイン人物（常に表示）
            mv_proposal["person_description"] = st.text_area(
                "メイン人物の説明",
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
            title = mv_proposal.get("main_title", "")
            subtitle = mv_proposal.get("subtitle", "") or mv_proposal.get("band_text", "")
            # タイトルとサブタイトル/帯テキストで区別がつくラベルを作る
            short_label = subtitle[:12] if subtitle else title[:12]
            single_btns[i] = st.button(
                f"案{i+1}: {short_label}",
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
