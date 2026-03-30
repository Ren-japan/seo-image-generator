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

【この画像の目的】{purpose}
【読者が得る結論】{conclusion}

{blocks_text}

【構成】{composition_description}

- 各ブロックのイラストは大きく、具体的に描く（アイコンではなく人物・モノの場面描写）
- テキストは{language}で記述。画像内テキストは合計100文字以内
- サイト名・ブランド名は画像内に入れない
"""

# =============================================================
# MV（メインビジュアル/アイキャッチ）用テンプレート
# テンプレート型: 構造・配置・装飾を完全固定、中身だけ変わる
# =============================================================

# デフォルトMVデザイン仕様書（色を柔軟にし、構造・比率・装飾のみ精密に記述）
# 参照画像5枚の共通パターンを抽出: 色はバラバラだが構造は統一
MV_DESIGN_SPEC_DEFAULT = """== 背景 ==
- 上部約65%: テーマカラーのグラデーション（左上から右下へ、濃→やや薄）
- 下部約35%: 白（またはごく薄いグレー）
- 境界: なめらかなグラデーション遷移（ハードな直線分割は避ける）

== 煽りテキスト（hook_text） ==
- 位置: 左上、画像上端から約8%の位置
- フォントサイズ: 画像高さの約4%
- スタイル: テーマカラー系の角丸ピル（pill型背景）に白文字
- ピルの角丸: 完全な丸み（radius 50%）
- ピルの内側余白: 上下2%, 左右4%程度

== メインタイトル（main_title） ==
- 位置: 左寄せ、画像左端から8%、上端から約25%
- フォントサイズ: 画像高さの約11%（最も大きい、超太字）
- 装飾:
  - 文字色: 白
  - 縁取り: テーマカラーの二重アウトライン（内側2px + 外側4px程度）
  - ドロップシャドウ: 右下方向に軽いシャドウ（opacity 30%程度）
- 占有幅: 画像幅の55〜60%（右側の人物と重ならない）

== サブタイトル（subtitle） ==
- 位置: メインタイトル直下、同じ左マージン
- フォントサイズ: 画像高さの約5%（太字）
- 装飾:
  - 文字色: アクセントカラー（暖色系推奨: 赤・オレンジ等）
  - 縁取り: 白の細い縁取り（1〜2px）
  - ドロップシャドウ: メインタイトルと同様

== 帯テキスト（band_text） ==
- 位置: サブタイトルの下、上端から約60%
- 帯の幅: 画像幅の55〜60%、高さ: 画像高さの約7%
- 帯の色: 白（または非常に薄い色）
- テキスト色: ダークグレー〜黒（コントラスト確保）
- フォントサイズ: 画像高さの約3.5%
- 角丸: 4px程度

== 補足テキスト（supplement_text） ==
- 位置: 帯の下、左寄せ
- フォントサイズ: 画像高さの約3%
- 文字色: ダークグレー（#2C2C2C程度）
- 装飾: なし（シンプル）

== メイン人物 ==
- 位置: 画像右側、右端から5%内側
- サイズ: 高さは画像高さの約75%、幅は画像幅の約35%
- 配置: 下揃え（足が画像下端に接する or わずかに切れる）
- スタイル: フォトリアリスティック（写真風・実写風）
- 背景: なし（人物のみ切り抜き風に配置、透過的に背景に溶け込む）

== 全体のレイアウトバランス ==
- 左側テキスト領域: 画像幅の約65%
- 右側人物領域: 画像幅の約35%
- テキストと人物は重ならない
- 上下左右マージン: 画像サイズの約8%
- テキストの縦方向の並び: 煽り → メインタイトル → サブタイトル → 帯 → 補足（上から順に等間隔ではなく、メインタイトル周辺に余白を多めにとる）

== テキストサイズ階層（厳守） ==
メインタイトル(11%) >> サブタイトル(5%) > 煽り(4%) ≈ 帯(3.5%) > 補足(3%)
※ メインタイトルとそれ以外のサイズ差を明確にすること（2倍以上の差）

== フォント ==
- すべて太めのゴシック体（Noto Sans JP Bold相当）
- メインタイトルは Extra Bold / Black ウェイト
"""

# MV用 Layer2: テンプレートの各スロットに入れる「中身」を提案
MV_PROPOSAL_TEMPLATE = """あなたはSEO記事のMV（メインビジュアル/アイキャッチ画像）のコピーライターです。

記事のタイトルと本文から、MV画像に入れるテキスト・ビジュアル要素の案を1〜3パターン考えてください。

== 記事タイトル ==
{article_title}

== 記事本文（概要把握用） ==
{article_text}

== MV画像のレイアウト構造（固定。変更不可） ==
以下の構造は固定です。あなたが考えるのは各スロットに入る「中身」だけです。

┌─────────────────────────────────────┐
│ [煽りテキスト]（左上・小さめ）        │
│                                     │
│ [メインタイトル]（左寄せ・超大きい）   │
│                                     │
│ [サブタイトル]（左寄せ・大きい・赤）   │
│                                     │
│ ┌帯─────────────────┐              │
│ │[帯テキスト1]        │ [メイン人物] │
│ └────────────────────┘（右側・大きい）│
│ [補足テキスト]（左下）                │
└─────────────────────────────────────┘
背景: 上部カラーグラデーション → 下部ホワイト

== 各スロットの役割 ==
- 煽りテキスト: 好奇心を刺激する短いフレーズ（5〜10文字。例: "今話題の", "〇〇で人気"）
- メインタイトル: 商品名やキーワード（2〜8文字。例: "リライブシャツ", "BAKUNE"）
- サブタイトル: 読者の疑問や関心事（8〜15文字。例: "本当に効果はある？", "口コミ・評判を調査！"）
- 帯テキスト1: 記事のベネフィットを一文で（10〜20文字。例: "リアルな口コミを調査！"）
- 補足テキスト: 記事でわかることの補足（15〜25文字。例: "期待できる効果や安く買う方法まで紹介"）
- メイン人物: MVに描く人物の説明（例: "スマホで口コミを見ている若い女性", "パジャマを着てリラックスしている人"）

== 出力形式（JSON配列で必ず出力） ==
```json
[
  {{
    "hook_text": "煽りテキスト",
    "main_title": "メインタイトル",
    "subtitle": "サブタイトル",
    "band_text": "帯テキスト1",
    "supplement_text": "補足テキスト",
    "person_description": "メイン人物の具体的な描写"
  }}
]
```

== ルール ==
- 各テキストは指定文字数の範囲内に収めること
- メインタイトルは記事の主題となる商品名・キーワードにする
- サブタイトルは読者の疑問形にすると効果的
- 帯テキスト1はベネフィットを端的に伝える
- メイン人物は記事のターゲット読者を想起させる人物にする
- テキストの内容は記事の本文に基づくこと（創作しない）
"""

# MV用 Layer3（参照画像あり・デザイン仕様書あり）: 参照画像 + 仕様書の二重指示
# 仕様書 = 手動記述 or Gemini自動分析結果。色はサイトカラーパレットで上書き。
MV_GENERATION_WITH_SPEC_TEMPLATE = """添付の参照画像と同じレイアウト構造・テキスト装飾・配置バランスで、テキスト内容と人物だけを差し替えたMV画像を作成してください。

== 重要: 配色の優先順位 ==
以下の配色ルールは、デザイン仕様書内の色指定（HEXコード）より**優先**する。
仕様書内の具体的な色コード（#36B0B0等）はあくまで参考値とし、実際の配色は以下に従うこと。

{color_instruction}

== デザイン仕様書（レイアウト・装飾・比率） ==
※ 以下の仕様書のうち、色以外の情報（位置%、サイズ%、装飾スタイル、配置ルール）は厳守すること。
{design_spec}

== 差し替えるテキスト内容 ==
- 左上の小さいテキスト: 「{hook_text}」
- メインタイトル（最も大きい文字）: 「{main_title}」
- サブタイトル（メインタイトルの下）: 「{subtitle}」
- 帯の上のテキスト: 「{band_text}」
- 下部の補足テキスト: 「{supplement_text}」
- 右側の人物: {person_description}

テキストはすべて{language}で記述。指定文字列のみ描画し、余計な文字を追加しない。
"""

# MV用 Layer3（参照画像あり・デザイン仕様書なし）: 参照画像 + サイト別補強ヒント
# Trial 16: 3層アーキテクチャ（参照画像主役 + 構造変数 + 条件付きoverrides）
#
# 設計思想:
#   Layer A: 参照画像がスタイルの主役（フォント・色・装飾は参照画像に委ねる）
#   Layer B: 構造系変数（person_crop等）でGeminiが苦手な空間配置のみ補強
#   Layer C: style_overrides（オプション）で参照画像だけでは伝わらない例外ルールのみ上書き
#
# JMROのように参照画像5枚+構造変数のみで80点超が出るケースでは
# overridesは空になり、「完全コピー」のみで矛盾ゼロのプロンプトになる。
#
# configの mv_style_hints に以下のキー:
#   [構造系 - 常に使用]
#   person_position    — 人物の配置位置（右側/左側）
#   person_size        — 人物の大きさ（高さ何%）
#   person_crop        — 人物のはみ出し方（右端で切れてよい等）
#   person_bottom      — 人物の足元処理（下端に接する等）
#   text_person_layer  — テキストと人物の前後関係（前面/背面）
#   background_style   — 背景のスタイル（白ベース+装飾 等）
#   supplement_style   — 補足テキストの表示スタイル
#   [装飾系 - オプション。overridesとして条件付き注入]
#   style_overrides    — 参照画像コピーへの上書きルール（文字列。なければ注入しない）
MV_GENERATION_WITH_REF_TEMPLATE = """添付の参照画像のデザインを完全にコピーして、テキスト内容と人物だけを差し替えた画像を生成してください。

【最重要原則】
参照画像のレイアウト構造・テキスト配置順序・フォント・色・装飾・背景・カード形状を完全にコピーすること。
参照画像に存在する要素だけを描画し、存在しない要素は絶対に追加しないこと。

{color_instruction}

== 人物 ==
- {person_crop}
- 配置: {person_position}
- 大きさ: {person_size}
- 足元: {person_bottom}
- {text_person_layer}
- 人物: {person_description}

== 背景 ==
{background_style}

== テキスト要素（文字列だけ差し替え。位置・順序・装飾は参照画像と完全に同じに） ==
{text_slots}
{style_overrides}
【テキストルール】
- 上記「」内の文字列を一字一句そのまま描画する。文言を変えたり省略したり追加しない
- テキストの配置順序は参照画像と同じにする（参照画像で上にあるものは上に、下にあるものは下に）
- 参照画像に存在しないテキスト要素は描画しない
- テキストは{language}のみ
"""

# MV用 Layer3（参照画像あり・スロット構造検出済み）: 超シンプル版
# mv_slot_structure がある場合のみ使用。参照画像に全て委ね、テキスト内容だけ差し替える。
MV_GENERATION_WITH_SLOT_STRUCTURE_TEMPLATE = """添付の参照画像のデザインを完全にコピーして、テキスト内容と人物だけを差し替えた画像を生成してください。

参照画像のレイアウト・色・フォント・装飾・背景・カード形状を全てコピーする。
参照画像に存在する要素だけを描画する。存在しない要素は追加しない。

{color_instruction}

== 差し替えるテキスト ==
{text_slots}

== 差し替える人物 ==
{person_description}

上記「」内の文字列を一字一句正確に描画する。それ以外のテキストは追加しない。テキストは{language}のみ。
{style_overrides}"""

# MV用 Layer3（参照画像なし）: テンプレート型フルプロンプト
# 色はサイトカラーパレット or AI自動判断。構造・比率・装飾のみ固定。
MV_GENERATION_TEMPLATE = """SEO記事のMV（メインビジュアル/アイキャッチ）画像を作成してください。

== 配色ルール ==
{color_instruction}

== レイアウト（厳守） ==
画像サイズ: 横長（{aspect_ratio}）
- 左側65%: テキスト要素すべて（上から煽り→タイトル→サブタイトル→帯→補足）
- 右側35%: メイン人物
- 上下左右マージン: 画像サイズの8%
- 背景: 上部65%はテーマカラー系のグラデーション → 下部35%は白（またはごく薄い色）

┌─────────────────────────────────────┐
│ [煽りテキスト] (ピル型の小さいラベル) │
│                                     │
│ [メインタイトル]（超大きい太字）      │
│     → 画像高さの11%相当フォント      │
│     → 白抜き+テーマカラーの二重縁取り │
│                                     │
│ [サブタイトル]（大きめ太字）          │
│     → 画像高さの5%相当フォント        │  [メイン人物]
│     → アクセントカラー or 白          │  → 右側配置
│                                     │  → 高さ75%
│ ┌帯─────────────────┐              │  → 幅35%
│ │[帯テキスト]         │              │  → フォトリアル
│ └────────────────────┘              │
│ [補足テキスト]（小さめ・控えめ）      │
│     → 画像高さの3%相当フォント        │
└─────────────────────────────────────┘

== メイン人物 ==
{person_description}
- フォトリアリスティックな人物として描く（イラストではなく写真風）
- 右側に配置、画像高さの約75%のサイズ
- 背景はなし（人物のみ切り抜き風に配置）

== テキスト装飾ルール（色名は配色ルールに従う） ==
- メインタイトル: 最も目立つ。白い文字+テーマカラーの太い縁取り（二重）+ドロップシャドウ
- サブタイトル: アクセントカラーの太字+白の縁取り+ドロップシャドウ
- 帯テキスト: 白帯（または淡色帯）+濃色テキスト、帯幅は画像幅の55〜60%
- 煽りテキスト: テーマカラーの角丸ピル背景+白文字、画像高さの4%相当フォント
- 補足テキスト: ダークグレー系、装飾なし
- すべて{language}の太めのゴシック体で描画

== テキスト階層（サイズ比 厳守） ==
メインタイトル(11%) > サブタイトル(5%) > 煽り/帯(4%) > 補足(3%)
※ パーセンテージは画像高さに対するフォントサイズ比

== 技術要件 ==
- アスペクト比: {aspect_ratio}
- 全テキストは{language}で記述
- 文字が崩れないよう、各テキストは短く保つ
- 視認性最優先：テキストが背景に埋もれないこと
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


def _build_blocks_text(proposal: dict) -> str:
    """proposalのblocksをテキスト化する共通処理"""
    blocks = proposal.get("blocks", [])
    if blocks and isinstance(blocks[0], dict):
        lines = []
        for b in blocks:
            line = f"- 【{b.get('heading', '')}】{b.get('description', '')}"
            illust = b.get("illustration", "")
            if illust:
                line += f"　→ イラスト: {illust}"
            lines.append(line)
        return "\n".join(lines)
    return "\n".join(f"- {b}" for b in blocks)


def render_mv_proposal_prompt(
    article_title: str,
    article_text: str,
    mv_slot_structure: dict | None = None,
) -> str:
    """記事タイトルと本文からMV画像案提案プロンプトを生成。

    mv_slot_structure がある場合、検出されたスロットのみ生成させる。
    """
    if not mv_slot_structure or "slots" not in mv_slot_structure:
        # フォールバック: 従来の5スロット版
        return MV_PROPOSAL_TEMPLATE.format(
            article_title=article_title,
            article_text=article_text[:3000],
        )

    # スロット構造対応版: 検出されたスロットのみ生成させる
    slots = mv_slot_structure["slots"]
    absent = mv_slot_structure.get("absent_slots", [])

    # スロット説明を組み立て
    role_labels = {
        "hook": ("煽りテキスト", "好奇心を刺激する短いフレーズ（5〜10文字）"),
        "main_title": ("メインタイトル", "記事の主題となる商品名・キーワード（2〜15文字）"),
        "subtitle": ("サブタイトル", "読者の疑問や関心事（8〜15文字）"),
        "band_text": ("帯テキスト", "記事のベネフィットを一文で（10〜20文字）"),
        "supplement_text": ("補足テキスト", "記事でわかることの補足（15〜25文字）"),
    }

    slot_lines = []
    json_keys = []
    for s in slots:
        role = s["role"]
        label, guide = role_labels.get(role, (role, ""))
        slot_lines.append(f"- {label}（{role}）: {guide}")
        json_keys.append(f'    "{role}": "{label}"')

    slot_section = "\n".join(slot_lines)
    json_fields = ",\n".join(json_keys)

    absent_section = ""
    if absent:
        absent_labels = [role_labels.get(a, (a, ""))[0] for a in absent]
        absent_section = (
            "\n※ 以下のスロットはこのMVデザインに存在しない。生成してはならない:\n"
            + "\n".join(f"- {lbl}" for lbl in absent_labels)
        )

    prompt = f"""あなたはSEO記事のMV（メインビジュアル/アイキャッチ画像）のコピーライターです。

記事のタイトルと本文から、MV画像に入れるテキスト・ビジュアル要素の案を1〜3パターン考えてください。

== 記事タイトル ==
{article_title}

== 記事本文（概要把握用） ==
{article_text[:3000]}

== このMVに存在するテキストスロット ==
{slot_section}
{absent_section}

== 出力形式（JSON配列で必ず出力） ==
```json
[
  {{
{json_fields},
    "person_description": "メイン人物の具体的な描写"
  }}
]
```

== ルール ==
- 上記スロットに対応するテキストのみ生成する。存在しないスロットのキーは出力に含めない
- 各テキストは指定文字数の範囲内に収めること
- メインタイトルは記事の主題となる商品名・キーワードにする
- メイン人物は記事のターゲット読者を想起させる人物にする
- テキストの内容は記事の本文に基づくこと（創作しない）
"""
    return prompt


def _build_mv_color_instruction(site_colors: dict | None = None, minimal: bool = False) -> str:
    """サイトカラーパレットからMV用の配色指示テキストを動的生成する。

    サイトカラーを配色のベース（アンカー）として渡す。
    参照画像が複数ありトーンがバラバラな場合でも、サイトカラーで配色を安定させる。

    minimal=True の場合（参照画像あり時）:
        テーマカラーのみ送る。accent_color等は参照画像に委ねる。
        accent_colorを送ると参照画像のスタイルと矛盾してタイトル色が狂う原因になる。
    """
    if site_colors:
        primary = site_colors.get("primary_color", "")

        if minimal:
            # 参照画像が主役の場合: テーマカラーだけで配色をアンカー
            lines = [
                "== 配色の基準 ==",
                f"- このサイトのテーマカラー: {primary}" if primary else "",
                "- それ以外の色は参照画像に従うこと",
            ]
        else:
            accent = site_colors.get("accent_color", "")
            bg = site_colors.get("background_color", "")
            text_c = site_colors.get("text_color", "")
            danger = site_colors.get("danger_color", "")
            lines = [
                "== 配色パレット（このサイトのブランドカラー。配色の基準として使うこと） ==",
                f"- テーマカラー: {primary}" if primary else "",
                f"- アクセントカラー: {accent or danger}" if (accent or danger) else "",
                f"- 背景ベース色: {bg}" if bg else "",
                f"- テキスト基本色: {text_c}" if text_c else "",
                "- 上記カラーパレットのトーンに合った配色で画像全体を統一すること",
            ]
        return "\n".join(line for line in lines if line)
    else:
        return (
            "== 配色 ==\n"
            "固定色の指定なし。参照画像がある場合は参照画像の配色に従うこと。\n"
            "参照画像がない場合は記事のテーマ・雰囲気に合った配色をAIが自動判断すること。"
        )


def _get_default_style_hints() -> dict:
    """mv_style_hintsが未設定の場合のデフォルト値（汎用的な指示）。

    Trial 16: 3層アーキテクチャ版
    構造系7変数のみ。フォント・色・装飾は参照画像に完全に委ねる。
    style_overrides は空文字列がデフォルト（= 参照画像コピーのみ、上書きなし）。

    デフォルト値は「参照画像のレイアウトを忠実にコピーする」ための汎用ガイド。
    参照画像から人物配置・背景・テキスト関係を自動的に読み取らせる。
    サイト固有のmv_style_hintsが設定されていればそちらが優先される。
    """
    return {
        "person_position": "参照画像と同じ位置・向き・ポーズで配置する。参照画像で人物が右側なら右側、左側なら左側に配置",
        "person_size": "参照画像と同じ大きさ・比率にする。参照画像で人物が大きければ大きく、小さければ小さく",
        "person_crop": "参照画像で人物が画像端で切れている場合、同じように切れてよい。全身が収まっている場合は全身を描く",
        "person_bottom": "参照画像と同じ足元の処理にする。下端で切れていれば切れてよい",
        "text_person_layer": "参照画像と同じ前後関係にする。テキストが人物の上に重なっているなら重ねる。分離しているなら分離する",
        "background_style": "参照画像と同じ背景スタイルを忠実に再現する。色・グラデーション・装飾パターン・カード型背景の有無をすべて参照画像からコピー",
        "supplement_style": "参照画像の補足テキストと同じスタイル。補足テキストがなければ描画しない",
        "style_overrides": "",  # 空 = 上書きなし。参照画像を完全コピー。
    }


def render_mv_generation_prompt(
    design_system: str,
    mv_proposal: dict,
    aspect_ratio: str,
    language: str = "Japanese",
    has_reference_images: bool = False,
    mv_design_analysis: str = "",
    site_colors: dict | None = None,
    mv_design_spec: str = "",
    mv_style_hints: dict | None = None,
    mv_slot_structure: dict | None = None,
) -> str:
    """MV画像案（テンプレート型）からMV生成プロンプトを組み立てる"""

    # 参照画像がある場合
    if has_reference_images:
        hook_text = mv_proposal.get("hook_text", "").strip()
        main_title = mv_proposal.get("main_title", "").strip()
        subtitle = mv_proposal.get("subtitle", "").strip()
        band_text = mv_proposal.get("band_text", "").strip()
        supplement_text = mv_proposal.get("supplement_text", "").strip()
        person_description = mv_proposal.get("person_description", "")
        text_params = dict(
            person_description=person_description,
            language=language,
        )

        # 手動デザイン仕様書がある場合 → 参照画像 + 仕様書 + 配色指示
        if mv_design_spec:
            color_instruction = _build_mv_color_instruction(site_colors)
            return MV_GENERATION_WITH_SPEC_TEMPLATE.format(
                design_spec=mv_design_spec,
                color_instruction=color_instruction,
                hook_text=hook_text,
                main_title=main_title,
                subtitle=subtitle,
                band_text=band_text,
                supplement_text=supplement_text,
                **text_params,
            )

        # V2: スロット構造検出済み → 超シンプルテンプレート
        # 参照画像に全て委ね、テキスト内容と人物だけ差し替える
        if mv_slot_structure and "slots" in mv_slot_structure:
            color_instruction = _build_mv_color_instruction(site_colors, minimal=True)
            # スロット構造からテキストスロットを組み立て
            text_lines = []
            for slot in mv_slot_structure["slots"]:
                role = slot["role"]
                value = mv_proposal.get(role, "").strip()
                if value:
                    desc = slot.get("description", role)
                    text_lines.append(f"- 「{value}」→ {desc}")
            text_slots = "\n".join(text_lines)
            # style_overrides（オプション）
            hints = mv_style_hints if mv_style_hints else {}
            raw_overrides = hints.get("style_overrides", "")
            if raw_overrides:
                style_overrides = (
                    "\n== 参照画像の補正ルール ==\n"
                    f"{raw_overrides}\n"
                )
            else:
                style_overrides = ""
            return MV_GENERATION_WITH_SLOT_STRUCTURE_TEMPLATE.format(
                color_instruction=color_instruction,
                text_slots=text_slots,
                person_description=person_description,
                language=language,
                style_overrides=style_overrides,
            )

        # Trial 16: 3層アーキテクチャ（V1フォールバック）
        #   Layer A: 参照画像（主役）
        #   Layer B: 構造系変数（人物配置・背景パターン）
        #   Layer C: style_overrides（オプション。参照画像で伝わらない例外ルールのみ）
        defaults = _get_default_style_hints()
        hints = mv_style_hints if mv_style_hints else defaults
        # 参照画像が主役 → カラーパレットは最小限（テーマカラーのみ）
        # accent_color等を送ると参照画像と矛盾してタイトル色が狂う
        color_instruction = _build_mv_color_instruction(site_colors, minimal=True)

        # style_overrides: 空なら注入しない。値があれば「上書きルール」として追加
        raw_overrides = hints.get("style_overrides", defaults["style_overrides"])
        if raw_overrides:
            style_overrides = (
                "\n== 参照画像の補正ルール（以下は参照画像のコピーに上書きする例外ルール） ==\n"
                f"{raw_overrides}\n"
            )
        else:
            style_overrides = ""

        # テキストスロットを動的組み立て: 空のスロットはプロンプトに含めない
        # 装飾指示は全て「参照画像と同じ」に委ねる（サイト固有の装飾ワードを混在させない）
        supplement_style = hints.get("supplement_style", defaults["supplement_style"])
        text_lines = []
        if hook_text:
            text_lines.append(f"- 「{hook_text}」→ 参照画像の煽りテキストと同じ位置・サイズ・色・装飾で描画")
        if main_title:
            text_lines.append(f"- 「{main_title}」→ 参照画像のメインタイトルと同じ位置・サイズ・色・太さ・装飾で描画（最も大きい文字）")
        if subtitle:
            text_lines.append(f"- 「{subtitle}」→ 参照画像のサブタイトルと同じ位置・サイズ・色・装飾で描画")
        if band_text:
            text_lines.append(f"- 「{band_text}」→ 参照画像の帯テキストと同じスタイルの帯/ボックス内に描画（帯の色・角丸・影も同じに）")
        if supplement_text:
            text_lines.append(f"- 「{supplement_text}」→ {supplement_style}")
        text_slots = "\n".join(text_lines)

        return MV_GENERATION_WITH_REF_TEMPLATE.format(
            color_instruction=color_instruction,
            person_position=hints.get("person_position", defaults["person_position"]),
            person_size=hints.get("person_size", defaults["person_size"]),
            person_crop=hints.get("person_crop", defaults["person_crop"]),
            person_bottom=hints.get("person_bottom", defaults["person_bottom"]),
            text_person_layer=hints.get("text_person_layer", defaults["text_person_layer"]),
            background_style=hints.get("background_style", defaults["background_style"]),
            style_overrides=style_overrides,
            text_slots=text_slots,
            **text_params,
        )

    # 参照画像なし → フルプロンプト（配色はサイトカラー or AI自動判断）
    color_instruction = _build_mv_color_instruction(site_colors)
    return MV_GENERATION_TEMPLATE.format(
        hook_text=mv_proposal.get("hook_text", ""),
        main_title=mv_proposal.get("main_title", ""),
        subtitle=mv_proposal.get("subtitle", ""),
        band_text=mv_proposal.get("band_text", ""),
        supplement_text=mv_proposal.get("supplement_text", ""),
        person_description=mv_proposal.get("person_description", ""),
        aspect_ratio=aspect_ratio,
        language=language,
        color_instruction=color_instruction,
    )


def render_generation_prompt(
    design_system: str,
    proposal: dict,
    aspect_ratio: str,
    language: str = "Japanese",
    has_reference_images: bool = False,
) -> str:
    """デザインシステム + 画像案から最終生成プロンプトを組み立てる"""
    blocks_text = _build_blocks_text(proposal)

    # 参照画像がある場合 → 短縮プロンプト（スタイルは画像に任せる）
    if has_reference_images:
        return IMAGE_GENERATION_WITH_REF_TEMPLATE.format(
            layout_type=proposal.get("layout_type", ""),
            purpose=proposal.get("purpose", ""),
            conclusion=proposal.get("conclusion", ""),
            blocks_text=blocks_text,
            composition_description=proposal.get("composition_description", ""),
            language=language,
        )

    # 参照画像なし → 従来のフルプロンプト
    return IMAGE_GENERATION_TEMPLATE.format(
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
