"""
3層プロンプトテンプレート
Layer1: デザインシステム（サイト固有のスタイル定義）
Layer2: 画像案提案（記事分析→3-5案のJSON出力）
Layer3: 画像生成（Layer1 + 構成説明を結合）
"""

from __future__ import annotations

# =============================================================
# Layer 1: デザインシステムプロンプト
# サイト設定のパラメータで動的に生成される
# =============================================================
DESIGN_SYSTEM_TEMPLATE = """あなたはプロのUIデザイナーです。
以下のデザインシステムを厳密に適用して画像を生成してください。

== ブランド ==
言語: {language}
※サイト名・ブランド名（{brand_name}）を画像内に表示してはならない。画像内テキストは読者にとって有益な情報のみにすること。

== 配色パレット ==
- 背景色: {background_color}
- メイン色: {primary_color}
- サブ色: {secondary_color}
- アクセント色（強調）: {accent_color}
- テキスト色: {text_color}
- 警告・重要色: {danger_color}
※上記以外の色の使用は禁止

== イラストレーション・タッチ ==
- スタイル: {illustration_style}
- 線の太さ・質感: {line_weight}
- 人物造形: {character_style}
- 塗り: {fill_style}
- 背景描写: 人物の背景（部屋、家具、床の線）は一切描かない

== UI・レイアウト構造 ==
- カード: {card_style}
- フォント: {font_family}相当の、癖のないモダンゴシック体。細字・丸文字は禁止
- 余白: {spacing}
- ブロック構造: 「小見出し帯 → イラスト → 説明文」の縦積みを基本とする

== 禁止事項 ==
{prohibited_elements}

== 追加スタイルノート ==
{additional_notes}

== 参照画像から抽出したデザイン特徴（最重要・厳守） ==
{ref_image_analysis}
"""

# =============================================================
# Layer 2: 画像案提案プロンプト
# 記事本文を分析して3-5個の画像案をJSON形式で提案する
# =============================================================
IMAGE_PROPOSAL_TEMPLATE = """あなたはSEO記事の画像設計ディレクターです。
あなたの仕事は「記事の構造整理」ではなく「読者の体験設計」です。

各H2セクションに来た読者が「今、何を不安に思っているか」「何がわかれば安心するか」を考え、
その読者の気持ちに寄り添う画像案を3〜5個設計してください。

== 記事本文 ==
{article_text}

== 最重要原則：読者ファーストの画像設計 ==
画像を設計する際、必ず以下の順序で考えること：

1. **読者の気持ちを想像する**: このH2に来た読者は今何を知りたい？何が不安？
2. **何を見せたら解決するか考える**: 比較表？具体的なモノの画像？ステップ？数字？
3. **記事の主題を視覚的に表現する**: 記事がリカバリーウェアの話ならリカバリーウェアを着た人を描く。料理の話なら料理を描く。読者が「この記事は自分に関係ある」と一瞬で感じるビジュアルにする
4. **最後に構図を決める**: 内容が決まってから、それを最も伝えやすい構図を選ぶ

== 画像案数の決定ルール ==
- 入口H2（導入・全体像）：必ず1つ。読者が「この記事は自分向けだ」と感じる画像
- 実務ブロックH2（具体手順・比較・選び方）：必ず1つ。読者の判断を助ける画像
- ケース系H2（例外・応用・パターン）：必要なら1つ
- 合計3〜5案（5案を超えない）

== 構図の選び方（内容に合わせて選ぶ） ==
使用可能な構図: {layout_types}

- 分類型（横3 or 横4 or 2×2）: 「3つのメリット」「4つのポイント」など項目を並列で見せたい時
- 比較型（横並び2〜3列）: 製品比較、A vs B、ビフォーアフター
- フロー型（横ステップ）: 手順・流れ・プロセスを見せる時のみ
- ピラミッド型: 重要度の階層がある時のみ

※構図は内容から自然に決まる。先に構図を決めてから内容を当てはめるのは禁止

== 各ブロックのイラスト指示ルール ==
- 記事の主題に関連する具体的なモノ・人・場面を描くこと
- 抽象的なアイコン（丸に￥マーク等）より、具体的なイラスト（実際のウェアを着た人等）を優先
- 読者が「あ、これのことか」と直感でわかるビジュアルにする

== 1画像あたりの情報量（厳守：文字化け防止のため文字数を抑える） ==
画像内テキストは最小限にすること。AI画像生成は文字が多いと描画が崩れる。
- 見出し: 最大8文字以内
- 説明文: 最大20文字×2行まで（それ以上は削る）
- 横3: 各カード見出し+説明1〜2行
- 横4: 各カード見出し+説明1行のみ
- 2×2: 各カード見出し+説明1〜2行
- 比較型: 左右で同じ情報量。各項目は見出し+1行
- フロー型: 各ステップ見出し+説明1行のみ（文字が多いと崩れるため最も注意）
- 画像全体で合計100文字以内を目安とする

== アスペクト比の推奨 ==
情報量が多い場合は縦長アスペクト比を推奨する。JSONに "recommended_aspect_ratio" で指定すること。
- ブロック2〜3個で情報少なめ → "16:9"（横長）
- ブロック3〜4個で標準量 → "4:3"（やや横長）
- ブロック4個以上 or 比較型で項目多め → "3:4"（やや縦長）
- 比較型で左右に3項目以上ずつ → "9:16"（縦長）

== トンマナ ==
- ブランドトーン: {brand_tone}
- 画像サイズ: {image_width}×{image_height}px の画角で潰れない情報量を維持

== 出力形式（JSON配列で必ず出力） ==
```json
[
  {{
    "placement": "H2: [見出しテキスト]",
    "reader_mindset": "このH2に来た読者が今思っていること・知りたいこと",
    "purpose": "この画像で読者の何を解決するか",
    "conclusion": "画像を見た読者が得る結論（1文）",
    "layout_type": "分類型|比較型|フロー型|ピラミッド型",
    "layout_reason": "読者にとってこの構図がベストな理由",
    "blocks": [
      {{"heading": "見出し", "description": "説明文", "illustration": "描くべき具体的なイラスト内容（記事の主題に関連するモノ・人・場面）"}}
    ],
    "recommended_aspect_ratio": "16:9|4:3|3:4|9:16（情報量に応じて選択）",
    "composition_description": "空間配置の説明のみ（下記ルール厳守）"
  }}
]
```

== composition_description の記述ルール（厳守） ==
書くこと：
- 要素の空間配置（「上部にタイトル帯、下部に横3カードを等間隔で配置」等）
- グリッド構造（「2×2グリッド」「横並び3列」等）
- 各ブロック内に描くイラストの配置（「カード上部にイラスト、下部にテキスト」等）

**絶対に書かない**こと：
- サイト名・ブランド名 → 画像内に入れない
- 色の指示 → デザインシステムが管理
- イラストのスタイル/タッチ → 参照画像が管理
- 雰囲気/印象の形容 → ブランドトーンが管理

== 禁止事項 ==
- サイト名・ブランド名を画像タイトルに入れること（読者にとって無意味）
- 表の丸写し、本文の長文転載
- 抽象的なアイコンだけで記事主題のビジュアルがない画像
- 構図を先に決めてから内容を当てはめること
- composition_descriptionにスタイル/色/雰囲気を記述すること
"""

# =============================================================
# Layer 3: 画像生成プロンプト
# デザインシステム + 構成説明を結合して最終プロンプトを組み立てる
# =============================================================
IMAGE_GENERATION_TEMPLATE = """{design_system_prompt}

== 画像生成リクエスト ==
以下の内容で{layout_type}のインフォグラフィック画像を作成してください。

【読者の状況】{reader_mindset}
【この画像の役割】{purpose}
【読者が得る結論】{conclusion}

== コンテンツブロック ==
{blocks_text}

== 構成イメージ ==
{composition_description}

== イラスト指示 ==
- 各ブロックには記事の主題に関連する具体的なイラストを必ず描くこと
- 抽象的なアイコン（丸に記号）ではなく、読者が「あ、これのことか」と直感でわかる具体的なモノ・人・場面を描く
- 人物イラストを描く場合は、参照画像と同じタッチ・頭身・表情で描くこと

== テキスト描画ルール（厳守：文字化け防止） ==
- 画像内テキストは最小限にすること。文字数が多いと描画が崩れる
- 各見出しは8文字以内、説明文は20文字×2行以内
- 画像全体で合計100文字以内
- 文字サイズは十分に大きく、判読可能なサイズで配置
- 文字が重なったり、はみ出したりしないよう余白を十分に確保
- 長い文は短く言い換えてでも文字数を削ること

== 技術要件 ==
- アスペクト比: {aspect_ratio}
- デザインシステムの配色を厳守
- 視覚的階層: タイトル > メインコンテンツ > 補足情報
- 画像内のテキストはすべて{language}で記述
- サイト名・ブランド名は画像内に表示しない
"""

# =============================================================
# 参照画像あり時の短縮プロンプト
# スタイルは全て参照画像に任せ、テキストでは「何を描くか」だけ伝える
# =============================================================
IMAGE_GENERATION_WITH_REF_TEMPLATE = """添付の参照画像と同じビジュアルスタイルで、{layout_type}のインフォグラフィック画像を作成してください。
スタイル（色・線・塗り・人物タッチ・カード形状・余白）はすべて参照画像を模倣すること。

【タイトル】{conclusion}

{blocks_text}

【構成】{composition_description}

テキストは{language}で記述。画像内テキストは合計100文字以内。サイト名は入れない。
"""

# 参照画像なし時に使う従来のスタイルトランスファー指示（フォールバック）
STYLE_TRANSFER_PREFIX = """【最重要指示】
この指示に添付されている参照画像は、出力すべきデザインスタイルの見本です。
以下の全要素において、参照画像のビジュアルスタイルを厳密に模倣してください：

- 背景の色味・質感を参照画像と同一にする
- カード/ボックスの角丸・枠線・影の有無を参照画像と完全一致させる
- 見出し帯の色・形状・テキスト色を参照画像に合わせる
- イラストの線の太さ・均一さ・ベクター感を参照画像と同一にする
- 人物の頭身・顔の描き方（目・口の表現）を参照画像に揃える
- 塗りスタイル（フラット/グラデーション/影の有無）を参照画像に完全一致させる
- 色使いを参照画像の配色パレットに限定する（参照画像にない色は使わない）
- 余白の取り方・要素間の間隔を参照画像に揃える

参照画像のスタイルと、下記のデザインシステム指示が矛盾する場合は、参照画像のビジュアルを優先してください。

---
"""


def render_design_system(config: dict) -> str:
    """サイト設定からデザインシステムプロンプトを生成"""
    return DESIGN_SYSTEM_TEMPLATE.format(
        brand_name=config.get("brand_name", ""),
        language=config.get("language", "Japanese"),
        background_color=config.get("background_color", "#FFFFFF"),
        primary_color=config.get("primary_color", "#3B82F6"),
        secondary_color=config.get("secondary_color", "#10B981"),
        accent_color=config.get("accent_color", "#F59E0B"),
        text_color=config.get("text_color", "#1F2937"),
        danger_color=config.get("danger_color", "#E74A3B"),
        illustration_style=config.get("illustration_style", "flat minimal"),
        line_weight=config.get("line_weight", "2.8〜3.2px統一"),
        character_style=config.get("character_style", "4頭身前後、記号的表現"),
        fill_style=config.get("fill_style", "フラット塗り"),
        card_style=config.get("card_style", "白背景 + 角丸28px"),
        font_family=config.get("font_family", "Noto Sans JP Medium"),
        spacing=config.get("spacing", "広めに均等"),
        prohibited_elements=config.get("prohibited_elements", ""),
        additional_notes=config.get("additional_notes", ""),
        ref_image_analysis=config.get("ref_image_analysis", "（参照画像なし）"),
    )


def render_proposal_prompt(article_text: str, config: dict) -> str:
    """記事本文とサイト設定から画像案提案プロンプトを生成"""
    image_size = config.get("image_sizes", {}).get("article", {})
    return IMAGE_PROPOSAL_TEMPLATE.format(
        article_text=article_text,
        layout_types="、".join(config.get("layout_types", [
            "分類型", "比較型", "フロー型", "ピラミッド型", "アイコン軽量型"
        ])),
        brand_tone=config.get("brand_tone", "professional and approachable"),
        image_width=image_size.get("width", 886),
        image_height=image_size.get("height", 600),
    )


def render_generation_prompt(
    design_system: str,
    proposal: dict,
    aspect_ratio: str,
    language: str = "Japanese",
    has_reference_images: bool = False,
) -> str:
    """デザインシステム + 画像案から最終生成プロンプトを組み立てる"""
    blocks = proposal.get("blocks", [])
    if blocks and isinstance(blocks[0], dict):
        lines = []
        for b in blocks:
            line = f"- 【{b.get('heading', '')}】{b.get('description', '')}"
            illust = b.get("illustration", "")
            if illust:
                line += f"　→ イラスト: {illust}"
            lines.append(line)
        blocks_text = "\n".join(lines)
    else:
        blocks_text = "\n".join(f"- {b}" for b in blocks)

    base_prompt = IMAGE_GENERATION_TEMPLATE.format(
        design_system_prompt=design_system,
        layout_type=proposal.get("layout_type", ""),
        reader_mindset=proposal.get("reader_mindset", ""),
        purpose=proposal.get("purpose", ""),
        conclusion=proposal.get("conclusion", ""),
        blocks_text=blocks_text,
        composition_description=proposal.get("composition_description", ""),
        aspect_ratio=aspect_ratio,
        language=language,
    )

    # 参照画像がある場合、スタイルトランスファー指示を先頭に付与
    if has_reference_images:
        return STYLE_TRANSFER_PREFIX + base_prompt

    return base_prompt
